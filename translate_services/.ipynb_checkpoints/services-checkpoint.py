"""
Enhanced Model Service with Queue System for Sequential Processing
Run with: CUDA_LAUNCH_BLOCKING=1 uvicorn model_service:app --host 0.0.0.0 --port 8001 --workers 1
"""
import os
# Disable PyTorch CUDA graphs to prevent threading issues
os.environ['PYTORCH_DISABLE_CUDA_GRAPHS'] = '1'
os.environ['TORCH_CUDNN_V8_API_DISABLED'] = '1'
os.environ['TORCH_COMPILE_DISABLE'] = '1'
os.environ['TORCHINDUCTOR_DISABLE'] = '1'

import json
import torch
import gc
import os
import traceback
import psutil
import asyncio
import time
import subprocess
import threading
from queue import Queue, Empty
from typing import Dict, Any, List, Optional, Union
from fastapi import FastAPI, HTTPException, Request, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, ConfigDict
from transformers import AutoTokenizer, AutoModelForCausalLM
import logging
from contextlib import asynccontextmanager
from enum import Enum
from datetime import datetime, timedelta
import uuid
from collections import deque
from pathlib import Path
import signal
import sys
import hashlib
from threading import RLock, Thread, Event

# Set CUDA environment variables for better debugging
os.environ['CUDA_LAUNCH_BLOCKING'] = '1'  # Synchronous CUDA operations
os.environ['TORCH_USE_CUDA_DSA'] = '1'    # Enable device-side assertions
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:512'  # Prevent memory fragmentation

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

