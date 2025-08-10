from django.apps import AppConfig
import subprocess
import os
import threading

class NewsPictureGeneratorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'News_Picture_Generator'



# class NewsPictureGeneratorConfig(AppConfig):
#    default_auto_field = 'django.db.models.BigAutoField'
#    name = 'News_Picture_Generator'
#    
#    def ready(self):
#        # Only run in the main process (not in migrations or other commands)
#        if os.environ.get('RUN_MAIN') == 'true':
#            # Start the image generation script in a separate thread
#            def run_image_generator():
#                # Adjust the path to where your makeNewsImage.py is located
#                script_path = os.path.join(
#                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
#                    'News_Picture_Generator', 
#                    'makeNewsImage.py'
#                )
#                subprocess.Popen(['python3', script_path, 'Digital_Art', '6', '30m'])
#                print("Started news image generator with Digital_Art style, 6 images, 30m interval")
#            
#            thread = threading.Thread(target=run_image_generator, daemon=True)
#            thread.start()
