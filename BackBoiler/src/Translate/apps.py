from django.apps import AppConfig
import sys
from transformers import M2M100ForConditionalGeneration
from transformers import MBartForConditionalGeneration, MBart50TokenizerFast

class TranslationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Translate'
    
    model = None
    tokenizer = None
    
    def ready(self):
        # This runs when Django starts
        if TranslationConfig.model is None:
            self._load_translation_model()
    
    def _load_translation_model(self):
        try:
            # Add your custom path for small100 tokenizer
            base_path = "/home/anews/PS/translate"
            SMALL100_PATH = "/home/anews/PS/translate/small100"
            if SMALL100_PATH not in sys.path:
                sys.path.append(SMALL100_PATH)
            
            from tokenization_small100 import SMALL100Tokenizer
            
            print("Loading translation model...")
            
            # TranslationConfig.model = M2M100ForConditionalGeneration.from_pretrained(SMALL100_PATH)
            # TranslationConfig.tokenizer = SMALL100Tokenizer.from_pretrained(SMALL100_PATH)
            
            
            TranslationConfig.model = MBartForConditionalGeneration.from_pretrained(f"{base_path}/mbart-large-50-many-to-many-mmt")
            TranslationConfig.tokenizer = MBart50TokenizerFast.from_pretrained(f"{base_path}/mbart-large-50-many-to-many-mmt")
            
        
            print("Translation model loaded successfully!")
            
        except Exception as e:
            print(f"Failed to load translation model: {e}")
           