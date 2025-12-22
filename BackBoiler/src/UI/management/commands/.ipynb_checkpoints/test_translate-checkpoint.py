# management/commands/test_translation.py
import time
import json
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from your_app.views import translate_text

User = get_user_model()

class Command(BaseCommand):
    help = 'Test translation service with various texts'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--text',
            type=str,
            default='Hello, how are you today?',
            help='Text to translate'
        )
        parser.add_argument(
            '--target',
            type=str,
            default='fa',
            help='Target language code'
        )
        parser.add_argument(
            '--long-test',
            action='store_true',
            help='Test with long text that takes time'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Testing translation service...'))
        
        # Create a mock request
        factory = RequestFactory()
        user = User.objects.first()  # Get first user for testing
        
        if options['long_test']:
            # Test with longer text
            text = """
            Artificial intelligence (AI) is intelligence demonstrated by machines, in contrast to the natural intelligence displayed by humans and animals. Leading AI textbooks define the field as the study of "intelligent agents": any device that perceives its environment and takes actions that maximize its chance of successfully achieving its goals. Colloquially, the term "artificial intelligence" is often used to describe machines that mimic "cognitive" functions that humans associate with the human mind, such as "learning" and "problem solving".
            
            As machines become increasingly capable, tasks considered to require "intelligence" are often removed from the definition of AI, a phenomenon known as the AI effect. A quip in Tesler's Theorem says "AI is whatever hasn't been done yet." For instance, optical character recognition is frequently excluded from things considered to be AI, having become a routine technology. Modern machine capabilities generally classified as AI include successfully understanding human speech, competing at the highest level in strategic game systems, autonomously operating cars, intelligent routing in content delivery networks, and military simulations.
            """ * 3  # Make it even longer
        else:
            text = options['text']
        
        request_data = {
            'text': text,
            'target_lang': options['target'],
            'wait_for_response': True  # Wait no matter how long
        }
        
        request = factory.post('/translate/', 
                              data=json.dumps(request_data),
                              content_type='application/json')
        request.user = user
        
        self.stdout.write(f"Text length: {len(text)} characters")
        self.stdout.write(f"Target language: {options['target']}")
        self.stdout.write("Sending request (NO TIMEOUT - will wait for completion)...")
        
        start_time = time.time()
        
        try:
            response = translate_text(request)
            elapsed = time.time() - start_time
            
            self.stdout.write(f"\nCompleted in {elapsed:.2f} seconds")
            
            if response.status_code == 200:
                data = json.loads(response.content)
                if data.get('return'):
                    self.stdout.write(self.style.SUCCESS('\n✓ Translation successful!'))
                    self.stdout.write(f"Original: {text[:100]}...")
                    self.stdout.write(f"Translation: {data['data']['translated_text'][:200]}...")
                    self.stdout.write(f"Translation time: {data['data'].get('translation_time', 'N/A')}s")
                else:
                    self.stdout.write(self.style.ERROR(f"\n✗ Translation failed: {data.get('error')}"))
            else:
                self.stdout.write(self.style.ERROR(f"\n✗ HTTP {response.status_code}: {response.content}"))
                
        except KeyboardInterrupt:
            elapsed = time.time() - start_time
            self.stdout.write(self.style.WARNING(f"\n\nInterrupted after {elapsed:.2f} seconds"))
            self.stdout.write("The translation is still running on the server...")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n✗ Error: {e}"))