# Translation Queue Manager with Cache
class TranslationQueueManager:
    def __init__(self, cache_path: str = "/home/anews/NewsPic_G/translate_services/translation_cache.json"):
        self.cache_path = cache_path
        self.processing_lock = RLock()  # Reentrant lock for sequential processing
        self.cache_lock = RLock()  # Separate lock for cache operations
        self.request_queue = deque()  # Queue for pending requests
        self.currently_processing = None
        self.processing_event = Event()
        self._ensure_cache_file()
        
    def _ensure_cache_file(self):
        """Ensure the cache storage file exists"""
        if not os.path.exists(self.cache_path):
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump({"cache": {}, "stats": {"hits": 0, "misses": 0}}, f)
            logger.info(f"Created cache storage file: {self.cache_path}")
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load the cache file"""
        try:
            with self.cache_lock:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "cache" not in data:
                        data["cache"] = {}
                    if "stats" not in data:
                        data["stats"] = {"hits": 0, "misses": 0}
                    return data
        except Exception as e:
            logger.error(f"Error loading cache file: {e}")
            return {"cache": {}, "stats": {"hits": 0, "misses": 0}}
    
    def _save_cache(self, data: Dict[str, Any]):
        """Save the cache file"""
        try:
            with self.cache_lock:
                with open(self.cache_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache file: {e}")
    
    def _get_cache_key(self, text: str, target_languages: List[str], is_json: bool) -> str:
        """Generate a cache key for translation request"""
        content = f"{text}|{'|'.join(sorted(target_languages))}|{is_json}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def check_cache(self, text: str, target_languages: List[str], is_json: bool) -> Optional[Dict[str, Any]]:
        """Check if translation exists in cache"""
        cache_key = self._get_cache_key(text, target_languages, is_json)
        cache_data = self._load_cache()
        
        if cache_key in cache_data.get("cache", {}):
            cached = cache_data["cache"][cache_key]
            # Check if cache is not too old (24 hours)
            if "timestamp" in cached:
                cached_time = datetime.fromisoformat(cached["timestamp"])
                if datetime.now() - cached_time < timedelta(hours=24):
                    cache_data["stats"]["hits"] += 1
                    self._save_cache(cache_data)
                    logger.info(f"Cache hit for key: {cache_key[:8]}...")
                    return cached.get("result")
        
        cache_data["stats"]["misses"] += 1
        self._save_cache(cache_data)
        return None
    
    def save_to_cache(self, text: str, target_languages: List[str], is_json: bool, result: Dict[str, Any]):
        """Save translation result to cache"""
        cache_key = self._get_cache_key(text, target_languages, is_json)
        cache_data = self._load_cache()
        
        # Limit cache size to 1000 entries
        if len(cache_data.get("cache", {})) > 1000:
            # Remove oldest entries
            cache_items = sorted(
                cache_data["cache"].items(),
                key=lambda x: x[1].get("timestamp", ""),
                reverse=True
            )
            cache_data["cache"] = dict(cache_items[:900])
        
        cache_data["cache"][cache_key] = {
            "result": result,
            "timestamp": datetime.now().isoformat(),
            "text_length": len(text),
            "languages": target_languages
        }
        
        self._save_cache(cache_data)
        logger.info(f"Saved to cache with key: {cache_key[:8]}...")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        cache_data = self._load_cache()
        return {
            "total_cached": len(cache_data.get("cache", {})),
            "cache_hits": cache_data.get("stats", {}).get("hits", 0),
            "cache_misses": cache_data.get("stats", {}).get("misses", 0),
            "hit_rate": cache_data.get("stats", {}).get("hits", 0) / 
                       max(1, cache_data.get("stats", {}).get("hits", 0) + cache_data.get("stats", {}).get("misses", 0))
        }
    
    def clear_cache(self):
        """Clear the cache"""
        with self.cache_lock:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump({"cache": {}, "stats": {"hits": 0, "misses": 0}}, f)
        logger.info("Cache cleared")

# Initialize queue manager
translation_queue_manager = TranslationQueueManager()

# Request tracking for debugging
class RequestTracker:
    def __init__(self, max_size=100):
        self.requests = deque(maxlen=max_size)
        self.active_requests = {}
        self.lock = threading.Lock()
        
    def start_request(self, request_id: str, text_length: int):
        with self.lock:
            self.active_requests[request_id] = {
                "id": request_id,
                "start_time": datetime.now().isoformat(),
                "text_length": text_length,
                "status": "processing"
            }
        logger.info(f"[REQUEST_START] ID: {request_id}, Text length: {text_length}")
        
    def end_request(self, request_id: str, status: str, error: str = None):
        with self.lock:
            if request_id in self.active_requests:
                req = self.active_requests.pop(request_id)
                req["end_time"] = datetime.now().isoformat()
                req["status"] = status
                req["error"] = error
                self.requests.append(req)
        logger.info(f"[REQUEST_END] ID: {request_id}, Status: {status}, Error: {error}")
            
    def get_active(self):
        with self.lock:
            return list(self.active_requests.values())
    
    def get_history(self):
        with self.lock:
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
            sorted_items = sorted(
                storage.items(),
                key=lambda x: x[1].get('timestamp', ''),
                reverse=True
            )
            storage = dict(sorted_items[:self.max_translations - 1])
            logger.info(f"Cleaned up old translations, kept {len(storage)} newest entries")
        return storage
    
    def save_translation(self, translation_id: str, text: Union[str, List[str]], translations: Dict[str, Any], 
                        target_languages: List[str], metadata: Dict[str, Any] = None) -> bool:
        """Save a translation with UUID"""
        with self.lock:
            try:
                storage = self._load_storage()
                storage = self._cleanup_old_translations(storage)
                
                storage[translation_id] = {
                    "id": translation_id,
                    "original_text": text,
                    "translations": translations,
                    "target_languages": target_languages,
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

class CudaError(Exception):
    """Raised when CUDA operations fail"""
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

# Standard Response Model
class StandardResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    return_: bool = Field(..., alias="return", description="Success status")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data when successful")
    message: Optional[str] = Field(None, description="Generic message")
    errors: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Detailed errors list")

# Request/Response models
class TranslationRequest(BaseModel):
    text: str = Field(..., description="Text to translate", max_length=50000)
    target_languages: List[SupportedLanguage] = Field(..., description="Target languages for translation", examples=[["Persian", "Spanish"]])
    is_json: bool = Field(False, description="Whether the text is JSON formatted")
    
    @field_validator('target_languages')
    @classmethod
    def validate_languages(cls, v):
        if not v:
            raise ValueError("At least one target language must be specified")
        return v

class AsyncTranslationRequest(BaseModel):
    text: str = Field(..., description="Big text to translate")
    target_languages: List[SupportedLanguage] = Field(..., description="Target languages for translation")
    is_json: bool = Field(False, description="Whether the text is JSON formatted")
    
    @field_validator('target_languages')
    @classmethod
    def validate_languages(cls, v):
        if not v:
            raise ValueError("At least one target language must be specified")
        return v

class BatchTranslationRequest(BaseModel):
    texts: List[str] = Field(..., description="List of texts to translate")
    target_languages: List[SupportedLanguage] = Field(..., description="Target languages for translation")
    is_json: bool = Field(False, description="Whether the texts are JSON formatted")
    
    @field_validator('target_languages')
    @classmethod
    def validate_languages(cls, v):
        if not v:
            raise ValueError("At least one target language must be specified")
        return v

class AsyncBatchTranslationRequest(BaseModel):
    texts: List[str] = Field(..., description="List of texts to translate asynchronously")
    target_languages: List[SupportedLanguage] = Field(..., description="Target languages for translation")
    is_json: bool = Field(False, description="Whether the texts are JSON formatted")
    
    @field_validator('target_languages')
    @classmethod
    def validate_languages(cls, v):
        if not v:
            raise ValueError("At least one target language must be specified")
        return v

class ConfigUpdate(BaseModel):
    config: Dict[str, Any]

class MemoryConfig(BaseModel):
    gpu_memory: str = Field(..., examples=["20GB"])
    cpu_memory: str = Field(..., examples=["30GB"])

class GlossaryUpdate(BaseModel):
    terms: Dict[str, str] = Field(..., examples=[{"AI": "هوش مصنوعی", "Computer": "رایانه"}])

class GenerationParams(BaseModel):
    max_new_tokens: Optional[int] = Field(None, ge=1, le=2048)
    temperature: Optional[float] = Field(None, ge=0.1, le=2.0)
    do_sample: Optional[bool] = None
    top_p: Optional[float] = Field(None, ge=0.1, le=1.0)
    top_k: Optional[int] = Field(None, ge=1, le=100)

# Model Manager Class with Queue Support
class ModelManager:
    def __init__(self, config_path: str = "/home/anews/NewsPic_G/translate_services/config.json"):
        logger.info("="*50)
        logger.info("Initializing ModelManager with Queue System")
        logger.info("="*50)
        
        self.model = None
        self.tokenizer = None
        self.config = None
        self.config_path = config_path
        self.supported_languages = [lang.value for lang in SupportedLanguage]
        self.model_load_error = None
        self.max_input_tokens = 2048
        self.max_batch_size = 5
        self.model_lock = threading.Lock()  # Thread lock for model access
        self.queue_manager = translation_queue_manager  # Reference to queue manager
        self.device = None  # Track the device
        self.model_healthy = False
        self.translation_stats = {
            "total_translations": 0,
            "successful_translations": 0,
            "failed_translations": 0,
            "last_error": None,
            "last_error_time": None,
            "crashes": [],
            "cuda_resets": 0
        }
        
        # Load config first
        try:
            self.load_config()
            logger.info("Config loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load config: {e}", exc_info=True)
            self.config = self.get_default_config()
            self.save_config(self.config)
        
        # Reset CUDA before loading model
        self._reset_cuda_context()
        
        # Try to load model
        logger.info("Attempting to load model during initialization...")
        success = self.load_model()
        if not success:
            logger.warning("Model failed to load during initialization. Service will run without model.")
        else:
            logger.info("Model loaded successfully during initialization")
    
    def _reset_cuda_context(self):
        """Reset CUDA context to clear any errors"""
        try:
            logger.info("Resetting CUDA context...")
            
            # Clear any existing CUDA cache
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                
                # Reset peak memory stats
                torch.cuda.reset_peak_memory_stats()
                torch.cuda.reset_accumulated_memory_stats()
                
            # Force garbage collection
            gc.collect()
            
            self.translation_stats["cuda_resets"] += 1
            logger.info("CUDA context reset completed")
            
        except Exception as e:
            logger.error(f"Error resetting CUDA context: {e}")
    
    def _check_cuda_health(self) -> tuple[bool, str]:
        """Check if CUDA is in a healthy state"""
        try:
            if not torch.cuda.is_available():
                return False, "CUDA not available"
            
            # Try a simple CUDA operation
            test_tensor = torch.zeros(1, device='cuda')
            test_tensor = test_tensor + 1
            result = test_tensor.item()
            
            if result != 1.0:
                return False, "CUDA computation error"
            
            # Check memory status
            allocated = torch.cuda.memory_allocated(0)
            reserved = torch.cuda.memory_reserved(0)
            total = torch.cuda.get_device_properties(0).total_memory
            
            if allocated > total * 0.95:
                return False, f"GPU memory nearly full: {allocated/1024**3:.2f}/{total/1024**3:.2f} GB"
            
            return True, "CUDA healthy"
            
        except Exception as e:
            return False, f"CUDA health check failed: {str(e)}"
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration with auto device mapping for CPU+GPU"""
        return {
            "model": {
                "model_id": "CohereForAI/aya-23-8B",
                "torch_dtype": "bfloat16",
                "device_map": "auto",  # Auto device mapping for CPU+GPU
                "max_memory": {
                    0: "4GB",   # GPU: 4GB
                    "cpu": "5GB"  # CPU: 5GB
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
                
                # Fix max_memory keys - convert string "0" to integer 0
                if 'model' in self.config:
                    if 'max_memory' in self.config['model']:
                        old_max_memory = self.config['model']['max_memory']
                        new_max_memory = {}
                        for key, value in old_max_memory.items():
                            # Convert string digits to integers for GPU devices
                            if isinstance(key, str) and key.isdigit():
                                new_max_memory[int(key)] = value
                            else:
                                new_max_memory[key] = value
                        self.config['model']['max_memory'] = new_max_memory
                    
                    # Update to use auto device mapping
                    if self.config['model'].get('device_map') != 'auto':
                        logger.warning("Updating device_map to 'auto' for CPU+GPU usage")
                        self.config['model']['device_map'] = 'auto'
                        self.config['model']['max_memory'] = {0: "4GB", "cpu": "5GB"}  # Integer 0, not string
                        self.config['model']['offload_state_dict'] = True
                        self.save_config(self.config)
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
    
    def estimate_completion_time(self, text_length: int, num_languages: int = 1) -> datetime:
        """Estimate completion time based on text length and number of languages"""
        # Rough estimate: ~100 chars per second per language
        estimated_seconds = max(5, (text_length / 100) * num_languages)
        return datetime.now() + timedelta(seconds=estimated_seconds)
    
    def load_model(self) -> bool:
        """Load or reload the model with current configuration"""
        logger.info("="*50)
        logger.info("STARTING MODEL LOAD PROCESS (WITH AUTO DEVICE MAPPING)")
        logger.info("="*50)
        
        with self.model_lock:
            try:
                # ... (existing code for freeing memory and resetting CUDA)
                
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
                
                # Ensure max_memory has correct format (integer keys for GPU devices)
                max_memory = model_config.get('max_memory', {0: "4GB", "cpu": "5GB"})
                
                # Fix any string keys that should be integers
                fixed_max_memory = {}
                for key, value in max_memory.items():
                    if isinstance(key, str) and key.isdigit():
                        fixed_max_memory[int(key)] = value
                    else:
                        fixed_max_memory[key] = value
                
                # Load model with auto device mapping
                logger.info("Loading model weights with auto device mapping...")
                logger.info(f"Max memory config: {fixed_max_memory}")
                
                # Clear cache before loading
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
                # Load model with auto device mapping
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_id,
                    torch_dtype=torch_dtype,
                    device_map="auto",  # Auto device mapping
                    max_memory=fixed_max_memory,  # Use fixed max_memory
                    offload_folder=model_config.get('offload_folder', 'offload'),
                    offload_state_dict=model_config.get('offload_state_dict', True),
                    low_cpu_mem_usage=model_config.get('low_cpu_mem_usage', True),
                    trust_remote_code=True
                )
                
                # Set model to evaluation mode
                self.model.eval()
                
                logger.info("✓ Model loaded successfully with auto device mapping")
                self.model_load_error = None
                self.model_healthy = True
                
                # Log device map
                if hasattr(self.model, 'hf_device_map'):
                    logger.info(f"Model device map: {self.model.hf_device_map}")
                
                # Verify model health with a test
                self._verify_model_health()
                
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
                
                # Log CPU memory
                process = psutil.Process()
                cpu_memory = process.memory_info().rss / 1024**3
                logger.info(f"CPU Memory Usage: {cpu_memory:.2f} GB")
                
                logger.info("="*50)
                logger.info("MODEL LOADING COMPLETE - SUCCESS")
                logger.info("="*50)
                return True
                
            except Exception as e:
                self.model_load_error = str(e)
                self.model_healthy = False
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
    
    def _verify_model_health(self):
        """Verify model is working with a simple test"""
        if not self.model or not self.tokenizer:
            self.model_healthy = False
            return
        
        try:
            logger.info("Verifying model health...")
            
            # Simple test translation
            test_text = "Hello"
            test_prompt = f"Translate to Spanish: {test_text}"
            
            inputs = self.tokenizer(
                test_prompt,
                return_tensors="pt",
                max_length=50,
                truncation=True
            )
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=10,
                    do_sample=False,
                    pad_token_id=self.tokenizer.pad_token_id
                )
            
            # If we get here, model is working
            self.model_healthy = True
            logger.info("✓ Model health check passed")
            
        except Exception as e:
            self.model_healthy = False
            logger.error(f"Model health check failed: {e}")
            raise
    
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
            
            # Check for invalid token IDs
            vocab_size = len(self.tokenizer)
            max_token_id = max(tokens) if tokens else 0
            
            if max_token_id >= vocab_size:
                return False, token_count, f"Invalid token ID {max_token_id} (vocab size: {vocab_size})"
            
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
            
            # Reset CUDA context if needed
            self._reset_cuda_context()
            
        except Exception as e:
            logger.error(f"Emergency cleanup failed: {e}")
    
    def translate_multi_language(self, text: str, target_languages: List[str], is_json: bool = False) -> Dict[str, Any]:
        """Translate to multiple languages with queue/cache support"""
        request_id = str(uuid.uuid4())[:8]
        logger.info(f"[MULTI_TRANSLATE] Request ID: {request_id}, Languages: {target_languages}")
        
        # First, check cache
        cached_result = self.queue_manager.check_cache(text, target_languages, is_json)
        if cached_result:
            logger.info(f"[{request_id}] Returning cached translation")
            return cached_result
        
        # Use the processing lock to ensure sequential processing
        with self.queue_manager.processing_lock:
            logger.info(f"[{request_id}] Acquired processing lock for sequential processing")
            
            # Double-check cache in case another thread just cached it
            cached_result = self.queue_manager.check_cache(text, target_languages, is_json)
            if cached_result:
                logger.info(f"[{request_id}] Returning cached translation (double-check)")
                return cached_result
            
            # Perform the actual translation
            result = self._translate_multi_language_internal(text, target_languages, is_json)
            
            # Save to cache if successful
            if result.get("success"):
                self.queue_manager.save_to_cache(text, target_languages, is_json, result)
            
            logger.info(f"[{request_id}] Released processing lock")
            return result
    
    def _translate_multi_language_internal(self, text: str, target_languages: List[str], is_json: bool = False) -> Dict[str, Any]:
        """Internal method to perform actual multi-language translation"""
        translations_dict = {}
        errors_list = []
        successful_languages = []
        failed_languages = []
        
        for target_language in target_languages:
            try:
                result = self.translate_with_safety(text, target_language, is_json)
                
                if result["success"]:
                    translations_dict[target_language] = result["translation"]
                    successful_languages.append(target_language)
                else:
                    translations_dict[target_language] = None
                    failed_languages.append(target_language)
                    errors_list.append({
                        "language": target_language,
                        "error": result["error"],
                        "error_type": result["error_type"],
                        "details": result.get("details", {})
                    })
            
            except Exception as e:
                translations_dict[target_language] = None
                failed_languages.append(target_language)
                errors_list.append({
                    "language": target_language,
                    "error": str(e),
                    "error_type": "UNEXPECTED_ERROR"
                })
                logger.error(f"Error translating to {target_language}: {e}")
        
        return {
            "translations": translations_dict,
            "successful_languages": successful_languages,
            "failed_languages": failed_languages,
            "errors": errors_list,
            "success": len(failed_languages) == 0
        }
    
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
            # Check if model is loaded and healthy
            if self.model is None or self.tokenizer is None:
                logger.error(f"[{request_id}] Model not loaded")
                raise ModelNotLoadedError(f"Model not loaded. Error: {self.model_load_error or 'Unknown error'}")
            
            if not self.model_healthy:
                logger.error(f"[{request_id}] Model unhealthy, attempting reload")
                # Try to reload the model
                if not self.load_model():
                    raise ModelNotLoadedError(f"Model unhealthy and reload failed: {self.model_load_error}")
            
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
            self.model_healthy = False
            
        except RuntimeError as e:
            error_str = str(e).lower()
            if "out of memory" in error_str:
                result["error"] = f"Out of memory: {str(e)}"
                result["error_type"] = "OOM"
                logger.critical(f"[{request_id}] OOM Error: {e}")
                self._emergency_memory_cleanup()
                self.model_healthy = False
            elif "cuda" in error_str or "device-side assert" in error_str:
                result["error"] = f"CUDA error: {str(e)}"
                result["error_type"] = "CUDA_ERROR"
                logger.critical(f"[{request_id}] CUDA Error: {e}")
                self.model_healthy = False
                self._reset_cuda_context()
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
            with torch.cuda.amp.autocast(enabled=False):  # Disable autocast to prevent dtype issues
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
            
            # Reset model health status
            self.model_healthy = False
            
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
            "model_healthy": self.model_healthy,
            "supported_languages": self.supported_languages,
            "model_load_error": self.model_load_error,
            "max_input_tokens": self.max_input_tokens,
            "max_batch_size": self.max_batch_size,
            "translation_stats": self.translation_stats,
            "active_requests": request_tracker.get_active(),
            "recent_requests": request_tracker.get_history()[-10:],
            "cache_stats": self.queue_manager.get_cache_stats()
        }
        
        # Check CUDA health
        cuda_healthy, cuda_message = self._check_cuda_health()
        memory_info['cuda_healthy'] = cuda_healthy
        memory_info['cuda_status'] = cuda_message
        
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
    logger.info("STARTING FASTAPI TRANSLATION SERVICE WITH QUEUE SYSTEM")
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
    version="4.0.0",
    description="Enhanced translation service with queue system for sequential processing",
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

