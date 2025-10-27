import json
import torch
import os
import gc
import traceback
from typing import Dict, Any, Optional
from transformers import AutoTokenizer, AutoModelForCausalLM
from threading import Lock
import logging

logger = logging.getLogger(__name__)

class TranslationModelManager:
    """Singleton manager for the translation model"""
    _instance = None
    _lock = Lock()
    _initialized = False
    _instance_count = 0  # Track instance attempts
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance_count += 1
                logger.info(f"Creating NEW TranslationModelManager instance (count: {cls._instance_count})")
                logger.info(f"Called from: {traceback.format_stack()[-2]}")
            else:
                logger.info(f"Returning EXISTING TranslationModelManager instance")
            return cls._instance
    
    def __init__(self):
        # Only initialize once
        if not TranslationModelManager._initialized:
            with TranslationModelManager._lock:
                if not TranslationModelManager._initialized:
                    logger.info("Initializing TranslationModelManager...")
                    self.model = None
                    self.tokenizer = None
                    self.config = None
                    self.config_path = "/home/anews/NewsPic_G/BackBoiler/src/Translate/config.json"
                    self.load_config()
                    self.load_model()
                    TranslationModelManager._initialized = True
                    logger.info("TranslationModelManager initialization complete")
                else:
                    logger.info("TranslationModelManager already initialized, skipping...")
    
    def free_gpu_memory(self) -> Dict[str, Any]:
        """Completely free GPU memory"""
        logger.info("Freeing GPU memory...")
        result = {"status": "started", "steps": []}
        
        try:
            # Step 1: Delete model
            if hasattr(self, 'model') and self.model is not None:
                del self.model
                self.model = None
                result["steps"].append("Model deleted")
                logger.info("Model deleted")
            
            # Step 2: Delete tokenizer
            if hasattr(self, 'tokenizer') and self.tokenizer is not None:
                del self.tokenizer
                self.tokenizer = None
                result["steps"].append("Tokenizer deleted")
                logger.info("Tokenizer deleted")
            
            # Step 3: Run garbage collection
            gc.collect()
            result["steps"].append("Garbage collection completed")
            logger.info("Garbage collection completed")
            
            # Step 4: Clear CUDA cache
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                result["steps"].append("CUDA cache cleared")
                logger.info("CUDA cache cleared")
                
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
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logger.info("Configuration loaded successfully")
            return self.config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            raise
    
    def save_config(self, new_config: Dict[str, Any]) -> bool:
        """Save new configuration to JSON file"""
        try:
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
                self.free_gpu_memory()
            
            model_config = self.config['model']
            
            # Convert string dtype to torch dtype
            dtype_map = {
                'bfloat16': torch.bfloat16,
                'float16': torch.float16,
                'float32': torch.float32
            }
            torch_dtype = dtype_map.get(model_config['torch_dtype'], torch.bfloat16)
            
            # Prepare max_memory dict
            max_memory = {}
            if 'gpu' in model_config['max_memory']:
                max_memory[0] = model_config['max_memory']['gpu']
            if 'cpu' in model_config['max_memory']:
                max_memory['cpu'] = model_config['max_memory']['cpu']
            
            logger.info(f"Loading model from {model_config['model_id']}")
            logger.info(f"Memory allocation - GPU: {max_memory.get(0, 'auto')}, CPU: {max_memory.get('cpu', 'auto')}")
            
            # Load model
            self.model = AutoModelForCausalLM.from_pretrained(
                model_config['model_id'],
                torch_dtype=torch_dtype,
                device_map=model_config['device_map'],
                max_memory=max_memory,
                offload_folder=model_config['offload_folder'],
                offload_state_dict=model_config['offload_state_dict'],
                low_cpu_mem_usage=model_config['low_cpu_mem_usage'],
                trust_remote_code=True
            )
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(model_config['model_id'])
            
            # Set padding token if needed
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            logger.info("Model loaded successfully")
            
            # Log memory usage after loading
            if torch.cuda.is_available():
                logger.info(f"GPU memory after loading - Allocated: {torch.cuda.memory_allocated(0) / 1024**3:.2f} GB, Reserved: {torch.cuda.memory_reserved(0) / 1024**3:.2f} GB")
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def reload_model(self) -> bool:
        """Reload the model with updated configuration"""
        try:
            logger.info("Reloading model...")
            return self.load_model()
        except Exception as e:
            logger.error(f"Error reloading model: {e}")
            return False
    
    def delete_glossary(self) -> bool:
        """Delete the glossary from configuration"""
        try:
            if 'glossary' in self.config:
                del self.config['glossary']
                logger.info("Glossary deleted from config")
            else:
                self.config['glossary'] = {}
                logger.info("Glossary was already empty")
            
            # Save the updated config
            return self.save_config(self.config)
        except Exception as e:
            logger.error(f"Error deleting glossary: {e}")
            return False
    
    def translate(self, text: str, is_json: bool = False) -> str:
        """Translate text using the loaded model"""
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Model not loaded")
        
        try:
            # Build system prompt
            trans_config = self.config['translation']
            system = [f"Translate the user's text to {trans_config['target_language']}."]
            
            for key, value in trans_config['context'].items():
                key_pascal = key.capitalize()
                system.append(f"{key_pascal}: {value}")
            
            # Add glossary if exists
            if 'glossary' in self.config and self.config['glossary']:
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
            gen_params = trans_config['generation_params']
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
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current GPU/CPU memory usage"""
        memory_info = {
            "instance_count": self._instance_count,
            "is_model_loaded": self.model is not None,
            "is_tokenizer_loaded": self.tokenizer is not None,
        }
        
        if torch.cuda.is_available():
            memory_info['gpu_allocated_gb'] = torch.cuda.memory_allocated(0) / 1024**3
            memory_info['gpu_reserved_gb'] = torch.cuda.memory_reserved(0) / 1024**3
            memory_info['gpu_total_gb'] = torch.cuda.get_device_properties(0).total_memory / 1024**3
        
        # Add CPU memory info (requires psutil)
        try:
            import psutil
            process = psutil.Process()
            memory_info['cpu_memory_gb'] = process.memory_info().rss / 1024**3
            memory_info['cpu_percent'] = process.memory_percent()
        except ImportError:
            pass
        
        return memory_info
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance"""
        if cls._instance is None:
            return cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """Completely reset the singleton instance"""
        with cls._lock:
            logger.info("Resetting TranslationModelManager instance...")
            if cls._instance:
                cls._instance.free_gpu_memory()
            cls._instance = None
            cls._initialized = False
            cls._instance_count = 0
            logger.info("TranslationModelManager instance reset complete")

# Create a module-level instance
_model_manager_instance = None

def get_model_manager():
    """Get the singleton model manager instance"""
    global _model_manager_instance
    if _model_manager_instance is None:
        _model_manager_instance = TranslationModelManager()
    return _model_manager_instance