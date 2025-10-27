"""
Standalone Model Service for Translation
Run with: uvicorn model_service:app --host 0.0.0.0 --port 8001 --workers 1
"""

import json
import torch
import gc
import os
import traceback
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoTokenizer, AutoModelForCausalLM
import logging
from contextlib import asynccontextmanager
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    text: str = Field(..., description="Text to translate", example="Hello, how are you?")
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

# Model Manager Class
class ModelManager:
    def __init__(self, config_path: str = "/home/anews/NewsPic_G/translate_services/config.json"):
        self.model = None
        self.tokenizer = None
        self.config = None
        self.config_path = config_path
        self.supported_languages = [lang.value for lang in SupportedLanguage]
        self.model_load_error = None
        
        # Load config first
        try:
            self.load_config()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self.config = self.get_default_config()
            self.save_config(self.config)
        
        # Try to load model
        success = self.load_model()
        if not success:
            logger.warning("Model failed to load during initialization. Service will run without model.")
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "model": {
                "model_id": "CohereForAI/aya-23-8B",  # Fixed model path
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
                    "max_new_tokens": 128,
                    "temperature": 0.7,
                    "do_sample": True,
                    "top_p": 0.9
                }
            },
            "glossary": {}
        }
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
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
                    "max_new_tokens": 128,
                    "temperature": 0.7,
                    "do_sample": True,
                    "top_p": 0.9
                }
            
            logger.info("Configuration loaded successfully")
            return self.config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            raise
    
    def save_config(self, new_config: Dict[str, Any]) -> bool:
        """Save new configuration to JSON file"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=2, ensure_ascii=False)
            self.config = new_config
            logger.info("Configuration saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False
    
    def load_model(self) -> bool:
        """Load or reload the model with current configuration"""
        try:
            # First, free any existing model
            if self.model is not None or self.tokenizer is not None:
                logger.info("Existing model detected, freeing memory first...")
                self.free_memory()
            
            model_config = self.config.get('model', {})
            
            # Validate model_id
            model_id = model_config.get('model_id', 'CohereForAI/aya-23-8B')
            logger.info(f"Attempting to load model: {model_id}")
            
            # Convert string dtype to torch dtype
            dtype_map = {
                'bfloat16': torch.bfloat16,
                'float16': torch.float16,
                'float32': torch.float32
            }
            torch_dtype = dtype_map.get(model_config.get('torch_dtype', 'bfloat16'), torch.bfloat16)
            
            # Prepare max_memory dict
            max_memory = {}
            if 'max_memory' in model_config:
                if 'gpu' in model_config['max_memory']:
                    max_memory[0] = model_config['max_memory']['gpu']
                if 'cpu' in model_config['max_memory']:
                    max_memory['cpu'] = model_config['max_memory']['cpu']
            else:
                # Default memory allocation
                max_memory = {0: "20GB", "cpu": "30GB"}
            
            logger.info(f"Memory allocation - GPU: {max_memory.get(0, 'auto')}, CPU: {max_memory.get('cpu', 'auto')}")
            
            # Create offload folder if needed
            offload_folder = model_config.get('offload_folder', 'offload')
            if offload_folder and not os.path.isabs(offload_folder):
                offload_folder = os.path.join(os.path.dirname(self.config_path), offload_folder)
            os.makedirs(offload_folder, exist_ok=True)
            
            # Load tokenizer first (less memory intensive)
            logger.info("Loading tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_id,
                trust_remote_code=True
            )
            
            # Set padding token if needed
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            logger.info("Tokenizer loaded successfully")
            
            # Load model
            logger.info("Loading model weights...")
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
            
            logger.info("Model loaded successfully")
            self.model_load_error = None
            
            # Log memory usage after loading
            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated(0) / 1024**3
                reserved = torch.cuda.memory_reserved(0) / 1024**3
                logger.info(f"GPU memory after loading - Allocated: {allocated:.2f} GB, Reserved: {reserved:.2f} GB")
            
            return True
            
        except Exception as e:
            self.model_load_error = str(e)
            logger.error(f"Error loading model: {e}")
            logger.error(traceback.format_exc())
            
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
    
    def translate(self, text: str, target_language: str = None, is_json: bool = False) -> str:
        """Translate text using the loaded model"""
        if self.model is None or self.tokenizer is None:
            raise RuntimeError(f"Model not loaded. Error: {self.model_load_error or 'Unknown error'}")
        
        # Validate target language
        if target_language and target_language not in self.supported_languages:
            raise ValueError(f"Unsupported language: {target_language}. Supported languages: {', '.join(self.supported_languages)}")
        
        try:
            # Use provided target language or default from config
            target_lang = target_language or self.config['translation'].get('target_language', 'Persian')
            
            # Build system prompt
            trans_config = self.config['translation']
            system = [f"Translate the user's text to {target_lang}."]
            
            # Add context if exists
            if 'context' in trans_config:
                for key, value in trans_config['context'].items():
                    key_pascal = key.capitalize()
                    system.append(f"{key_pascal}: {value}")
            
            # Add glossary if exists and target language matches configured one
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
            prompt = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            
            # Tokenize
            inputs = self.tokenizer(prompt, return_tensors="pt")
            
            # Move to appropriate device
            if torch.cuda.is_available():
                inputs = inputs.to("cuda")
            
            input_length = inputs["input_ids"].shape[1]
            
            # Generate
            gen_params = trans_config.get('generation_params', {})
            with torch.inference_mode():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=gen_params.get('max_new_tokens', 128),
                    temperature=gen_params.get('temperature', 0.7),
                    do_sample=gen_params.get('do_sample', True),
                    top_p=gen_params.get('top_p', 0.9),
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
            
            # Decode
            generated_tokens = outputs[0][input_length:]
            translation = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
            
            # Try to parse as JSON if requested
            if is_json:
                try:
                    return json.loads(translation)
                except json.JSONDecodeError:
                    return translation
            
            return translation
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            raise
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current GPU/CPU memory usage"""
        memory_info = {
            "is_model_loaded": self.model is not None,
            "is_tokenizer_loaded": self.tokenizer is not None,
            "supported_languages": self.supported_languages,
            "model_load_error": self.model_load_error,
        }
        
        if torch.cuda.is_available():
            memory_info['gpu_allocated_gb'] = torch.cuda.memory_allocated(0) / 1024**3
            memory_info['gpu_reserved_gb'] = torch.cuda.memory_reserved(0) / 1024**3
            memory_info['gpu_total_gb'] = torch.cuda.get_device_properties(0).total_memory / 1024**3
        
        # Add CPU memory info
        try:
            import psutil
            process = psutil.Process()
            memory_info['cpu_memory_gb'] = process.memory_info().rss / 1024**3
            memory_info['cpu_percent'] = process.memory_percent()
        except ImportError:
            pass
        
        return memory_info