# Helper function to create StandardResponse
def create_response(success: bool, data: Optional[Dict[str, Any]] = None, 
                   message: Optional[str] = None, errors: Optional[List[Dict[str, Any]]] = None) -> StandardResponse:
    """Helper to create StandardResponse with proper field names"""
    return StandardResponse(**{
        "return": success,
        "data": data,
        "message": message,
        "errors": errors or []
    })

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
        "CUDA_ERROR": "GPU error detected. The model will be reloaded automatically. Please try again.",
        "UNKNOWN_ERROR": "An unexpected error occurred. Please contact support."
    }
    return suggestions.get(error_type, "Please try again or contact support.")

# API Endpoints

@app.get("/", response_model=StandardResponse)
async def root():
    """Root endpoint with service information"""
    return create_response(
        success=model_manager is not None,
        data={
            "service": "Translation Model Service",
            "version": "4.0.0",
            "status": "running",
            "model_loaded": model_manager.model is not None if model_manager else False,
            "model_healthy": model_manager.model_healthy if model_manager else False,
            "max_input_tokens": model_manager.max_input_tokens if model_manager else 2048,
            "supported_languages": [lang.value for lang in SupportedLanguage],
            "cuda_available": torch.cuda.is_available(),
            "cache_stats": translation_queue_manager.get_cache_stats(),
            "endpoints": {
                "health": "/health",
                "translate": "/translate",
                "translate_async": "/translate/async",
                "get_async_translation": "/translate/async/{uuid}",
                "batch": "/translate/batch",
                "batch_async": "/translate/batch/async",
                "languages": "/languages",
                "memory": "/memory",
                "stats": "/stats",
                "reload": "/reload",
                "free_memory": "/free_memory",
                "cache": "/cache",
                "clear_cache": "/cache/clear"
            }
        },
        message="Service is running with queue system for sequential processing"
    )

