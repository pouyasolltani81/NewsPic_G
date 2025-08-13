from django.apps import AppConfig
import sys
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
from threading import Lock

class TranslationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Translate'
    
    _model = None
    _tokenizer = None
    _lock = Lock()
    
    @classmethod
    def get_model_and_tokenizer(cls):
        """Get model and tokenizer, loading them if necessary"""
        if cls._model is None:
            with cls._lock:
                # Double-check after acquiring lock
                if cls._model is None:
                    cls._load_translation_model()
        return cls._model, cls._tokenizer
    
    @classmethod
    def _load_translation_model(cls):
        try:
            m2m100_418M_PATH = "/home/anews/PS/translate/m2m100_418M"
            
            if m2m100_418M_PATH not in sys.path:
                sys.path.append(m2m100_418M_PATH)
            
            print("Loading translation model...")
            cls._model = M2M100ForConditionalGeneration.from_pretrained(m2m100_418M_PATH)
            cls._tokenizer = M2M100Tokenizer.from_pretrained(m2m100_418M_PATH)
            print("Translation model loaded successfully!")
            
        except Exception as e:
            print(f"Failed to load translation model: {e}")
            raise e