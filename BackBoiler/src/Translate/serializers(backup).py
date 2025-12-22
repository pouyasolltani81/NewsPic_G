from rest_framework import serializers

# Supported languages choices
SUPPORTED_LANGUAGES = [
    ('Arabic', 'Arabic'),
    ('Bulgarian', 'Bulgarian'),
    ('Chinese', 'Chinese'),
    ('Czech', 'Czech'),
    ('Danish', 'Danish'),
    ('Dutch', 'Dutch'),
    ('English', 'English'),
    ('Finnish', 'Finnish'),
    ('French', 'French'),
    ('German', 'German'),
    ('Greek', 'Greek'),
    ('Gujarati', 'Gujarati'),
    ('Hebrew', 'Hebrew'),
    ('Hindi', 'Hindi'),
    ('Hungarian', 'Hungarian'),
    ('Indonesian', 'Indonesian'),
    ('Italian', 'Italian'),
    ('Japanese', 'Japanese'),
    ('Korean', 'Korean'),
    ('Persian', 'Persian'),
    ('Polish', 'Polish'),
    ('Portuguese', 'Portuguese'),
    ('Romanian', 'Romanian'),
    ('Russian', 'Russian'),
    ('Slovak', 'Slovak'),
    ('Spanish', 'Spanish'),
    ('Swedish', 'Swedish'),
    ('Tagalog', 'Tagalog'),
    ('Thai', 'Thai'),
    ('Turkish', 'Turkish'),
    ('Ukrainian', 'Ukrainian'),
    ('Vietnamese', 'Vietnamese'),
]

class TranslationRequestSerializer(serializers.Serializer):
    text = serializers.CharField(
        required=True,
        help_text="Text to translate",
        max_length=5000000,
        style={'base_template': 'textarea.html'}
    )
    target_language = serializers.ChoiceField(
        choices=SUPPORTED_LANGUAGES,
        required=True,
        help_text="Target language for translation"
    )
    is_json = serializers.BooleanField(
        default=False,
        help_text="Whether the text is JSON formatted"
    )

    class Meta:
        examples = {
            'simple_text': {
                'value': {
                    'text': 'Hello, how are you?',
                    'target_language': 'Persian',
                    'is_json': False
                }
            },
            'json_text': {
                'value': {
                    'text': '{"title": "News", "content": "Breaking news"}',
                    'target_language': 'Spanish',
                    'is_json': True
                }
            }
        }

class TranslationBatchRequestSerializer(serializers.Serializer):
    texts = serializers.ListField(
        child=serializers.CharField(max_length=5000000),
        required=True,
        help_text="List of texts to translate",
        min_length=1,
        max_length=100
    )
    target_language = serializers.ChoiceField(
        choices=SUPPORTED_LANGUAGES,
        required=True,
        help_text="Target language for translation"
    )
    is_json = serializers.BooleanField(
        default=False,
        help_text="Whether the texts are JSON formatted"
    )

class MemoryConfigSerializer(serializers.Serializer):
    gpu_memory = serializers.CharField(
        required=True,
        help_text="GPU memory allocation (e.g., '20GB')",
        max_length=10
    )
    cpu_memory = serializers.CharField(
        required=True,
        help_text="CPU memory allocation (e.g., '30GB')",
        max_length=10
    )

    def validate_gpu_memory(self, value):
        """Validate GPU memory format"""
        if not value.endswith('GB') and not value.endswith('MB'):
            raise serializers.ValidationError("Memory must be specified with GB or MB suffix")
        return value

    def validate_cpu_memory(self, value):
        """Validate CPU memory format"""
        if not value.endswith('GB') and not value.endswith('MB'):
            raise serializers.ValidationError("Memory must be specified with GB or MB suffix")
        return value

class GlossarySerializer(serializers.Serializer):
    terms = serializers.DictField(
        child=serializers.CharField(max_length=500),
        required=True,
        help_text="Dictionary of terms and their translations"
    )

    def validate_terms(self, value):
        """Validate glossary terms"""
        if len(value) > 1000:
            raise serializers.ValidationError("Glossary cannot contain more than 1000 terms")
        return value