@app.get("/health", response_model=StandardResponse)
async def health_check():
    """Health check endpoint"""
    global model_manager
    
    if not model_manager:
        return create_response(
            success=False,
            message="Model manager not initialized",
            errors=[{"type": "INIT_ERROR", "detail": "Model manager not initialized"}],
            data={
                "status": "unhealthy",
                "model_loaded": False
            }
        )
    
    return create_response(
        success=model_manager.model is not None and model_manager.model_healthy,
        data={
            "status": "healthy" if (model_manager.model is not None and model_manager.model_healthy) else "degraded",
            "model_loaded": model_manager.model is not None,
            "model_healthy": model_manager.model_healthy,
            "model_load_error": model_manager.model_load_error,
            "supported_languages": model_manager.supported_languages,
            "max_input_tokens": model_manager.max_input_tokens,
            "stats": model_manager.translation_stats,
            "memory": model_manager.get_memory_usage(),
            "async_storage_stats": async_storage.get_stats(),
            "cache_stats": translation_queue_manager.get_cache_stats()
        },
        message="Service is healthy" if (model_manager.model is not None and model_manager.model_healthy) else "Service is degraded - model issues detected",
        errors=[] if (model_manager.model is not None and model_manager.model_healthy) else [{"type": "MODEL_UNHEALTHY", "detail": model_manager.model_load_error}]
    )

