"""
Enhanced Model Service with Comprehensive Debugging and Proper Model Loading
Run with: uvicorn model_service:app --host 0.0.0.0 --port 8001 --workers 1
"""

import json
import torch
import gc
import os
import traceback
import psutil
import asyncio
import time
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from transformers import AutoTokenizer, AutoModelForCausalLM
import logging
from contextlib import asynccontextmanager
from enum import Enum
from datetime import datetime, timedelta
import uuid
from collections import deque
import threading
from pathlib import Path

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('/home/anews/NewsPic_G/translate_services/fastapi_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Request tracking for debugging
class RequestTracker:
    def __init__(self, max_size=100):
        self.requests = deque(maxlen=max_size)
        self.active_requests = {}
        
    def start_request(self, request_id: str, text_length: int):
        self.active_requests[request_id] = {
            "id": request_id,
            "start_time": datetime.now().isoformat(),
            "text_length": text_length,
            "status": "processing"
        }
        logger.info(f"[REQUEST_START] ID: {request_id}, Text length: {text_length}")
        
    def end_request(self, request_id: str, status: str, error: str = None):
        if request_id in self.active_requests:
            req = self.active_requests.pop(request_id)
            req["end_time"] = datetime.now().isoformat()
            req["status"] = status
            req["error"] = error
            self.requests.append(req)
            logger.info(f"[REQUEST_END] ID: {request_id}, Status: {status}, Error: {error}")
            
    def get_active(self):
        return list(self.active_requests.values())
    
    def get_history(self):
        return list(self.requests)

request_tracker = RequestTracker()

# Async Translation Storage Manager
class AsyncTranslationStorage:
    def __init__(self, storage_path: str = "/home/anews/NewsPic_G/translate_services/async_translations.json", max_translations: int = 500):
        self.storage_path = storage_path
        self.max_translations = max_translations
        self.lock = threading.Lock()
        self._ensure_storage_file()
    
    def _ensure_storage_file(self):
        """Ensure the storage file exists"""
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            logger.info(f"Created async translation storage file: {self.storage_path}")
    
    def _load_storage(self) -> Dict[str, Any]:
        """Load the storage file"""
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading storage file: {e}")
            return {}
    
    def _save_storage(self, data: Dict[str, Any]):
        """Save the storage file"""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving storage file: {e}")
            raise
    
    def _cleanup_old_translations(self, storage: Dict[str, Any]) -> Dict[str, Any]:
        """Remove oldest translations if exceeding max limit"""
        if len(storage) >= self.max_translations:
            # Sort by timestamp and keep only the newest
            sorted_items = sorted(
                storage.items(),
                key=lambda x: x[1].get('timestamp', ''),
                reverse=True
            )
            # Keep only max_translations - 1 to make room for new one
            storage = dict(sorted_items[:self.max_translations - 1])
            logger.info(f"Cleaned up old translations, kept {len(storage)} newest entries")
        return storage
    
    def save_translation(self, translation_id: str, text: str, translation: str, target_language: str, metadata: Dict[str, Any] = None) -> bool:
        """Save a translation with UUID"""
        with self.lock:
            try:
                storage = self._load_storage()
                
                # Cleanup if needed
                storage = self._cleanup_old_translations(storage)
                
                # Save new translation
                storage[translation_id] = {
                    "id": translation_id,
                    "original_text": text,
                    "translation": translation,
                    "target_language": target_language,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": metadata or {}
                }
                
                self._save_storage(storage)
                logger.info(f"Saved async translation: {translation_id}")
                return True
                
            except Exception as e:
                logger.error(f"Error saving translation {translation_id}: {e}")
                return False
    
    def get_translation(self, translation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a translation by UUID"""
        with self.lock:
            try:
                storage = self._load_storage()
                return storage.get(translation_id)
            except Exception as e:
                logger.error(f"Error retrieving translation {translation_id}: {e}")
                return None
    
    def delete_translation(self, translation_id: str) -> bool:
        """Delete a translation by UUID"""
        with self.lock:
            try:
                storage = self._load_storage()
                if translation_id in storage:
                    del storage[translation_id]
                    self._save_storage(storage)
                    logger.info(f"Deleted translation: {translation_id}")
                    return True
                return False
            except Exception as e:
                logger.error(f"Error deleting translation {translation_id}: {e}")
                return False
    
    def get_all_ids(self) -> List[str]:
        """Get all translation IDs"""
        with self.lock:
            try:
                storage = self._load_storage()
                return list(storage.keys())
            except Exception as e:
                logger.error(f"Error getting translation IDs: {e}")
                return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        with self.lock:
            try:
                storage = self._load_storage()
                return {
                    "total_translations": len(storage),
                    "max_translations": self.max_translations,
                    "storage_file": self.storage_path,
                    "oldest_translation": min(
                        (item.get('timestamp') for item in storage.values()),
                        default=None
                    ),
                    "newest_translation": max(
                        (item.get('timestamp') for item in storage.values()),
                        default=None
                    )
                }
            except Exception as e:
                logger.error(f"Error getting storage stats: {e}")
                return {
                    "error": str(e),
                    "total_translations": 0,
                    "max_translations": self.max_translations
                }

# Initialize async translation storage
async_storage = AsyncTranslationStorage()

# Custom exception classes
class ModelMemoryError(Exception):
    """Raised when model runs out of memory"""
    pass

class TokenLimitError(Exception):
    """Raised when input exceeds token limit"""
    pass

class ModelNotLoadedError(Exception):
    """Raised when model is not loaded"""
    pass

# Supported languages enum
class SupportedLanguage(str, Enum):
    ARABIC = "Arabic"
    BULGARIAN = "Bulgarian"
    CHINESE = "Chinese"
    CZECH = "Czech"
    DANISH = "Danish"
    DUTCH = "Dutch"
    ENGLISH = "English"
    FINNISH = "Finnish"
    FRENCH = "French"
    GERMAN = "German"
    GREEK = "Greek"
    GUJARATI = "Gujarati"
    HEBREW = "Hebrew"
    HINDI = "Hindi"
    HUNGARIAN = "Hungarian"
    INDONESIAN = "Indonesian"
    ITALIAN = "Italian"
    JAPANESE = "Japanese"
    KOREAN = "Korean"
    PERSIAN = "Persian"
    POLISH = "Polish"
    PORTUGUESE = "Portuguese"
    ROMANIAN = "Romanian"
    RUSSIAN = "Russian"
    SLOVAK = "Slovak"
    SPANISH = "Spanish"
    SWEDISH = "Swedish"
    TAGALOG = "Tagalog"
    THAI = "Thai"
    TURKISH = "Turkish"
    UKRAINIAN = "Ukrainian"
    VIETNAMESE = "Vietnamese"

# Request/Response models
class TranslationRequest(BaseModel):
    text: str = Field(..., description="Text to translate", max_length=50000)
    target_language: SupportedLanguage = Field(..., description="Target language for translation", example="Persian")
    is_json: bool = Field(False, description="Whether the text is JSON formatted")
    
    class Config:
        schema_extra = {
            "example": {
                "text": "Hello, how are you?",
                "target_language": "Persian",
                "is_json": False
            }
        }

class AsyncTranslationRequest(BaseModel):
    text: str = Field(..., description="Big text to translate")
    target_language: SupportedLanguage = Field(..., description="Target language for translation", example="Persian")
    is_json: bool = Field(False, description="Whether the text is JSON formatted")
    
    class Config:
        schema_extra = {
            "example": {
                "text": "This is a very long text that needs to be translated...",
                "target_language": "Persian",
                "is_json": False
            }
        }

class AsyncTranslationResponse(BaseModel):
    uuid: str = Field(..., description="Unique identifier for the translation")
    status: str = Field(..., description="Status of the translation")
    message: str = Field(..., description="Status message")
    estimated_completion_time: Optional[str] = Field(None, description="Estimated completion time")
    
    class Config:
        schema_extra = {
            "example": {
                "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "status": "processing",
                "message": "Translation has been queued and will be processed",
                "estimated_completion_time": "2024-01-01T12:00:30"
            }
        }

class BatchTranslationRequest(BaseModel):
    texts: List[str] = Field(..., description="List of texts to translate", example=["Hello", "Good morning"])
    target_language: SupportedLanguage = Field(..., description="Target language for translation", example="Persian")
    is_json: bool = Field(False, description="Whether the texts are JSON formatted")
    
    class Config:
        schema_extra = {
            "example": {
                "texts": ["Hello, how are you?", "Good morning", "Thank you"],
                "target_language": "Spanish",
                "is_json": False
            }
        }

class ConfigUpdate(BaseModel):
    config: Dict[str, Any]

class MemoryConfig(BaseModel):
    gpu_memory: str = Field(..., example="20GB")
    cpu_memory: str = Field(..., example="30GB")

class GlossaryUpdate(BaseModel):
    terms: Dict[str, str] = Field(..., example={"AI": "هوش مصنوعی", "Computer": "رایانه"})

class GenerationParams(BaseModel):
    max_new_tokens: Optional[int] = Field(None, ge=1, le=2048)
    temperature: Optional[float] = Field(None, ge=0.1, le=2.0)
    do_sample: Optional[bool] = None
    top_p: Optional[float] = Field(None, ge=0.1, le=1.0)
    top_k: Optional[int] = Field(None, ge=1, le=100)

# Model Manager Class with Enhanced Debugging
class ModelManager:
    def __init__(self, config_path: str = "/home/anews/NewsPic_G/translate_services/config.json"):
        logger.info("="*50)
        logger.info("Initializing ModelManager")
        logger.info("="*50)
        
        self.model = None
        self.tokenizer = None
        self.config = None
        self.config_path = config_path
        self.supported_languages = [lang.value for lang in SupportedLanguage]
        self.model_load_error = None
        self.max_input_tokens = 2048  # Support up to 2048 tokens
        self.max_batch_size = 5
        self.translation_stats = {
            "total_translations": 0,
            "successful_translations": 0,
            "failed_translations": 0,
            "last_error": None,
            "last_error_time": None,
            "crashes": []
        }
        
        # Load config first
        try:
            self.load_config()
            logger.info("Config loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load config: {e}", exc_info=True)
            self.config = self.get_default_config()
            self.save_config(self.config)
        
        # Try to load model
        logger.info("Attempting to load model during initialization...")
        success = self.load_model()
        if not success:
            logger.warning("Model failed to load during initialization. Service will run without model.")
        else:
            logger.info("Model loaded successfully during initialization")
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "model": {
                "model_id": "CohereForAI/aya-23-8B",
                "torch_dtype": "bfloat16",
                "device_map": "auto",
                "max_memory": {
                    "gpu": "20GB",
                    "cpu": "30GB"
                },
                "offload_folder": "offload",
                "offload_state_dict": True,
                "low_cpu_mem_usage": True
            },
            "translation": {
                "target_language": "Persian",
                "context": {
                    "domain": "general",
                    "style": "formal"
                },
                "generation_params": {
                    "max_new_tokens": 512,
                    "temperature": 0.7,
                    "do_sample": True,
                    "top_p": 0.9
                },
                "max_input_tokens": 2048,
                "max_batch_size": 5
            },
            "glossary": {}
        }
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            if os.path.exists(self.config_path):
                logger.info(f"Loading config from {self.config_path}")
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info("Config file loaded successfully")
            else:
                logger.warning(f"Config file not found at {self.config_path}, using defaults")
                self.config = self.get_default_config()
                self.save_config(self.config)
            
            # Ensure required fields exist
            if 'translation' not in self.config:
                self.config['translation'] = {}
            if 'target_language' not in self.config['translation']:
                self.config['translation']['target_language'] = 'Persian'
            if 'generation_params' not in self.config['translation']:
                self.config['translation']['generation_params'] = {
                    "max_new_tokens": 512,
                    "temperature": 0.7,
                    "do_sample": True,
                    "top_p": 0.9
                }
            
            # Update max tokens from config if available
            if 'max_input_tokens' in self.config['translation']:
                self.max_input_tokens = self.config['translation']['max_input_tokens']
            if 'max_batch_size' in self.config['translation']:
                self.max_batch_size = self.config['translation']['max_batch_size']
            
            logger.info(f"Configuration loaded. Max input tokens: {self.max_input_tokens}")
            return self.config
            
        except Exception as e:
            logger.error(f"Error loading config: {e}", exc_info=True)
            raise
    
    def save_config(self, new_config: Dict[str, Any]) -> bool:
        """Save new configuration to JSON file"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=2, ensure_ascii=False)
            self.config = new_config
            
            # Update runtime parameters
            if 'translation' in new_config:
                if 'max_input_tokens' in new_config['translation']:
                    self.max_input_tokens = new_config['translation']['max_input_tokens']
                if 'max_batch_size' in new_config['translation']:
                    self.max_batch_size = new_config['translation']['max_batch_size']
            
            logger.info("Configuration saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}", exc_info=True)
            return False
    
    def estimate_completion_time(self, text_length: int) -> datetime:
        """Estimate completion time based on text length"""
        # Rough estimate: ~100 chars per second
        estimated_seconds = max(5, text_length / 100)
        return datetime.now() + timedelta(seconds=estimated_seconds)
    
    def load_model(self) -> bool:
        """Load or reload the model with current configuration"""
        logger.info("="*50)
        logger.info("STARTING MODEL LOAD PROCESS")
        logger.info("="*50)
        
        try:
            # First, free any existing model
            if self.model is not None or self.tokenizer is not None:
                logger.info("Existing model detected, freeing memory first...")
                self.free_memory()
            
            model_config = self.config.get('model', {})
            
            # Validate model_id
            model_id = model_config.get('model_id', 'CohereForAI/aya-23-8B')
            logger.info(f"Model ID: {model_id}")
            
            # Convert string dtype to torch dtype
            dtype_map = {
                'bfloat16': torch.bfloat16,
                'float16': torch.float16,
                'float32': torch.float32
            }
            torch_dtype = dtype_map.get(model_config.get('torch_dtype', 'bfloat16'), torch.bfloat16)
            logger.info(f"Using dtype: {torch_dtype}")
            
            # Prepare max_memory dict
            max_memory = {}
            if 'max_memory' in model_config:
                if 'gpu' in model_config['max_memory']:
                    max_memory[0] = model_config['max_memory']['gpu']
                if 'cpu' in model_config['max_memory']:
                    max_memory['cpu'] = model_config['max_memory']['cpu']
            else:
                max_memory = {0: "20GB", "cpu": "30GB"}
            
            logger.info(f"Memory allocation - GPU: {max_memory.get(0, 'auto')}, CPU: {max_memory.get('cpu', 'auto')}")
            
            # Create offload folder if needed
            offload_folder = model_config.get('offload_folder', 'offload')
            if offload_folder and not os.path.isabs(offload_folder):
                offload_folder = os.path.join(os.path.dirname(self.config_path), offload_folder)
            os.makedirs(offload_folder, exist_ok=True)
            logger.info(f"Offload folder: {offload_folder}")
            
            # Load tokenizer first (less memory intensive)
            logger.info("Loading tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_id,
                trust_remote_code=True
            )
            
            # Set padding token if needed
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            logger.info("✓ Tokenizer loaded successfully")
            
            # Load model
            logger.info("Loading model weights (this may take a few minutes)...")
            self.model = AutoModelForCausalLM.from_pretrained(
                model_id,
                torch_dtype=torch_dtype,
                device_map=model_config.get('device_map', 'auto'),
                max_memory=max_memory,
                offload_folder=offload_folder,
                offload_state_dict=model_config.get('offload_state_dict', True),
                low_cpu_mem_usage=model_config.get('low_cpu_mem_usage', True),
                trust_remote_code=True
            )
            
            logger.info("✓ Model loaded successfully")
            self.model_load_error = None
            
            # Log memory usage after loading
            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated(0) / 1024**3
                reserved = torch.cuda.memory_reserved(0) / 1024**3
                total = torch.cuda.get_device_properties(0).total_memory / 1024**3
                logger.info(f"GPU Memory Status:")
                logger.info(f"  - Allocated: {allocated:.2f} GB")
                logger.info(f"  - Reserved: {reserved:.2f} GB")
                logger.info(f"  - Total: {total:.2f} GB")
                logger.info(f"  - Free: {total - allocated:.2f} GB")
            
            logger.info("="*50)
            logger.info("MODEL LOADING COMPLETE - SUCCESS")
            logger.info("="*50)
            return True
            
        except Exception as e:
            self.model_load_error = str(e)
            logger.error("="*50)
            logger.error("MODEL LOADING FAILED")
            logger.error("="*50)
            logger.error(f"Error: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            
            # Clean up partial loads
            if self.model is not None:
                del self.model
                self.model = None
            if self.tokenizer is not None:
                del self.tokenizer
                self.tokenizer = None
            
            # Try to free memory
            try:
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except:
                pass
            
            return False
    
    def check_memory_availability(self, estimated_tokens: int) -> tuple[bool, str]:
        """Check if there's enough memory for the translation"""
        try:
            details = []
            
            if torch.cuda.is_available():
                # Get current GPU memory
                allocated = torch.cuda.memory_allocated(0)
                reserved = torch.cuda.memory_reserved(0)
                total = torch.cuda.get_device_properties(0).total_memory
                available = total - allocated
                
                # Estimate memory needed (3MB per token for 8B model)
                bytes_per_token = 3 * 1024 * 1024
                estimated_memory_needed = estimated_tokens * bytes_per_token
                
                details.append(f"GPU - Available: {available/1024**3:.2f}GB, Needed: {estimated_memory_needed/1024**3:.2f}GB")
                
                if available < estimated_memory_needed * 1.2:  # 20% safety margin
                    return False, f"Insufficient GPU memory. {' '.join(details)}"
            
            # Check CPU memory
            vm = psutil.virtual_memory()
            details.append(f"RAM - Available: {vm.available/1024**3:.2f}GB")
            
            if vm.available < 2 * 1024 * 1024 * 1024:  # Less than 2GB available
                return False, f"Insufficient system memory. {' '.join(details)}"
            
            return True, f"Memory check passed. {' '.join(details)}"
        except Exception as e:
            logger.warning(f"Memory check failed: {e}")
            return True, "Memory check skipped due to error"
    
    def validate_input_length(self, text: str) -> tuple[bool, int, str]:
        """Validate input text length and return token count"""
        if not self.tokenizer:
            return False, 0, "Tokenizer not loaded"
        
        try:
            # Tokenize to get actual token count
            tokens = self.tokenizer.encode(text, add_special_tokens=True)
            token_count = len(tokens)
            
            if token_count > self.max_input_tokens:
                return False, token_count, f"Input too long: {token_count} tokens (max: {self.max_input_tokens})"
            
            return True, token_count, f"Input length valid: {token_count} tokens"
        except Exception as e:
            logger.error(f"Tokenization error: {e}", exc_info=True)
            return False, 0, f"Tokenization error: {str(e)}"
    
    def _emergency_memory_cleanup(self):
        """Emergency cleanup when OOM occurs"""
        logger.warning("EMERGENCY MEMORY CLEANUP INITIATED")
        try:
            # Clear CUDA cache
            if torch.cuda.is_available():
                before = torch.cuda.memory_allocated(0) / 1024**3
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                after = torch.cuda.memory_allocated(0) / 1024**3
                logger.info(f"GPU memory freed: {before:.2f}GB -> {after:.2f}GB")
            
            # Force garbage collection
            gc.collect()
            logger.info("Garbage collection completed")
        except Exception as e:
            logger.error(f"Emergency cleanup failed: {e}")
    
    def translate_with_safety(self, text: str, target_language: str = None, is_json: bool = False) -> Dict[str, Any]:
        """Translate with comprehensive error handling and safety checks"""
        request_id = str(uuid.uuid4())[:8]
        logger.info(f"[TRANSLATE_START] Request ID: {request_id}, Text length: {len(text)} chars")
        
        result = {
            "success": False,
            "translation": None,
            "error": None,
            "error_type": None,
            "details": {
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        request_tracker.start_request(request_id, len(text))
        self.translation_stats["total_translations"] += 1
        
        try:
            # Check if model is loaded
            if self.model is None or self.tokenizer is None:
                logger.error(f"[{request_id}] Model not loaded")
                raise ModelNotLoadedError(f"Model not loaded. Error: {self.model_load_error or 'Unknown error'}")
            
            # Validate input length
            logger.debug(f"[{request_id}] Validating input length...")
            valid, token_count, message = self.validate_input_length(text)
            result["details"]["input_tokens"] = token_count
            result["details"]["validation_message"] = message
            
            if not valid:
                logger.error(f"[{request_id}] {message}")
                raise TokenLimitError(message)
            
            logger.info(f"[{request_id}] Input validated: {token_count} tokens")
            
            # Check memory availability
            logger.debug(f"[{request_id}] Checking memory availability...")
            memory_ok, memory_message = self.check_memory_availability(token_count * 2)
            result["details"]["memory_check"] = memory_message
            
            if not memory_ok:
                logger.error(f"[{request_id}] Memory check failed: {memory_message}")
                raise ModelMemoryError(memory_message)
            
            # Log current memory state
            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated(0) / 1024**3
                logger.debug(f"[{request_id}] GPU memory before translation: {allocated:.2f}GB")
                result["details"]["gpu_memory_before"] = {"allocated_gb": allocated}
            
            # Perform translation
            logger.info(f"[{request_id}] Starting translation...")
            start_time = time.time()
            
            translation = self._translate_internal(text, target_language, is_json)
            
            elapsed = time.time() - start_time
            logger.info(f"[{request_id}] Translation completed in {elapsed:.2f}s")
            
            # Log memory after translation
            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated(0) / 1024**3
                logger.debug(f"[{request_id}] GPU memory after translation: {allocated:.2f}GB")
                result["details"]["gpu_memory_after"] = {"allocated_gb": allocated}
            
            result["success"] = True
            result["translation"] = translation
            result["details"]["elapsed_time"] = elapsed
            self.translation_stats["successful_translations"] += 1
            
            request_tracker.end_request(request_id, "success")
            logger.info(f"[{request_id}] Translation successful")
            
            return result
            
        except ModelNotLoadedError as e:
            result["error"] = str(e)
            result["error_type"] = "MODEL_NOT_LOADED"
            logger.error(f"[{request_id}] Model not loaded: {e}")
            
        except TokenLimitError as e:
            result["error"] = str(e)
            result["error_type"] = "TOKEN_LIMIT_EXCEEDED"
            logger.error(f"[{request_id}] Token limit exceeded: {e}")
            
        except ModelMemoryError as e:
            result["error"] = str(e)
            result["error_type"] = "MEMORY_ERROR"
            logger.error(f"[{request_id}] Memory error: {e}")
            
        except torch.cuda.OutOfMemoryError as e:
            result["error"] = f"GPU out of memory: {str(e)}"
            result["error_type"] = "GPU_OOM"
            logger.critical(f"[{request_id}] GPU OOM: {e}")
            self._emergency_memory_cleanup()
            
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                result["error"] = f"Out of memory: {str(e)}"
                result["error_type"] = "OOM"
                logger.critical(f"[{request_id}] OOM Error: {e}")
                self._emergency_memory_cleanup()
            else:
                result["error"] = f"Runtime error: {str(e)}"
                result["error_type"] = "RUNTIME_ERROR"
                logger.error(f"[{request_id}] Runtime error: {e}")
                
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            result["error_type"] = "UNKNOWN_ERROR"
            logger.error(f"[{request_id}] Unexpected error: {e}")
            logger.error(f"[{request_id}] Traceback:\n{traceback.format_exc()}")
        
        # Update error stats
        if not result["success"]:
            self.translation_stats["failed_translations"] += 1
            self.translation_stats["last_error"] = result["error"]
            self.translation_stats["last_error_time"] = datetime.now().isoformat()
            
            # Record crash details
            crash_info = {
                "timestamp": datetime.now().isoformat(),
                "request_id": request_id,
                "error_type": result["error_type"],
                "error_message": result["error"],
                "text_length": len(text)
            }
            self.translation_stats["crashes"].append(crash_info)
            
            # Keep only last 10 crashes
            if len(self.translation_stats["crashes"]) > 10:
                self.translation_stats["crashes"] = self.translation_stats["crashes"][-10:]
            
            request_tracker.end_request(request_id, "failed", result["error"])
        
        return result
    
    def _translate_internal(self, text: str, target_language: str = None, is_json: bool = False) -> str:
        """Internal translation method with memory-efficient processing"""
        logger.debug("Starting internal translation")
        
        # Validate target language
        if target_language and target_language not in self.supported_languages:
            raise ValueError(f"Unsupported language: {target_language}")
        
        # Use provided target language or default from config
        target_lang = target_language or self.config['translation'].get('target_language', 'Persian')
        logger.debug(f"Target language: {target_lang}")
        
        # Build system prompt
        trans_config = self.config['translation']
        system = [f"Translate the user's text to {target_lang}."]
        
        # Add context if exists
        if 'context' in trans_config:
            for key, value in trans_config['context'].items():
                key_pascal = key.capitalize()
                system.append(f"{key_pascal}: {value}")
        
        # Add glossary if exists and target language matches
        if target_lang == self.config['translation'].get('target_language') and 'glossary' in self.config and self.config['glossary']:
            system.append("Glossary:")
            for term, translation in self.config['glossary'].items():
                system.append(f"- {term} -> {translation}")
        
        system.append("Provide the final translation immediately without any other text.")
        
        # Prepare messages
        messages = [
            {"role": "system", "content": "\n".join(system)},
            {"role": "user", "content": text},
        ]
        
        # Create prompt
        logger.debug("Creating prompt...")
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        # Tokenize with explicit truncation
        logger.debug("Tokenizing input...")
        inputs = self.tokenizer(
            prompt, 
            return_tensors="pt",
            max_length=self.max_input_tokens,
            truncation=True
        )
        
        # Move to appropriate device
        if torch.cuda.is_available():
            inputs = inputs.to("cuda")
        
        input_length = inputs["input_ids"].shape[1]
        logger.debug(f"Input tokenized: {input_length} tokens")
        
        # Generate with parameters from config
        gen_params = trans_config.get('generation_params', {})
        
        # Calculate adaptive max_new_tokens
        remaining_context = self.max_input_tokens - input_length
        adaptive_max_tokens = min(
            gen_params.get('max_new_tokens', 512),
            max(128, remaining_context)
        )
        
        logger.debug(f"Generating with max_new_tokens={adaptive_max_tokens}")
        
        # Generate translation
        with torch.inference_mode():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=adaptive_max_tokens,
                temperature=gen_params.get('temperature', 0.7),
                do_sample=gen_params.get('do_sample', True),
                top_p=gen_params.get('top_p', 0.9),
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )
        
        # Decode
        generated_tokens = outputs[0][input_length:]
        translation = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
        
        logger.debug(f"Generated {len(generated_tokens)} tokens")
        
        # Clear outputs from memory immediately
        del outputs
        del inputs
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        # Try to parse as JSON if requested
        if is_json:
            try:
                return json.loads(translation)
            except json.JSONDecodeError:
                return translation
        
        return translation
    
    def translate(self, text: str, target_language: str = None, is_json: bool = False) -> str:
        """Public translate method with safety wrapper"""
        result = self.translate_with_safety(text, target_language, is_json)
        
        if result["success"]:
            return result["translation"]
        else:
            # Raise appropriate exception based on error type
            error_msg = f"{result['error_type']}: {result['error']}"
            if result.get("details"):
                error_msg += f"\nDetails: {json.dumps(result['details'], indent=2)}"
            raise RuntimeError(error_msg)
    
    def free_memory(self) -> Dict[str, Any]:
        """Completely free GPU memory"""
        logger.info("Freeing GPU memory...")
        result = {"status": "started", "steps": []}
        
        try:
            # Delete model
            if self.model is not None:
                del self.model
                self.model = None
                result["steps"].append("Model deleted")
            
            # Delete tokenizer
            if self.tokenizer is not None:
                del self.tokenizer
                self.tokenizer = None
                result["steps"].append("Tokenizer deleted")
            
            # Run garbage collection
            gc.collect()
            result["steps"].append("Garbage collection completed")
            
            # Clear CUDA cache
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                result["steps"].append("CUDA cache cleared")
                
                # Get memory stats after clearing
                result["gpu_memory_after"] = {
                    "allocated_gb": torch.cuda.memory_allocated(0) / 1024**3,
                    "reserved_gb": torch.cuda.memory_reserved(0) / 1024**3
                }
            
            result["status"] = "completed"
            logger.info("GPU memory freed successfully")
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            logger.error(f"Error freeing GPU memory: {e}")
        
        return result
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current GPU/CPU memory usage"""
        memory_info = {
            "is_model_loaded": self.model is not None,
            "is_tokenizer_loaded": self.tokenizer is not None,
            "supported_languages": self.supported_languages,
            "model_load_error": self.model_load_error,
            "max_input_tokens": self.max_input_tokens,
            "max_batch_size": self.max_batch_size,
            "translation_stats": self.translation_stats,
            "active_requests": request_tracker.get_active(),
            "recent_requests": request_tracker.get_history()[-10:]
        }
        
        if torch.cuda.is_available():
            memory_info['gpu_allocated_gb'] = torch.cuda.memory_allocated(0) / 1024**3
            memory_info['gpu_reserved_gb'] = torch.cuda.memory_reserved(0) / 1024**3
            memory_info['gpu_total_gb'] = torch.cuda.get_device_properties(0).total_memory / 1024**3
            memory_info['gpu_free_gb'] = memory_info['gpu_total_gb'] - memory_info['gpu_allocated_gb']
        
        # Add CPU memory info
        try:
            process = psutil.Process()
            vm = psutil.virtual_memory()
            memory_info['cpu_memory_gb'] = process.memory_info().rss / 1024**3
            memory_info['cpu_percent'] = process.memory_percent()
            memory_info['system_memory_available_gb'] = vm.available / 1024**3
            memory_info['system_memory_percent'] = vm.percent
        except Exception:
            pass
        
        return memory_info

# Initialize model manager globally
model_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global model_manager
    logger.info("="*50)
    logger.info("STARTING FASTAPI TRANSLATION SERVICE")
    logger.info("="*50)
    
    try:
        model_manager = ModelManager()
        
        # Check if model loaded successfully
        if model_manager.model is None:
            logger.warning("⚠ Model Service started but model is not loaded. Use /reload endpoint to retry loading.")
        else:
            logger.info("✓ Model Service started successfully with model loaded")
    except Exception as e:
        logger.error(f"Failed to initialize ModelManager: {e}", exc_info=True)
        model_manager = None
    
    yield
    
    # Shutdown
    logger.info("="*50)
    logger.info("SHUTTING DOWN FASTAPI TRANSLATION SERVICE")
    logger.info("="*50)
    if model_manager:
        model_manager.free_memory()
    logger.info("Service shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="Translation Model Service",
    version="2.1.0",
    description="Enhanced translation service with comprehensive error handling and debugging",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log request
    logger.info(f"[HTTP] {request.method} {request.url.path} from {request.client.host}")
    
    try:
        response = await call_next(request)
        elapsed = time.time() - start_time
        logger.info(f"[HTTP] {request.url.path} - Status: {response.status_code} - Time: {elapsed:.3f}s")
        return response
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[HTTP] {request.url.path} - Error: {e} - Time: {elapsed:.3f}s", exc_info=True)
        raise

# Helper function for error suggestions
def get_error_suggestion(error_type: str) -> str:
    """Provide suggestions based on error type"""
    suggestions = {
        "TOKEN_LIMIT_EXCEEDED": "Please reduce the input text length or split it into smaller chunks (max 2048 tokens).",
        "MEMORY_ERROR": "The server is low on memory. Try again later or reduce input size.",
        "GPU_OOM": "GPU memory exhausted. Please try with shorter text or contact admin.",
        "MODEL_NOT_LOADED": "Use the /reload endpoint to load the model.",
        "OOM": "System out of memory. Please try again with smaller input.",
        "RUNTIME_ERROR": "An unexpected runtime error occurred. Please try again or contact support.",
        "UNKNOWN_ERROR": "An unexpected error occurred. Please contact support."
    }
    return suggestions.get(error_type, "Please try again or contact support.")

# API Endpoints
@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Translation Model Service",
        "version": "2.1.0",
        "status": "running",
        "model_loaded": model_manager.model is not None if model_manager else False,
        "max_input_tokens": model_manager.max_input_tokens if model_manager else 2048,
        "debug_log": "/home/anews/NewsPic_G/translate_services/fastapi_debug.log",
        "endpoints": {
            "health": "/health",
            "translate": "/translate",
            "translate_async": "/translate/async",
            "get_async_translation": "/translate/async/{uuid}",
            "batch": "/translate/batch",
            "languages": "/languages",
            "memory": "/memory",
            "stats": "/stats",
            "crashes": "/debug/crashes",
            "requests": "/debug/requests"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    global model_manager
    
    if not model_manager:
        return {
            "status": "unhealthy",
            "model_loaded": False,
            "error": "Model manager not initialized",
            "return": False
        }
    
    return {
        "status": "healthy" if model_manager.model is not None else "degraded",
        "model_loaded": model_manager.model is not None,
        "model_load_error": model_manager.model_load_error,
        "supported_languages": model_manager.supported_languages,
        "max_input_tokens": model_manager.max_input_tokens,
        "stats": model_manager.translation_stats,
        "active_requests": request_tracker.get_active(),
        "async_storage_stats": async_storage.get_stats(),
        "return": model_manager.model is not None
    }

@app.get("/languages")
async def get_supported_languages():
    """Get list of supported languages"""
    return {
        "languages": [lang.value for lang in SupportedLanguage],
        "count": len(SupportedLanguage),
        "return": True
    }

@app.post("/translate")
async def translate(request: TranslationRequest):
    """Translate single text with detailed error reporting"""
    logger.info(f"[TRANSLATE_ENDPOINT] Received request for {len(request.text)} chars to {request.target_language.value}")
    
    if not model_manager:
        logger.error("Model manager not initialized")
        raise HTTPException(status_code=503, detail={"error": "Model service not initialized", "return": False})
    
    try:
        # Use the safe translation method
        result = model_manager.translate_with_safety(
            request.text, 
            request.target_language.value,
            request.is_json
        )
        
        if result["success"]:
            return {
                "translation": result["translation"],
                "original": request.text,
                "target_language": request.target_language.value,
                "details": result.get("details", {}),
                "return": True
            }
        else:
            # Return detailed error information
            logger.error(f"Translation failed: {result['error_type']}: {result['error']}")
            raise HTTPException(
                status_code=400 if result["error_type"] in ["TOKEN_LIMIT_EXCEEDED", "VALIDATION_ERROR"] else 503,
                detail={
                    "error": result["error"],
                    "error_type": result["error_type"],
                    "details": result.get("details", {}),
                    "suggestion": get_error_suggestion(result["error_type"]),
                    "return": False
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in translate endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "error_type": "UNEXPECTED_ERROR",
                "suggestion": "Please try again or contact support",
                "return": False
            }
        )

@app.post("/translate/async", response_model=AsyncTranslationResponse)
async def translate_async(request: AsyncTranslationRequest, background_tasks: BackgroundTasks):
    """Submit a big text for translation and get a UUID to retrieve it later"""
    logger.info(f"[TRANSLATE_ASYNC] Received async request for {len(request.text)} chars to {request.target_language.value}")
    
    if not model_manager:
        logger.error("Model manager not initialized")
        raise HTTPException(status_code=503, detail={"error": "Model service not initialized", "return": False})
    
    # Generate unique ID for this translation
    translation_id = str(uuid.uuid4())
    
    # Estimate completion time
    estimated_completion = model_manager.estimate_completion_time(len(request.text))
    
    # Function to perform translation in background
    def perform_translation_background(trans_id: str, text: str, target_lang: str, is_json: bool):
        """Background task to perform translation"""
        try:
            logger.info(f"[BACKGROUND] Starting translation for {trans_id}")
            
            # Save initial processing status
            async_storage.save_translation(
                translation_id=trans_id,
                text=text,
                translation=None,
                target_language=target_lang,
                metadata={
                    "is_json": is_json,
                    "text_length": len(text),
                    "status": "processing",
                    "started_at": datetime.now().isoformat(),
                    "estimated_completion": estimated_completion.isoformat()
                }
            )
            
            # Perform the translation
            result = model_manager.translate_with_safety(
                text,
                target_lang,
                is_json
            )
            
            if result["success"]:
                # Save successful translation
                async_storage.save_translation(
                    translation_id=trans_id,
                    text=text,
                    translation=result["translation"],
                    target_language=target_lang,
                    metadata={
                        "is_json": is_json,
                        "text_length": len(text),
                        "translation_details": result.get("details", {}),
                        "status": "completed",
                        "completed_at": datetime.now().isoformat()
                    }
                )
                logger.info(f"[BACKGROUND] Translation {trans_id} completed successfully")
            else:
                # Save error information
                async_storage.save_translation(
                    translation_id=trans_id,
                    text=text,
                    translation=None,
                    target_language=target_lang,
                    metadata={
                        "is_json": is_json,
                        "error": result["error"],
                        "error_type": result["error_type"],
                        "details": result.get("details", {}),
                        "status": "failed",
                        "failed_at": datetime.now().isoformat()
                    }
                )
                logger.error(f"[BACKGROUND] Translation {trans_id} failed: {result['error']}")
                
        except Exception as e:
            logger.error(f"[BACKGROUND] Translation {trans_id} error: {e}")
            # Save error state
            try:
                async_storage.save_translation(
                    translation_id=trans_id,
                    text=text,
                    translation=None,
                    target_language=target_lang,
                    metadata={
                        "is_json": is_json,
                        "error": str(e),
                        "error_type": "UNEXPECTED_ERROR",
                        "status": "failed",
                        "failed_at": datetime.now().isoformat()
                    }
                )
            except:
                pass
    
    # Add translation task to background
    background_tasks.add_task(
        perform_translation_background,
        translation_id,
        request.text,
        request.target_language.value,
        request.is_json
    )
    
    # Return UUID immediately with estimated completion time
    logger.info(f"[TRANSLATE_ASYNC] Returning UUID {translation_id} immediately")
    return AsyncTranslationResponse(
        uuid=translation_id,
        status="processing",
        message="Translation request received and is being processed",
        estimated_completion_time=estimated_completion.isoformat()
    )

@app.get("/translate/async/{uuid}")
async def get_async_translation(uuid: str):
    """Retrieve a previously translated text using its UUID"""
    logger.info(f"[GET_ASYNC_TRANSLATION] Retrieving translation {uuid}")
    
    # Retrieve the translation
    translation_data = async_storage.get_translation(uuid)
    
    if translation_data is None:
        logger.warning(f"[GET_ASYNC_TRANSLATION] Translation {uuid} not found")
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Translation with UUID {uuid} not found",
                "return": False
            }
        )
    
    # Get status from metadata
    metadata = translation_data.get("metadata", {})
    status = metadata.get("status", "unknown")
    
    # Check if translation is still processing
    if status == "processing":
        return {
            "uuid": uuid,
            "status": "processing",
            "original_text": translation_data.get("original_text"),
            "translation": None,
            "target_language": translation_data.get("target_language"),
            "timestamp": translation_data.get("timestamp"),
            "estimated_completion": metadata.get("estimated_completion"),
            "metadata": metadata,
            "return": True
        }
    
    # Check if translation was successful
    if status == "completed" and translation_data.get("translation") is not None:
        return {
            "uuid": uuid,
            "status": "completed",
            "original_text": translation_data.get("original_text"),
            "translation": translation_data.get("translation"),
            "target_language": translation_data.get("target_language"),
            "timestamp": translation_data.get("timestamp"),
            "metadata": metadata,
            "return": True
        }
    else:
        # Translation failed
        return {
            "uuid": uuid,
            "status": "failed",
            "original_text": translation_data.get("original_text"),
            "translation": None,
            "target_language": translation_data.get("target_language"),
            "timestamp": translation_data.get("timestamp"),
            "error": metadata.get("error", "Unknown error"),
            "error_type": metadata.get("error_type", "UNKNOWN_ERROR"),
            "metadata": metadata,
            "return": False
        }

@app.delete("/translate/async/{uuid}")
async def delete_async_translation(uuid: str):
    """Delete a stored translation by UUID"""
    logger.info(f"[DELETE_ASYNC_TRANSLATION] Deleting translation {uuid}")
    
    deleted = async_storage.delete_translation(uuid)
    
    if deleted:
        return {
            "message": f"Translation {uuid} deleted successfully",
            "uuid": uuid,
            "return": True
        }
    else:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Translation with UUID {uuid} not found",
                "return": False
            }
        )

@app.get("/translate/async")
async def list_async_translations():
    """List all stored translation UUIDs"""
    translation_ids = async_storage.get_all_ids()
    stats = async_storage.get_stats()
    
    return {
        "translation_ids": translation_ids,
        "count": len(translation_ids),
        "stats": stats,
        "return": True
    }

@app.post("/translate/batch")
async def translate_batch(request: BatchTranslationRequest):
    """Translate multiple texts with safety limits"""
    if not model_manager:
        raise HTTPException(status_code=503, detail={"error": "Model service not initialized", "return": False})
    
    # Limit batch size
    if len(request.texts) > model_manager.max_batch_size:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"Batch size too large. Maximum: {model_manager.max_batch_size} texts",
                "return": False
            }
        )
    
    translations = []
    errors = []
    
    for idx, text in enumerate(request.texts):
        result = model_manager.translate_with_safety(
            text,
            request.target_language.value,
            request.is_json
        )
        
        if result["success"]:
            translations.append({
                "index": idx,
                "original": text,
                "translation": result["translation"],
                "success": True
            })
        else:
            translations.append({
                "index": idx,
                "original": text,
                "translation": None,
                "success": False,
                "error": result["error"],
                "error_type": result["error_type"]
            })
            errors.append(idx)
    
    return {
        "translations": translations,
        "target_language": request.target_language.value,
        "total": len(request.texts),
        "successful": len(request.texts) - len(errors),
        "failed_indices": errors,
        "return": len(errors) == 0
    }

@app.get("/stats")
async def get_stats():
    """Get translation statistics"""
    if not model_manager:
        raise HTTPException(status_code=503, detail={"error": "Model service not initialized", "return": False})
    
    return {
        "statistics": model_manager.translation_stats,
        "memory": model_manager.get_memory_usage(),
        "async_storage": async_storage.get_stats(),
        "return": True
    }

@app.get("/debug/crashes")
async def get_crashes():
    """Get recent crash information for debugging"""
    if not model_manager:
        return {"crashes": [], "return": False}
    return {
        "crashes": model_manager.translation_stats.get("crashes", []),
        "return": True
    }

@app.get("/debug/requests")
async def get_request_history():
    """Get request history for debugging"""
    return {
        "active": request_tracker.get_active(),
        "history": request_tracker.get_history(),
        "return": True
    }

@app.get("/config")
async def get_config():
    """Get current configuration"""
    if not model_manager:
        raise HTTPException(status_code=503, detail={"error": "Model service not initialized", "return": False})
    return {
        **model_manager.config,
        "return": True
    }

@app.put("/config")
async def update_config(request: ConfigUpdate):
    """Update entire configuration"""
    if not model_manager:
        raise HTTPException(status_code=503, detail={"error": "Model service not initialized", "return": False})
    
    try:
        if model_manager.save_config(request.config):
            if model_manager.load_model():
                return {
                    "message": "Configuration updated and model reloaded successfully",
                    "config": request.config,
                    "return": True
                }
            else:
                return {
                    "message": "Configuration saved but model reload failed",
                    "config": request.config,
                    "model_error": model_manager.model_load_error,
                    "return": False
                }
        else:
            raise HTTPException(status_code=500, detail={"error": "Failed to save configuration", "return": False})
    except Exception as e:
        logger.error(f"Config update error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": str(e), "return": False})

@app.patch("/config/memory")
async def update_memory_config(request: MemoryConfig):
    """Update memory configuration"""
    if not model_manager:
        raise HTTPException(status_code=503, detail={"error": "Model service not initialized", "return": False})
    
    try:
        model_manager.config['model']['max_memory'] = {
            'gpu': request.gpu_memory,
            'cpu': request.cpu_memory
        }
        
        if model_manager.save_config(model_manager.config):
            if model_manager.load_model():
                return {
                    "message": "Memory configuration updated successfully",
                    "gpu_memory": request.gpu_memory,
                    "cpu_memory": request.cpu_memory,
                    "return": True
                }
            else:
                return {
                    "message": "Configuration saved but model reload failed",
                    "gpu_memory": request.gpu_memory,
                    "cpu_memory": request.cpu_memory,
                    "model_error": model_manager.model_load_error,
                    "return": False
                }
    except Exception as e:
        logger.error(f"Memory config update error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": str(e), "return": False})

@app.patch("/config/glossary")
async def update_glossary(request: GlossaryUpdate):
    """Update glossary"""
    if not model_manager:
        raise HTTPException(status_code=503, detail={"error": "Model service not initialized", "return": False})
    
    try:
        model_manager.config['glossary'] = request.terms
        
        if model_manager.save_config(model_manager.config):
            return {
                "message": "Glossary updated successfully",
                "glossary": request.terms,
                "return": True
            }
    except Exception as e:
        logger.error(f"Glossary update error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": str(e), "return": False})

@app.delete("/config/glossary")
async def delete_glossary():
    """Delete glossary"""
    if not model_manager:
        raise HTTPException(status_code=503, detail={"error": "Model service not initialized", "return": False})
    
    try:
        model_manager.config['glossary'] = {}
        
        if model_manager.save_config(model_manager.config):
            return {"message": "Glossary deleted successfully", "return": True}
    except Exception as e:
        logger.error(f"Delete glossary error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": str(e), "return": False})

@app.patch("/config/generation")
async def update_generation_params(request: GenerationParams):
    """Update generation parameters"""
    if not model_manager:
        raise HTTPException(status_code=503, detail={"error": "Model service not initialized", "return": False})
    
    try:
        # Update only provided parameters
        params_dict = request.dict(exclude_none=True)
        model_manager.config['translation']['generation_params'].update(params_dict)
        
        if model_manager.save_config(model_manager.config):
            return {
                "message": "Generation parameters updated successfully",
                "params": params_dict,
                "return": True
            }
    except Exception as e:
        logger.error(f"Generation params update error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": str(e), "return": False})

@app.get("/memory")
async def get_memory_usage():
    """Get memory usage statistics"""
    if not model_manager:
        raise HTTPException(status_code=503, detail={"error": "Model service not initialized", "return": False})
    return {
        **model_manager.get_memory_usage(),
        "return": True
    }

@app.post("/reload")
async def reload_model():
    """Reload the model"""
    if not model_manager:
        raise HTTPException(status_code=503, detail={"error": "Model service not initialized", "return": False})
    
    logger.info("Model reload requested via API")
    
    try:
        if model_manager.load_model():
            return {
                "message": "Model reloaded successfully",
                "memory": model_manager.get_memory_usage(),
                "return": True
            }
        else:
            raise HTTPException(
                status_code=500, 
                detail={
                    "error": f"Model reload failed. Error: {model_manager.model_load_error or 'Unknown error'}",
                    "return": False
                }
            )
    except Exception as e:
        logger.error(f"Model reload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": str(e), "return": False})

@app.post("/free_memory")
async def free_gpu_memory():
    """Free GPU memory"""
    if not model_manager:
        raise HTTPException(status_code=503, detail={"error": "Model service not initialized", "return": False})
    
    try:
        result = model_manager.free_memory()
        return {
            **result,
            "return": result.get("status") == "completed"
        }
    except Exception as e:
        logger.error(f"Free memory error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": str(e), "return": False})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, workers=1)