class GenerationParamsSerializer(serializers.Serializer):
    max_new_tokens = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=2048,
        help_text="Maximum number of tokens to generate"
    )
    temperature = serializers.FloatField(
        required=False,
        min_value=0.1,
        max_value=2.0,
        help_text="Temperature for sampling (higher = more creative)"
    )
    do_sample = serializers.BooleanField(
        required=False,
        help_text="Whether to use sampling"
    )
    top_p = serializers.FloatField(
        required=False,
        min_value=0.1,
        max_value=1.0,
        help_text="Top-p value for nucleus sampling"
    )
    top_k = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        help_text="Top-k value for sampling"
    )

class ModelConfigSerializer(serializers.Serializer):
    model_id = serializers.CharField(
        required=True,
        help_text="Model identifier or path"
    )
    torch_dtype = serializers.ChoiceField(
        choices=['bfloat16', 'float16', 'float32'],
        required=False,
        default='bfloat16',
        help_text="PyTorch data type for model"
    )
    device_map = serializers.CharField(
        required=False,
        default='auto',
        help_text="Device mapping strategy"
    )
    max_memory = serializers.DictField(
        child=serializers.CharField(),
        required=False,
        help_text="Memory allocation per device"
    )
    offload_folder = serializers.CharField(
        required=False,
        default='offload',
        help_text="Folder for offloading model parts"
    )
    offload_state_dict = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Whether to offload state dict"
    )
    low_cpu_mem_usage = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Enable low CPU memory usage mode"
    )

class TranslationConfigSerializer(serializers.Serializer):
    target_language = serializers.ChoiceField(
        choices=SUPPORTED_LANGUAGES,
        required=False,
        default='Persian',
        help_text="Default target language"
    )
    context = serializers.DictField(
        child=serializers.CharField(),
        required=False,
        help_text="Translation context settings"
    )
    generation_params = GenerationParamsSerializer(
        required=False,
        help_text="Generation parameters for translation"
    )

class ConfigSerializer(serializers.Serializer):
    model = ModelConfigSerializer(
        required=False,
        help_text="Model configuration"
    )
    translation = TranslationConfigSerializer(
        required=False,
        help_text="Translation configuration"
    )
    glossary = serializers.DictField(
        child=serializers.CharField(),
        required=False,
        help_text="Translation glossary"
    )

    def to_internal_value(self, data):
        """Allow flexible config input"""
        # If data is already a dict with the right structure, return it
        if isinstance(data, dict):
            return data
        return super().to_internal_value(data)

# Response serializers for documentation
class TranslationResponseSerializer(serializers.Serializer):
    translation = serializers.CharField(help_text="Translated text")
    original = serializers.CharField(help_text="Original text")
    target_language = serializers.CharField(help_text="Target language used")

class BatchTranslationResponseSerializer(serializers.Serializer):
    translations = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of translation results"
    )
    target_language = serializers.CharField(help_text="Target language used")
    count = serializers.IntegerField(help_text="Number of translations")

class MemoryUsageSerializer(serializers.Serializer):
    is_model_loaded = serializers.BooleanField(help_text="Whether model is loaded")
    is_tokenizer_loaded = serializers.BooleanField(help_text="Whether tokenizer is loaded")
    gpu_allocated_gb = serializers.FloatField(help_text="GPU memory allocated in GB", required=False)
    gpu_reserved_gb = serializers.FloatField(help_text="GPU memory reserved in GB", required=False)
    gpu_total_gb = serializers.FloatField(help_text="Total GPU memory in GB", required=False)
    cpu_memory_gb = serializers.FloatField(help_text="CPU memory usage in GB", required=False)
    cpu_percent = serializers.FloatField(help_text="CPU memory percentage", required=False)
    supported_languages = serializers.ListField(
        child=serializers.CharField(),
        help_text="List of supported languages"
    )

class HealthCheckSerializer(serializers.Serializer):
    status = serializers.CharField(help_text="Service health status")
    model_service = serializers.BooleanField(help_text="Model service availability")
    model_service_details = serializers.DictField(
        help_text="Detailed model service information",
        required=False
    )

class MessageResponseSerializer(serializers.Serializer):
    message = serializers.CharField(help_text="Response message")

class ErrorResponseSerializer(serializers.Serializer):
    error = serializers.CharField(help_text="Error message")
    details = serializers.CharField(help_text="Error details", required=False)