@app.get("/cache", response_model=StandardResponse)
async def get_cache_stats():
    """Get cache statistics"""
    return create_response(
        success=True,
        data=translation_queue_manager.get_cache_stats(),
        message="Cache statistics retrieved successfully"
    )

@app.post("/cache/clear", response_model=StandardResponse)
async def clear_cache():
    """Clear the translation cache"""
    try:
        translation_queue_manager.clear_cache()
        return create_response(
            success=True,
            message="Cache cleared successfully"
        )
    except Exception as e:
        return create_response(
            success=False,
            message="Failed to clear cache",
            errors=[{"type": "CACHE_ERROR", "detail": str(e)}]
        )

@app.get("/languages", response_model=StandardResponse)
async def get_supported_languages():
    """Get list of supported languages"""
    return create_response(
        success=True,
        data={
            "languages": [lang.value for lang in SupportedLanguage],
            "count": len(SupportedLanguage)
        },
        message="Supported languages retrieved successfully"
    )

@app.post("/translate", response_model=StandardResponse)
async def translate(request: TranslationRequest):
    """Translate single text to multiple languages (sequential processing with cache)"""
    logger.info(f"[TRANSLATE_ENDPOINT] Received request for {len(request.text)} chars to {len(request.target_languages)} languages")
    
    if not model_manager:
        return create_response(
            success=False,
            message="Model service not initialized",
            errors=[{"type": "SERVICE_ERROR", "detail": "Model service not initialized"}]
        )
    
    try:
        # Convert target_languages to list of string values
        target_langs = [lang.value for lang in request.target_languages]
        
        # Use multi-language translation (will check cache and process sequentially)
        result = model_manager.translate_multi_language(
            request.text,
            target_langs,
            request.is_json
        )
        
        if result["success"]:
            return create_response(
                success=True,
                data={
                    "translations": result["translations"],
                    "original": request.text,
                    "target_languages": target_langs,
                    "successful_languages": result["successful_languages"]
                },
                message="Translation completed successfully"
            )
        else:
            return create_response(
                success=False,
                data={
                    "translations": result["translations"],
                    "original": request.text,
                    "target_languages": target_langs,
                    "successful_languages": result["successful_languages"],
                    "failed_languages": result["failed_languages"]
                },
                message="Some translations failed",
                errors=result["errors"]
            )
    
    except Exception as e:
        logger.error(f"Unexpected error in translate endpoint: {e}", exc_info=True)
        return create_response(
            success=False,
            message="Translation failed due to unexpected error",
            errors=[{
                "type": "UNEXPECTED_ERROR",
                "detail": str(e),
                "suggestion": get_error_suggestion("UNEXPECTED_ERROR")
            }]
        )