# Initialize model manager globally
model_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global model_manager
    logger.info("Starting Model Service...")
    model_manager = ModelManager()
    
    # Check if model loaded successfully
    if model_manager.model is None:
        logger.warning("Model Service started but model is not loaded. Use /reload endpoint to retry loading.")
    else:
        logger.info("Model Service started successfully with model loaded")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Model Service...")
    if model_manager:
        model_manager.free_memory()
    logger.info("Model Service shutdown complete")

# Create FastAPI app
app = FastAPI(title="Translation Model Service", version="1.0.0", lifespan=lifespan)

# API Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    global model_manager
    
    if not model_manager:
        return {
            "status": "unhealthy",
            "model_loaded": False,
            "error": "Model manager not initialized"
        }
    
    return {
        "status": "healthy" if model_manager.model is not None else "degraded",
        "model_loaded": model_manager.model is not None,
        "model_load_error": model_manager.model_load_error,
        "supported_languages": model_manager.supported_languages
    }

@app.get("/languages")
async def get_supported_languages():
    """Get list of supported languages"""
    return {
        "languages": [lang.value for lang in SupportedLanguage],
        "count": len(SupportedLanguage)
    }

@app.post("/translate")
async def translate(request: TranslationRequest):
    """Translate single text"""
    if not model_manager:
        raise HTTPException(status_code=503, detail="Model service not initialized")
    
    if model_manager.model is None:
        raise HTTPException(
            status_code=503, 
            detail=f"Model not loaded. Error: {model_manager.model_load_error or 'Unknown error'}. Use /reload endpoint to retry."
        )
    
    try:
        translation = model_manager.translate(
            request.text, 
            request.target_language.value,
            request.is_json
        )
        return {
            "translation": translation,
            "original": request.text,
            "target_language": request.target_language.value
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Translation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/translate/batch")
async def translate_batch(request: BatchTranslationRequest):
    """Translate multiple texts"""
    if not model_manager:
        raise HTTPException(status_code=503, detail="Model service not initialized")
    
    if model_manager.model is None:
        raise HTTPException(
            status_code=503, 
            detail=f"Model not loaded. Error: {model_manager.model_load_error or 'Unknown error'}. Use /reload endpoint to retry."
        )
    
    try:
        translations = []
        for text in request.texts:
            translation = model_manager.translate(
                text,
                request.target_language.value,
                request.is_json
            )
            translations.append({
                "original": text,
                "translation": translation
            })
        
        return {
            "translations": translations,
            "target_language": request.target_language.value,
            "count": len(translations)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Batch translation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/config")
async def get_config():
    """Get current configuration"""
    if not model_manager:
        raise HTTPException(status_code=503, detail="Model service not initialized")
    return model_manager.config

@app.put("/config")
async def update_config(request: ConfigUpdate):
    """Update entire configuration"""
    if not model_manager:
        raise HTTPException(status_code=503, detail="Model service not initialized")
    
    try:
        if model_manager.save_config(request.config):
            if model_manager.load_model():
                return {
                    "message": "Configuration updated and model reloaded successfully",
                    "config": request.config
                }
            else:
                return {
                    "message": "Configuration saved but model reload failed",
                    "config": request.config,
                    "model_error": model_manager.model_load_error
                }
        else:
            raise HTTPException(status_code=500, detail="Failed to save configuration")
    except Exception as e:
        logger.error(f"Config update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/config/memory")
async def update_memory_config(request: MemoryConfig):
    """Update memory configuration"""
    if not model_manager:
        raise HTTPException(status_code=503, detail="Model service not initialized")
    
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
                    "cpu_memory": request.cpu_memory
                }
            else:
                return {
                    "message": "Configuration saved but model reload failed",
                    "gpu_memory": request.gpu_memory,
                    "cpu_memory": request.cpu_memory,
                    "model_error": model_manager.model_load_error
                }
    except Exception as e:
        logger.error(f"Memory config update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/config/glossary")
async def update_glossary(request: GlossaryUpdate):
    """Update glossary"""
    if not model_manager:
        raise HTTPException(status_code=503, detail="Model service not initialized")
    
    try:
        model_manager.config['glossary'] = request.terms
        
        if model_manager.save_config(model_manager.config):
            return {
                "message": "Glossary updated successfully",
                "glossary": request.terms
            }
    except Exception as e:
        logger.error(f"Glossary update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/config/glossary")
async def delete_glossary():
    """Delete glossary"""
    if not model_manager:
        raise HTTPException(status_code=503, detail="Model service not initialized")
    
    try:
        model_manager.config['glossary'] = {}
        
        if model_manager.save_config(model_manager.config):
            return {"message": "Glossary deleted successfully"}
    except Exception as e:
        logger.error(f"Delete glossary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/config/generation")
async def update_generation_params(request: GenerationParams):
    """Update generation parameters"""
    if not model_manager:
        raise HTTPException(status_code=503, detail="Model service not initialized")
    
    try:
        # Update only provided parameters
        params_dict = request.dict(exclude_none=True)
        model_manager.config['translation']['generation_params'].update(params_dict)
        
        if model_manager.save_config(model_manager.config):
            return {
                "message": "Generation parameters updated successfully",
                "params": params_dict
            }
    except Exception as e:
        logger.error(f"Generation params update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/memory")
async def get_memory_usage():
    """Get memory usage statistics"""
    if not model_manager:
        raise HTTPException(status_code=503, detail="Model service not initialized")
    return model_manager.get_memory_usage()

@app.post("/reload")
async def reload_model():
    """Reload the model"""
    if not model_manager:
        raise HTTPException(status_code=503, detail="Model service not initialized")
    
    try:
        if model_manager.load_model():
            return {"message": "Model reloaded successfully"}
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Model reload failed. Error: {model_manager.model_load_error or 'Unknown error'}"
            )
    except Exception as e:
        logger.error(f"Model reload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/free_memory")
async def free_gpu_memory():
    """Free GPU memory"""
    if not model_manager:
        raise HTTPException(status_code=503, detail="Model service not initialized")
    
    try:
        result = model_manager.free_memory()
        return result
    except Exception as e:
        logger.error(f"Free memory error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, workers=1)