@app.post("/translate/async", response_model=StandardResponse)
async def translate_async(request: AsyncTranslationRequest, background_tasks: BackgroundTasks):
    """Submit a text for async translation to multiple languages"""
    logger.info(f"[TRANSLATE_ASYNC] Received async request for {len(request.text)} chars to {len(request.target_languages)} languages")
    
    if not model_manager:
        return create_response(
            success=False,
            message="Model service not initialized",
            errors=[{"type": "SERVICE_ERROR", "detail": "Model service not initialized"}]
        )
    
    if not model_manager.model:
        return create_response(
            success=False,
            message="Model not loaded",
            errors=[{
                "type": "MODEL_NOT_LOADED",
                "detail": f"Model is not loaded. Error: {model_manager.model_load_error or 'Unknown'}",
                "suggestion": "Use /reload endpoint to load the model"
            }]
        )
    
    # Generate unique ID for this translation
    translation_id = str(uuid.uuid4())
    
    # Convert target_languages to list of string values
    target_langs = [lang.value for lang in request.target_languages]
    
    # Estimate completion time
    estimated_completion = model_manager.estimate_completion_time(len(request.text), len(target_langs))
    
    # Save initial status
    try:
        async_storage.save_translation(
            translation_id=translation_id,
            text=request.text,
            translations={},
            target_languages=target_langs,
            metadata={
                "is_json": request.is_json,
                "text_length": len(request.text),
                "status": "processing",
                "started_at": datetime.now().isoformat(),
                "estimated_completion": estimated_completion.isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Failed to save initial status: {e}")
        return create_response(
            success=False,
            message="Failed to initialize async translation",
            errors=[{"type": "STORAGE_ERROR", "detail": str(e)}]
        )
    
    # Function to perform translation in background
    def perform_multi_translation_background(trans_id: str, text: str, target_langs: List[str], is_json: bool):
        """Background task to perform multi-language translation"""
        try:
            logger.info(f"[BACKGROUND] Starting multi-language translation for {trans_id}")
            
            # Perform the translation (will use queue and cache automatically)
            result = model_manager.translate_multi_language(text, target_langs, is_json)
            
            if result["success"]:
                async_storage.save_translation(
                    translation_id=trans_id,
                    text=text,
                    translations=result["translations"],
                    target_languages=target_langs,
                    metadata={
                        "is_json": is_json,
                        "text_length": len(text),
                        "successful_languages": result["successful_languages"],
                        "status": "completed",
                        "completed_at": datetime.now().isoformat()
                    }
                )
                logger.info(f"[BACKGROUND] Translation {trans_id} completed successfully")
            else:
                async_storage.save_translation(
                    translation_id=trans_id,
                    text=text,
                    translations=result["translations"],
                    target_languages=target_langs,
                    metadata={
                        "is_json": is_json,
                        "errors": result["errors"],
                        "successful_languages": result["successful_languages"],
                        "failed_languages": result["failed_languages"],
                        "status": "partial" if result["successful_languages"] else "failed",
                        "completed_at": datetime.now().isoformat()
                    }
                )
                logger.warning(f"[BACKGROUND] Translation {trans_id} completed with errors")
                
        except Exception as e:
            logger.error(f"[BACKGROUND] Translation {trans_id} error: {e}", exc_info=True)
            try:
                async_storage.save_translation(
                    translation_id=trans_id,
                    text=text,
                    translations={},
                    target_languages=target_langs,
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
        perform_multi_translation_background,
        translation_id,
        request.text,
        target_langs,
        request.is_json
    )
    
    logger.info(f"[TRANSLATE_ASYNC] Returning UUID {translation_id} immediately")
    return create_response(
        success=True,
        data={
            "uuid": translation_id,
            "status": "processing",
            "estimated_completion_time": estimated_completion.isoformat()
        },
        message="Translation request received and is being processed"
    )

@app.get("/translate/async/{uuid}", response_model=StandardResponse)
async def get_async_translation(uuid: str):
    """Retrieve a previously translated text using its UUID"""
    logger.info(f"[GET_ASYNC_TRANSLATION] Retrieving translation {uuid}")
    
    translation_data = async_storage.get_translation(uuid)
    
    if translation_data is None:
        logger.warning(f"[GET_ASYNC_TRANSLATION] Translation {uuid} not found")
        return create_response(
            success=False,
            message=f"Translation with UUID {uuid} not found",
            errors=[{"type": "NOT_FOUND", "detail": f"No translation found with UUID: {uuid}"}]
        )
    
    metadata = translation_data.get("metadata", {})
    status_value = metadata.get("status", "unknown")
    
    if status_value == "processing":
        return create_response(
            success=True,
            data={
                "uuid": uuid,
                "status": "processing",
                "original_text": translation_data.get("original_text"),
                "translations": {},
                "target_languages": translation_data.get("target_languages"),
                "timestamp": translation_data.get("timestamp"),
                "estimated_completion": metadata.get("estimated_completion")
            },
            message="Translation is still being processed"
        )
    
    if status_value in ["completed", "partial"]:
        return create_response(
            success=status_value == "completed",
            data={
                "uuid": uuid,
                "status": status_value,
                "original_text": translation_data.get("original_text"),
                "translations": translation_data.get("translations", {}),
                "target_languages": translation_data.get("target_languages"),
                "timestamp": translation_data.get("timestamp"),
                "successful_languages": metadata.get("successful_languages", []),
                "failed_languages": metadata.get("failed_languages", [])
            },
            message="Translation completed successfully" if status_value == "completed" else "Translation partially completed",
            errors=metadata.get("errors", []) if status_value == "partial" else []
        )
    else:
        return create_response(
            success=False,
            data={
                "uuid": uuid,
                "status": "failed",
                "original_text": translation_data.get("original_text"),
                "translations": translation_data.get("translations", {}),
                "target_languages": translation_data.get("target_languages"),
                "timestamp": translation_data.get("timestamp")
            },
            message="Translation failed",
            errors=metadata.get("errors", []) or [{"type": metadata.get("error_type", "UNKNOWN"), "detail": metadata.get("error", "Unknown error")}]
        )

@app.post("/translate/batch", response_model=StandardResponse)
async def translate_batch(request: BatchTranslationRequest):
    """Translate multiple texts to multiple languages synchronously (sequential processing with cache)"""
    if not model_manager:
        return create_response(
            success=False,
            message="Model service not initialized",
            errors=[{"type": "SERVICE_ERROR", "detail": "Model service not initialized"}]
        )
    
    if len(request.texts) > model_manager.max_batch_size:
        return create_response(
            success=False,
            message=f"Batch size too large. Maximum: {model_manager.max_batch_size} texts",
            errors=[{
                "type": "BATCH_SIZE_ERROR",
                "detail": f"Received {len(request.texts)} texts, maximum allowed is {model_manager.max_batch_size}"
            }]
        )
    
    target_langs = [lang.value for lang in request.target_languages]
    
    translations = []
    all_errors = []
    
    for idx, text in enumerate(request.texts):
        # Each translation will be processed sequentially with cache support
        result = model_manager.translate_multi_language(text, target_langs, request.is_json)
        
        translation_entry = {
            "index": idx,
            "original": text,
            "translations": result["translations"],
            "success": result["success"],
            "successful_languages": result["successful_languages"],
            "failed_languages": result.get("failed_languages", [])
        }
        
        if not result["success"]:
            for error in result.get("errors", []):
                all_errors.append({
                    "text_index": idx,
                    "language": error.get("language"),
                    "error": error.get("error"),
                    "error_type": error.get("error_type")
                })
        
        translations.append(translation_entry)
    
    success = len(all_errors) == 0
    
    return create_response(
        success=success,
        data={
            "translations": translations,
            "target_languages": target_langs,
            "total_texts": len(request.texts),
            "successful": sum(1 for t in translations if t["success"]),
            "failed": sum(1 for t in translations if not t["success"])
        },
        message="All translations completed successfully" if success else "Some translations failed",
        errors=all_errors
    )

@app.post("/translate/batch/async", response_model=StandardResponse)
async def translate_batch_async(request: AsyncBatchTranslationRequest, background_tasks: BackgroundTasks):
    """Submit multiple texts for async translation to multiple languages"""
    logger.info(f"[BATCH_ASYNC] Received async batch request for {len(request.texts)} texts to {len(request.target_languages)} languages")
    
    if not model_manager:
        return create_response(
            success=False,
            message="Model service not initialized",
            errors=[{"type": "SERVICE_ERROR", "detail": "Model service not initialized"}]
        )
    
    batch_id = str(uuid.uuid4())
    target_langs = [lang.value for lang in request.target_languages]
    
    total_text_length = sum(len(text) for text in request.texts)
    estimated_completion = model_manager.estimate_completion_time(total_text_length, len(target_langs))
    
    def perform_batch_translation_background(batch_id: str, texts: List[str], target_langs: List[str], is_json: bool):
        try:
            logger.info(f"[BACKGROUND_BATCH] Starting batch translation for {batch_id}")
            
            async_storage.save_translation(
                translation_id=batch_id,
                text=texts,
                translations={},
                target_languages=target_langs,
                metadata={
                    "is_json": is_json,
                    "is_batch": True,
                    "text_count": len(texts),
                    "total_length": sum(len(t) for t in texts),
                    "status": "processing",
                    "started_at": datetime.now().isoformat(),
                    "estimated_completion": estimated_completion.isoformat()
                }
            )
            
            batch_translations = {}
            batch_errors = []
            successful_count = 0
            
            for idx, text in enumerate(texts):
                # Each translation will be processed sequentially with cache support
                result = model_manager.translate_multi_language(text, target_langs, is_json)
                
                batch_translations[f"text_{idx}"] = {
                    "original": text,
                    "translations": result["translations"],
                    "success": result["success"],
                    "successful_languages": result["successful_languages"],
                    "failed_languages": result.get("failed_languages", [])
                }
                
                if result["success"]:
                    successful_count += 1
                else:
                    for error in result.get("errors", []):
                        batch_errors.append({
                            "text_index": idx,
                            "language": error.get("language"),
                            "error": error.get("error"),
                            "error_type": error.get("error_type")
                        })
            
            async_storage.save_translation(
                translation_id=batch_id,
                text=texts,
                translations=batch_translations,
                target_languages=target_langs,
                metadata={
                    "is_json": is_json,
                    "is_batch": True,
                    "text_count": len(texts),
                    "successful_count": successful_count,
                    "failed_count": len(texts) - successful_count,
                    "errors": batch_errors,
                    "status": "completed" if not batch_errors else "partial",
                    "completed_at": datetime.now().isoformat()
                }
            )
            
            logger.info(f"[BACKGROUND_BATCH] Batch {batch_id} completed with {successful_count}/{len(texts)} successful")
            
        except Exception as e:
            logger.error(f"[BACKGROUND_BATCH] Batch {batch_id} error: {e}", exc_info=True)
            try:
                async_storage.save_translation(
                    translation_id=batch_id,
                    text=texts,
                    translations={},
                    target_languages=target_langs,
                    metadata={
                        "is_json": is_json,
                        "is_batch": True,
                        "error": str(e),
                        "error_type": "UNEXPECTED_ERROR",
                        "status": "failed",
                        "failed_at": datetime.now().isoformat()
                    }
                )
            except:
                pass
    
    background_tasks.add_task(
        perform_batch_translation_background,
        batch_id,
        request.texts,
        target_langs,
        request.is_json
    )
    
    logger.info(f"[BATCH_ASYNC] Returning batch UUID {batch_id} immediately")
    return create_response(
        success=True,
        data={
            "uuid": batch_id,
            "status": "processing",
            "text_count": len(request.texts),
            "target_languages": target_langs,
            "estimated_completion_time": estimated_completion.isoformat()
        },
        message="Batch translation request received and is being processed"
    )

@app.delete("/translate/async/{uuid}", response_model=StandardResponse)
async def delete_async_translation(uuid: str):
    """Delete a stored translation by UUID"""
    logger.info(f"[DELETE_ASYNC_TRANSLATION] Deleting translation {uuid}")
    
    deleted = async_storage.delete_translation(uuid)
    
    if deleted:
        return create_response(
            success=True,
            data={"uuid": uuid},
            message=f"Translation {uuid} deleted successfully"
        )
    else:
        return create_response(
            success=False,
            message=f"Translation with UUID {uuid} not found",
            errors=[{"type": "NOT_FOUND", "detail": f"No translation found with UUID: {uuid}"}]
        )

@app.get("/translate/async", response_model=StandardResponse)
async def list_async_translations():
    """List all stored translation UUIDs"""
    translation_ids = async_storage.get_all_ids()
    stats = async_storage.get_stats()
    
    return create_response(
        success=True,
        data={
            "translation_ids": translation_ids,
            "count": len(translation_ids),
            "stats": stats
        },
        message="Translation list retrieved successfully"
    )

@app.get("/stats", response_model=StandardResponse)
async def get_stats():
    """Get translation statistics"""
    if not model_manager:
        return create_response(
            success=False,
            message="Model service not initialized",
            errors=[{"type": "SERVICE_ERROR", "detail": "Model service not initialized"}]
        )
    
    return create_response(
        success=True,
        data={
            "statistics": model_manager.translation_stats,
            "memory": model_manager.get_memory_usage(),
            "async_storage": async_storage.get_stats(),
            "cache_stats": translation_queue_manager.get_cache_stats()
        },
        message="Statistics retrieved successfully"
    )

@app.get("/memory", response_model=StandardResponse)
async def get_memory_usage():
    """Get memory usage statistics"""
    if not model_manager:
        return create_response(
            success=False,
            message="Model service not initialized",
            errors=[{"type": "SERVICE_ERROR", "detail": "Model service not initialized"}]
        )
    
    return create_response(
        success=True,
        data=model_manager.get_memory_usage(),
        message="Memory usage retrieved successfully"
    )

@app.post("/reload", response_model=StandardResponse)
async def reload_model():
    """Reload the model with CUDA reset"""
    if not model_manager:
        return create_response(
            success=False,
            message="Model service not initialized",
            errors=[{"type": "SERVICE_ERROR", "detail": "Model service not initialized"}]
        )
    
    logger.info("Model reload requested via API")
    
    try:
        # Reset CUDA context before reloading
        model_manager._reset_cuda_context()
        
        if model_manager.load_model():
            return create_response(
                success=True,
                data={"memory": model_manager.get_memory_usage()},
                message="Model reloaded successfully"
            )
        else:
            return create_response(
                success=False,
                message="Model reload failed",
                errors=[{
                    "type": "RELOAD_ERROR",
                    "detail": model_manager.model_load_error or "Unknown error",
                    "suggestion": get_error_suggestion("MODEL_NOT_LOADED")
                }]
            )
    except Exception as e:
        logger.error(f"Model reload error: {e}", exc_info=True)
        return create_response(
            success=False,
            message="Model reload failed due to unexpected error",
            errors=[{
                "type": "UNEXPECTED_ERROR",
                "detail": str(e),
                "suggestion": get_error_suggestion("UNKNOWN_ERROR")
            }]
        )

@app.post("/free_memory", response_model=StandardResponse)
async def free_gpu_memory():
    """Free GPU memory and reset CUDA context"""
    if not model_manager:
        return create_response(
            success=False,
            message="Model service not initialized",
            errors=[{"type": "SERVICE_ERROR", "detail": "Model service not initialized"}]
        )
    
    try:
        result = model_manager.free_memory()
        
        # Also reset CUDA context after freeing memory
        model_manager._reset_cuda_context()
        
        return create_response(
            success=result.get("status") == "completed",
            data=result,
            message="Memory freed successfully" if result.get("status") == "completed" else "Memory free operation failed",
            errors=[] if result.get("status") == "completed" else [{"type": "MEMORY_ERROR", "detail": result.get("error", "Unknown error")}]
        )
    except Exception as e:
        logger.error(f"Free memory error: {e}", exc_info=True)
        return create_response(
            success=False,
            message="Failed to free memory",
            errors=[{
                "type": "UNEXPECTED_ERROR",
                "detail": str(e)
            }]
        )

@app.post("/reset_cuda", response_model=StandardResponse)
async def reset_cuda():
    """Reset CUDA context to recover from errors"""
    if not model_manager:
        return create_response(
            success=False,
            message="Model service not initialized",
            errors=[{"type": "SERVICE_ERROR", "detail": "Model service not initialized"}]
        )
    
    try:
        logger.info("CUDA reset requested via API")
        
        # Free model memory first
        if model_manager.model is not None:
            model_manager.free_memory()
        
        # Reset CUDA context
        model_manager._reset_cuda_context()
        
        # Check CUDA health
        cuda_healthy, cuda_message = model_manager._check_cuda_health()
        
        return create_response(
            success=cuda_healthy,
            data={
                "cuda_healthy": cuda_healthy,
                "cuda_status": cuda_message,
                "cuda_resets": model_manager.translation_stats.get("cuda_resets", 0)
            },
            message="CUDA context reset successfully" if cuda_healthy else "CUDA reset completed but health check failed",
            errors=[] if cuda_healthy else [{"type": "CUDA_ERROR", "detail": cuda_message}]
        )
    except Exception as e:
        logger.error(f"CUDA reset error: {e}", exc_info=True)
        return create_response(
            success=False,
            message="Failed to reset CUDA context",
            errors=[{
                "type": "UNEXPECTED_ERROR",
                "detail": str(e)
            }]
        )

@app.get("/config", response_model=StandardResponse)
async def get_config():
    """Get current configuration"""
    if not model_manager:
        return create_response(
            success=False,
            message="Model service not initialized",
            errors=[{"type": "SERVICE_ERROR", "detail": "Model service not initialized"}]
        )
    
    return create_response(
        success=True,
        data={"config": model_manager.config},
        message="Configuration retrieved successfully"
    )

@app.post("/config", response_model=StandardResponse)
async def update_config(config_update: ConfigUpdate):
    """Update configuration"""
    if not model_manager:
        return create_response(
            success=False,
            message="Model service not initialized",
            errors=[{"type": "SERVICE_ERROR", "detail": "Model service not initialized"}]
        )
    
    try:
        success = model_manager.save_config(config_update.config)
        if success:
            return create_response(
                success=True,
                data={"config": model_manager.config},
                message="Configuration updated successfully. Reload model to apply changes."
            )
        else:
            return create_response(
                success=False,
                message="Failed to save configuration",
                errors=[{"type": "CONFIG_ERROR", "detail": "Could not save configuration file"}]
            )
    except Exception as e:
        logger.error(f"Config update error: {e}", exc_info=True)
        return create_response(
            success=False,
            message="Failed to update configuration",
            errors=[{
                "type": "UNEXPECTED_ERROR",
                "detail": str(e)
            }]
        )

@app.post("/glossary", response_model=StandardResponse)
async def update_glossary(glossary: GlossaryUpdate):
    """Update translation glossary"""
    if not model_manager:
        return create_response(
            success=False,
            message="Model service not initialized",
            errors=[{"type": "SERVICE_ERROR", "detail": "Model service not initialized"}]
        )
    
    try:
        if 'glossary' not in model_manager.config:
            model_manager.config['glossary'] = {}
        
        model_manager.config['glossary'].update(glossary.terms)
        success = model_manager.save_config(model_manager.config)
        
        if success:
            return create_response(
                success=True,
                data={"glossary": model_manager.config['glossary']},
                message="Glossary updated successfully"
            )
        else:
            return create_response(
                success=False,
                message="Failed to save glossary",
                errors=[{"type": "GLOSSARY_ERROR", "detail": "Could not save glossary to configuration"}]
            )
    except Exception as e:
        logger.error(f"Glossary update error: {e}", exc_info=True)
        return create_response(
            success=False,
            message="Failed to update glossary",
            errors=[{
                "type": "UNEXPECTED_ERROR",
                "detail": str(e)
            }]
        )

@app.get("/glossary", response_model=StandardResponse)
async def get_glossary():
    """Get current glossary"""
    if not model_manager:
        return create_response(
            success=False,
            message="Model service not initialized",
            errors=[{"type": "SERVICE_ERROR", "detail": "Model service not initialized"}]
        )
    
    return create_response(
        success=True,
        data={"glossary": model_manager.config.get('glossary', {})},
        message="Glossary retrieved successfully"
    )

@app.post("/generation_params", response_model=StandardResponse)
async def update_generation_params(params: GenerationParams):
    """Update generation parameters"""
    if not model_manager:
        return create_response(
            success=False,
            message="Model service not initialized",
            errors=[{"type": "SERVICE_ERROR", "detail": "Model service not initialized"}]
        )
    
    try:
        if 'translation' not in model_manager.config:
            model_manager.config['translation'] = {}
        if 'generation_params' not in model_manager.config['translation']:
            model_manager.config['translation']['generation_params'] = {}
        
        # Update only provided parameters
        for key, value in params.model_dump(exclude_none=True).items():
            model_manager.config['translation']['generation_params'][key] = value
        
        success = model_manager.save_config(model_manager.config)
        
        if success:
            return create_response(
                success=True,
                data={"generation_params": model_manager.config['translation']['generation_params']},
                message="Generation parameters updated successfully"
            )
        else:
            return create_response(
                success=False,
                message="Failed to save generation parameters",
                errors=[{"type": "CONFIG_ERROR", "detail": "Could not save parameters to configuration"}]
            )
    except Exception as e:
        logger.error(f"Generation params update error: {e}", exc_info=True)
        return create_response(
            success=False,
            message="Failed to update generation parameters",
            errors=[{
                "type": "UNEXPECTED_ERROR",
                "detail": str(e)
            }]
        )

@app.get("/generation_params", response_model=StandardResponse)
async def get_generation_params():
    """Get current generation parameters"""
    if not model_manager:
        return create_response(
            success=False,
            message="Model service not initialized",
            errors=[{"type": "SERVICE_ERROR", "detail": "Model service not initialized"}]
        )
    
    params = {}
    if 'translation' in model_manager.config:
        params = model_manager.config['translation'].get('generation_params', {})
    
    return create_response(
        success=True,
        data={"generation_params": params},
        message="Generation parameters retrieved successfully"
    )

# Signal handlers for graceful shutdown
def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    if model_manager:
        model_manager.free_memory()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    import uvicorn
    
    # Set up environment for better CUDA debugging
    os.environ['CUDA_LAUNCH_BLOCKING'] = '1'
    os.environ['TORCH_USE_CUDA_DSA'] = '1'
    
    logger.info("Starting Translation Service with Queue System...")
    logger.info(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        logger.info(f"CUDA device: {torch.cuda.get_device_name(0)}")
        logger.info(f"CUDA version: {torch.version.cuda}")
        logger.info("GPU Memory Limit: 4GB")
    logger.info("CPU Memory Limit: 5GB")
    logger.info("Queue System: Enabled for sequential processing")
    logger.info("Cache System: Enabled for duplicate request optimization")
    
    # Run with single worker to avoid CUDA context issues
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8001, 
        workers=1,  # IMPORTANT: Only 1 worker for CUDA
        loop="asyncio",
        log_level="info"
    )