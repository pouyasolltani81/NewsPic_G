import os
import sys
import json
import time
import torch
import requests
import argparse
import hashlib
from PIL import Image
import matplotlib.pyplot as plt
from typing import List, Tuple, Optional, Dict, Any, Set
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, validator, HttpUrl, SecretStr
from enum import Enum
import gc
from PIL import ImageDraw, ImageFont, ImageStat


def clear_gpu_memory():
    """Clear GPU memory"""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    gc.collect()

# Set memory allocation configuration
import os
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'

# Clear memory before starting
clear_gpu_memory()

# =============================
# Pydantic Models for News API
# =============================

class NewsCategory(str, Enum):
    CRYPTOCURRENCIES = "cryptocurrencies"
    BLOCKCHAIN = "blockchain"
    DEFI = "defi"
    NFT = "nft"

class SortOrder(str, Enum):
    ASCENDING = "1"
    DESCENDING = "-1"

class NewsApiRequest(BaseModel):
    """Model for news API request parameters"""
    symbols: str = Field(default="all")
    startDate: int = Field(default=1716373411)
    category: str = Field(default="cryptocurrencies")
    llmOnly: bool = Field(default=True)
    language: str = Field(default="en", pattern="^[a-z]{2}$")
    page: int = Field(default=1, ge=1)
    pageLimit: int = Field(default=10, ge=1, le=100)
    filterBy: str = Field(default="")
    filterValue: str = Field(default="")
    sortBy: str = Field(default="pubDate")
    sortValue: str = Field(default="-1")
    
    
    
class UpdateNewsApiRequest(BaseModel):
    id: str = Field(..., alias="_id")
    image_url: str

    class Config:
        populate_by_name = True 
    
class ClusterInfo(BaseModel):
    """Model for cluster information"""
    cluster_category: Optional[str] = Field(default=None)
    
class NewsItem(BaseModel):
    """Model for individual news items"""
    id: str = Field(..., alias="_id")
    title: str = Field(..., min_length=10)
    summaryEn: str = Field(..., min_length=10)
    
    link: Optional[str] = Field(default=None)  # Add this field
    keywords: List[str] = Field(default_factory=list, alias="keywords")  # Note: API uses 'keywords' not 'tag'
    tag: List[str] = Field(default_factory=list)  # Keep this for backward compatibility
    cluster_info: Optional[ClusterInfo] = Field(default=None)
    
    class Config:
        extra = "allow"  # Allow extra fields
        populate_by_name = True 
    
    @validator('title')
    def clean_title(cls, v):
        return v.strip()
    
    @property
    def tags(self) -> List[str]:
        """Get tags from either tag or keywords field"""
        return self.tag or self.keywords or []
        
class NewsApiResponse(BaseModel):
    """Model for news API response"""
    results: List[NewsItem]
    total: Optional[int] = None
    page: Optional[int] = None

# =============================
# Pydantic Models for Image Generation
# =============================

class PromptResponse(BaseModel):
    """Model for the prompt response from the API"""
    prompt: str = Field(..., min_length=1)
    negative_prompt: str = Field(..., min_length=1)
    
    @validator('prompt', 'negative_prompt')
    def validate_prompts(cls, v):
        if not v.strip():
            raise ValueError("Prompt cannot be empty or just whitespace")
        return v.strip()

class ChatMessage(BaseModel):
    """Model for chat messages"""
    role: str = Field(..., pattern="^(system|user|assistant)$")
    content: str = Field(..., min_length=1)

class ChatCompletionRequest(BaseModel):
    """Model for the chat completion API request"""
    model: str = Field(default="Qwen/Qwen2.5-14B-Instruct")
    messages: List[ChatMessage]
    temperature: Optional[float] = Field(default=0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=500, ge=1)

class ImageGenerationParams(BaseModel):
    """Model for image generation parameters"""
    prompt: str = Field(..., min_length=1)
    negative_prompt: str = Field(..., min_length=1)
    height: int = Field(default=1069, ge=64, le=2048)
    width: int = Field(default=1900, ge=64, le=2048)
    seed: int = Field(default=42)
    
    @validator('height', 'width')
    def validate_dimensions(cls, v):
        if v % 8 != 0:
            raise ValueError("Image dimensions must be divisible by 8")
        return v

class Config(BaseModel):
    """Configuration model"""
    # News API Configuration
    news_api_url: HttpUrl = Field(default="https://news.imoonex.ir/News/GetPaginatedData/")
    update_news_api_url: HttpUrl = Field(default="https://news.imoonex.ir/News/UpdateNews/")
    
    news_api_token: SecretStr = Field(..., description="Authentication token for news API")
    
    # Prompt Generation API Configuration
    prompt_api_url: HttpUrl = Field(default="http://79.175.177.113:17800/v1/chat/completions")
    
    # General Configuration
    output_dir: str = Field(default="crypto_news_images")
    timeout: int = Field(default=30, ge=1)
    max_titles: int = Field(default=6, ge=1, le=20)
    style: Optional[str] = Field(default=None)
    
    system_prompt: str = Field(default=(
    "You are an expert at creating image generation prompts for crypto news editorial illustrations. "
    "Your prompts must follow these strict rules:\n\n"
    
    "LOGO RULES:\n"
    "- ONLY use Bitcoin logo for Bitcoin-specific or general crypto news\n"
    "- ONLY use Ethereum logo for Ethereum-specific or general crypto news\n"
    "- For ALL other cryptocurrencies: use abstract symbols, geometric shapes, or metaphorical representations\n"
    "- NEVER use Bitcoin/Ethereum logos for other coins specific news symbols\n\n"
    
    "VISUAL REQUIREMENTS:\n"
    "- Create symbolic, metaphorical imagery based on the news sentiment and context\n"
    "- Use economic and financial visual metaphors (bulls, bears, charts, vaults, etc.)\n"
    "- Consider the tags and category to inform the visual theme\n"
    "- Focus on mood, emotion, and abstract concepts rather than literal representations\n\n"
    
    "STRICT PROHIBITIONS:\n"
    "- NO text, numbers, letters, or written words anywhere in the image\n"
    "- NO UI elements, screenshots, or app interfaces\n"
    "- NO specific coin logos except Bitcoin/Ethereum when explicitly mentioned\n"
    "- NO cluttered or overly complex compositions\n\n"
    
    "NEGATIVE PROMPT MUST INCLUDE:\n"
    "- 'text, words, letters, numbers, writing, typography, logos, UI, interface'\n"
    "- Plus any specific elements to avoid based on the context\n\n"
    
    "Output only a JSON object with 'prompt' and 'negative_prompt' keys."
    ))

# =============================
# Service Classes
# =============================

class NewsApiClient:
    """Client for fetching news from the API"""
    
    def __init__(self, config: Config):
        self.config = config
        self.headers = {
            "Accept": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": "d4735e3a265e16ee2393953",
        }
    
    def fetch_news(self, request_params: NewsApiRequest) -> List[NewsItem]:
        """Fetch news items from the API"""
        try:
            response = requests.post(
                str(self.config.news_api_url),
                headers=self.headers,
                json=request_params.dict(),
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            results_list = data['data']['result']
            
            # Create NewsApiResponse with the results list
            news_response = NewsApiResponse(results=results_list)
            
            # Limit the number of titles
            return news_response.results[:self.config.max_titles]
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching news: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            raise
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise
        

class UpdateNewsApiClient:
    """Client for fetching news from the API"""
    
    def __init__(self, config: Config):
        self.config = config
        self.headers = {
            "Accept": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": "96fd30916bb6fafe293b182a0f400df8",
        }
    
    def update_news(self, request_params: UpdateNewsApiRequest):  # Rename from fetch_news
        """Update news item with image URL"""
        try:
            response = requests.post(
                str(self.config.update_news_api_url),
                headers=self.headers,
                json=request_params.dict(),
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            if 'data' in data and 'message' in data['data']:
                update_message = data['data']['message']
                print(f"Update response: {update_message}")
            else:
                print(f"Update response: {data}")
                
        except requests.exceptions.RequestException as e:
            print(f"Error updating news: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            raise
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise

class PromptGenerator:
    """Service for generating prompts from the API"""
    
    def __init__(self, config: Config):
        self.config = config

    def get_prompts_from_qwen(self, title: str, tags: List[str] = None, cluster: str = None) -> Tuple[str, str]:
        """Get prompts from Qwen API"""
        # Build comprehensive context
        context_parts = [f"Title: {title}"]
        
        if tags:
            context_parts.append(f"Tags: {', '.join(tags)}")
            # Identify if it's about a specific coin
            coin_tags = [tag.lower() for tag in tags]
            if any(coin in coin_tags for coin in ['bitcoin', 'btc']):
                context_parts.append("Note: This is specifically about Bitcoin - use Bitcoin logo")
            elif any(coin in coin_tags for coin in ['ethereum', 'eth']):
                context_parts.append("Note: This is specifically about Ethereum - use Ethereum logo")
            else:
                # Check for other specific coins
                known_coins = ['solana', 'cardano', 'ripple', 'xrp', 'dogecoin', 'shiba', 'bnb', 'polygon', 'avalanche']
                mentioned_coins = [tag for tag in coin_tags if any(coin in tag for coin in known_coins)]
                if mentioned_coins:
                    context_parts.append(f"Note: This involves {', '.join(mentioned_coins)} - use abstract symbols, NOT Bitcoin/Ethereum logos")
        
        if cluster:
            context_parts.append(f"Cluster Category: {cluster}")
            # Add cluster-specific guidance
            cluster_lower = cluster.lower()
            if 'price' in cluster_lower or 'market' in cluster_lower:
                context_parts.append("Visual theme: Market dynamics, price movements, trading")
            elif 'regulation' in cluster_lower or 'legal' in cluster_lower:
                context_parts.append("Visual theme: Legal, governmental, regulatory symbols")
            elif 'technology' in cluster_lower or 'development' in cluster_lower:
                context_parts.append("Visual theme: Innovation, technology, development")
            elif 'hack' in cluster_lower or 'security' in cluster_lower:
                context_parts.append("Visual theme: Security, protection, or breach imagery")
        
        context = "\n".join(context_parts)
        
        user_message = (
            f"Generate a news-style editorial image prompt and negative prompt for this crypto news. "
            f"Remember: NO text/numbers in the image, and follow logo rules strictly.\n\n{context}"
        )
        
        # Add style to system prompt if provided
        system_prompt = self.config.system_prompt
        if self.config.style:
            system_prompt += f"\n\nSTYLE REQUIREMENT: Apply {self.config.style} artistic style while maintaining all other rules."
        
        request = ChatCompletionRequest(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_message)
            ]
        )
        
        try:
            response = requests.post(
                str(self.config.prompt_api_url),
                json=request.dict(),
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Check if 'choices' exists
            if 'choices' not in data:
                print(f"[ERROR] 'choices' not found in response. Keys available: {list(data.keys())}")
                return "A symbolic digital crypto scene", "blurry, distorted, text, words, letters, numbers, UI"
            
            # Check if choices is not empty
            if not data['choices']:
                print(f"[ERROR] 'choices' is empty")
                return "A symbolic digital crypto scene", "blurry, distorted, text, words, letters, numbers, UI"
            
            # Get content
            content = data['choices'][0]['message']['content']
            content = content.strip()
            
            # Parse JSON response
            try:
                # First try to find JSON in the content
                if '```json' in content:
                    # Extract JSON from markdown code block
                    json_start = content.find('```json') + 7
                    json_end = content.find('```', json_start)
                    content = content[json_start:json_end].strip()
                elif '```' in content:
                    # Extract from generic code block
                    json_start = content.find('```') + 3
                    json_end = content.find('```', json_start)
                    content = content[json_start:json_end].strip()
                
                json_data = json.loads(content)
                
            except json.JSONDecodeError as e:
                print(f"[ERROR] JSON decode error: {e}")
                print(f"[ERROR] Content: {repr(content[:500])}")
                
                # Try manual extraction as fallback
                import re
                
                # Fixed regex patterns
                prompt_patterns = [
                    r'"prompt"\s*:\s*"([^"\```*(?:\\.[^"\```*)*)"',
                    r"'prompt'\s*:\s*'([^'\```*(?:\\.[^'\```*)*)'",
                ]
                
                negative_patterns = [
                    r'"negative_prompt"\s*:\s*"([^"\```*(?:\\.[^"\```*)*)"',
                    r"'negative_prompt'\s*:\s*'([^'\```*(?:\\.[^'\```*)*)'",
                ]
                
                prompt_text = None
                negative_text = None
                
                for pattern in prompt_patterns:
                    match = re.search(pattern, content, re.DOTALL)
                    if match:
                        prompt_text = match.group(1)
                        break
                
                for pattern in negative_patterns:
                    match = re.search(pattern, content, re.DOTALL)
                    if match:
                        negative_text = match.group(1)
                        break
                
                if prompt_text and negative_text:
                    json_data = {
                        "prompt": prompt_text.replace('\\"', '"').replace("\\'", "'"),
                        "negative_prompt": negative_text.replace('\\"', '"').replace("\\'", "'")
                    }
                else:
                    return "A symbolic digital crypto scene", "blurry, distorted, text, words, letters, numbers, UI"
            
            # Validate with Pydantic
            prompt_response = PromptResponse(**json_data)
            return prompt_response.prompt, prompt_response.negative_prompt
            
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Request failed for '{title}': {e}")
            return "A symbolic digital crypto scene", "blurry, distorted, text, words, letters, numbers, UI"
        except Exception as e:
            print(f"[ERROR] Unexpected error for '{title}': {type(e).__name__}: {e}")
            return "A symbolic digital crypto scene", "blurry, distorted, text, words, letters, numbers, UI"

class ImageGenerator:
    """Service for generating images"""
    
    def __init__(self, pipe):
        self.pipe = pipe
    
    def generate_image(self, params: ImageGenerationParams) -> Image.Image:
        """Generate an image based on the parameters"""
        generator = torch.manual_seed(params.seed)
        
        result = self.pipe(
            prompt=params.prompt,
            negative_prompt=params.negative_prompt,
            height=params.height,
            width=params.width,
            generator=generator
        )
        
        return result.images[0]
    
    @staticmethod
    def sanitize_filename(title: str) -> str:
        """Sanitize title for use as filename"""
        # Limit length and remove special characters
        safe_title = "".join(c if c.isalnum() or c in ' -_' else "_" for c in title[:100])
        return safe_title.strip().replace(' ', '_')

# =============================
# History Manager
# =============================

class HistoryManager:
    """Manages history of generated images with metadata"""
    
    def __init__(self, history_file: str = "generated_history.json"):
        self.history_file = history_file
        self.history: Dict[str, Dict[str, Any]] = self._load_history()
    
    def _load_history(self) -> Dict[str, Dict[str, Any]]:
        """Load history from file"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_history(self):
        """Save history to file"""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)
    
    def get_title_hash(self, title: str) -> str:
        """Get hash of title for tracking"""
        return hashlib.md5(title.encode()).hexdigest()
    
    def is_generated(self, title: str) -> bool:
        """Check if title has been generated before"""
        return self.get_title_hash(title) in self.history
    
    def add_entry(self, title: str, summaryEn: str, prompt: str, negative_prompt: str, tags: List[str], cluster: str, filepath: str):
        """Add a new entry to history with all metadata"""
        title_hash = self.get_title_hash(title)
        self.history[title_hash] = {
            "title": title,
            "summaryEn": summaryEn,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "tags": tags,
            "cluster": cluster,
            "timestamp": datetime.now().isoformat(),
            "filepath": filepath,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self._save_history()
    
    def get_all_entries(self) -> List[Dict[str, Any]]:
        """Get all entries sorted by timestamp"""
        entries = list(self.history.values())
        return sorted(entries, key=lambda x: x.get('timestamp', ''), reverse=True)

# =============================
# Pipeline Manager (NEW)
# =============================

class PipelineManager:
    """Manages loading and unloading of the diffusion pipeline"""
    
    def __init__(self, model_path: str = "./SANA1.5_4.8B_1024px_diffusers"):
        self.model_path = model_path
        self.pipe = None
        
    def load_pipeline(self):
        """Load the diffusion pipeline"""
        if self.pipe is not None:
            print("Pipeline already loaded")
            return self.pipe
            
        print("Loading diffusion model...")
        from diffusers import SanaPipeline
        
        self.pipe = SanaPipeline.from_pretrained(
            self.model_path,
            torch_dtype=torch.bfloat16,
        )
        self.pipe.to("cuda" if torch.cuda.is_available() else "cpu")
        self.pipe.text_encoder.to(torch.bfloat16)
        
        print("Model loaded successfully")
        return self.pipe
    
    def unload_pipeline(self):
        """Unload the pipeline and free memory"""
        if self.pipe is None:
            print("No pipeline to unload")
            return
            
        print("Unloading pipeline and freeing memory...")
        
        # Move model to CPU first to free GPU memory
        self.pipe.to("cpu")
        
        # Delete the pipeline
        del self.pipe
        self.pipe = None
        
        # Clear GPU cache and run garbage collection
        clear_gpu_memory()
        
        print("Pipeline unloaded and memory freed")
    
    def get_pipeline(self):
        """Get the current pipeline (load if necessary)"""
        if self.pipe is None:
            return self.load_pipeline()
        return self.pipe

# =============================
# Main Application (UPDATED)
# =============================

class CryptoNewsImageGenerator:
    """Main application class"""
    
    def __init__(self, config: Config, pipeline_manager: PipelineManager):
        self.config = config
        self.pipeline_manager = pipeline_manager
        self.news_client = NewsApiClient(config)
        self.update_news_client = UpdateNewsApiClient(config)
        self.prompt_generator = PromptGenerator(config)
        self.history_manager = HistoryManager()
        
        
       

    # Add this method to the CryptoNewsImageGenerator class
    def add_logo_to_image(self, image: Image.Image, title: str) -> Image.Image:
         # IMPORTANT: Ensure image is on CPU and in PIL format
        if hasattr(image, 'cpu'):
            image = image.cpu()
        
        # If it's a tensor, convert to PIL
        if torch.is_tensor(image):
            image = transforms.ToPILImage()(image)
        
        # Ensure it's a PIL Image
        if not isinstance(image, Image.Image):
            print(f"Warning: Image is not PIL format, it's {type(image)}")
            return image
            
        print(f"Adding logo to image for: {title[:50]}...")
        
        # Configuration
        light_logo_path = "/home/anews/PS/gan/my_concept/DarkMode.png"
        dark_logo_path = "/home/anews/PS/gan/my_concept/lightmode.png"
        strip_width_percentage = 12
        logo_opacity = 0.9
        strip_opacity = 0.7
        font_size_percentage = 50
        brightness_threshold = 128
        
        # Check if logo files exist
        if not os.path.exists(light_logo_path) or not os.path.exists(dark_logo_path):
            print("Warning: Logo files not found, returning original image")
            return image
        
        try:
            # Convert to RGBA if needed
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            main_width, main_height = image.size
            
            # Calculate strip width
            strip_width = int(main_width * (strip_width_percentage / 100))
            
            # Analyze the brightness of the left edge
            left_edge = image.crop((0, 0, strip_width, main_height))
            gray_edge = left_edge.convert('L')
            stat = ImageStat.Stat(gray_edge)
            avg_brightness = stat.mean[0]
            
            # Determine if background is dark or light
            is_dark_background = avg_brightness < brightness_threshold
            
            # Select appropriate logo and colors
            if is_dark_background:
                logo_path = light_logo_path
                text_color = '#FFFFFF'
            else:
                logo_path = dark_logo_path
                text_color = '#1F1E2E'
            
            # Create a copy of the image
            output_image = image.copy()
            
            # Create transparent strip overlay
            strip = Image.new('RGBA', (strip_width, main_height), (0, 0, 0, 0))
            strip_draw = ImageDraw.Draw(strip)
            
            # Open and resize logo
            logo = Image.open(logo_path).convert('RGBA')
            logo_size = int(strip_width * 0.3)
            logo_aspect = logo.height / logo.width
            logo_height = int(logo_size * logo_aspect)
            
            if logo_height > logo_size:
                logo_height = logo_size
                logo_size = int(logo_height / logo_aspect)
            
            logo = logo.resize((logo_size, logo_height), Image.Resampling.LANCZOS)
            
            # Rotate logo 90 degrees
            logo = logo.rotate(-90, expand=True)
            logo_size, logo_height = logo_height, logo_size
            
            # Apply opacity to logo
            if logo_opacity < 1.0:
                logo_with_opacity = Image.new('RGBA', logo.size, (0, 0, 0, 0))
                logo_with_opacity.paste(logo, (0, 0))
                logo_array = logo_with_opacity.split()
                if len(logo_array) == 4:
                    alpha = logo_array[3]
                    alpha = alpha.point(lambda p: p * logo_opacity)
                    logo_with_opacity.putalpha(alpha)
                    logo = logo_with_opacity
            
            # Position logo
            top_padding = 50
            logo_x = (strip_width - logo_size) // 2
            logo_y = top_padding
            strip.paste(logo, (logo_x, logo_y), logo)
            
            # Add text
            text = "Aimoonhub"
            font_size = int(strip_width * (font_size_percentage / 200))
            
            try:
                font_paths = [
                    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
                    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                ]
                font = None
                for font_path in font_paths:
                    if os.path.exists(font_path):
                        font = ImageFont.truetype(font_path, font_size)
                        break
                if not font:
                    font = ImageFont.load_default()
            except:
                font = ImageFont.load_default()
            
            # Create vertical text
            text_img = Image.new('RGBA', (main_height, strip_width), (0, 0, 0, 0))
            text_draw = ImageDraw.Draw(text_img)
            
            text_bbox = text_draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            text_start_y = logo_y + logo_height + 10
            text_x = text_start_y
            text_y = (strip_width - text_height) // 2
            
            # Parse text color
            if text_color.startswith('#'):
                tr = int(text_color[1:3], 16)
                tg = int(text_color[3:5], 16)
                tb = int(text_color[5:7], 16)
            else:
                tr, tg, tb = 255, 255, 255
            
            text_draw.text(
                (text_x, text_y),
                text,
                fill=(tr, tg, tb, int(255 * logo_opacity)),
                font=font
            )
            
            # Rotate text
            text_img = text_img.rotate(-90, expand=True)
            strip.paste(text_img, (0, 0), text_img)
            
            # Paste strip onto image
            output_image.paste(strip, (0, 0), strip)
            
            return output_image
            
        except Exception as e:
            print(f"Error adding logo: {e}")
            return image
    
    def run(self, news_params: Optional[NewsApiRequest] = None ):
        """Run the image generation pipeline"""
        # Load pipeline at the start of generation
        pipe = self.pipeline_manager.load_pipeline()
        image_generator = ImageGenerator(pipe)
        
        try:
            # Use default parameters if none provided
            if news_params is None:
                news_params = NewsApiRequest()
                
          
            
            print(f"\nFetching news...")
            
            # Fetch news items
            try:
                news_items = self.news_client.fetch_news(news_params)
                print(f"Fetched {len(news_items)} news items")
            except Exception as e:
                print(f"Failed to fetch news: {e}")
                return
            
            if not news_items:
                print("No news items found")
                return
            
            # Create output directory
            os.makedirs(self.config.output_dir, exist_ok=True)
            
            images = []
            fig_titles = []
            skipped_count = 0
            
            for idx, news_item in enumerate(news_items):
                
                # Check if already generated
                if self.history_manager.is_generated(news_item.title):
                    print(f"\n--- Skipping {idx + 1}/{len(news_items)}: {news_item.title} (already generated) ---")
                    skipped_count += 1
                    continue
                
                try:
                    print(f"\n--- Processing {idx + 1}/{len(news_items)}: {news_item.title} ---")
                    if news_item.tag:
                        print(f"Tags: {', '.join(news_item.tag)}")
                    
                    # Get prompts
                    prompt, negative_prompt = self.prompt_generator.get_prompts_from_qwen(
                        news_item.title, 
                        news_item.tag,
                        news_item.cluster_info.cluster_category if news_item.cluster_info else None
                    )
                    
                    print(f"Prompt: {prompt[:100]}...")
                    print(f"Negative Prompt: {negative_prompt[:100]}...")
                    
                    # Create generation parameters
                    params = ImageGenerationParams(
                        prompt=prompt,
                        negative_prompt=negative_prompt
                    )
                    
                    # Generate image
  
                    image = image_generator.generate_image(params)
                    
                    
                    # Add logo overlay
                    
                    image = self.add_logo_to_image(image, news_item.title)

                    # Save image
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_filename = ImageGenerator.sanitize_filename(news_item.title)
                    filename = f"{timestamp}_{idx}_{safe_filename}.png"
                    filepath = os.path.join(self.config.output_dir, filename)
                    image.save(filepath)
                    print(f"Saved: {filepath}")

                    
                    try:
                        # Try to find an ID field
                        news_id = None
                        for field in ['_id', 'id', 'ID', 'newsId', 'news_id']:
                            if hasattr(news_item, field):
                                news_id = getattr(news_item, field)
                                if news_id:
                                    break
                        
                        if news_id:
                            # Construct the proper image URL
                            base_url = "http://79.175.177.113:19800"
                            image_url = f"{base_url}/crypto_news_images/{filename}"
                            
                            update_news_params = UpdateNewsApiRequest(
                                _id=news_id,
                                image_url=image_url
                            )
                            print('works till update')
                            self.update_news_client.update_news(update_news_params)
                            print(f"Updated news item {news_id} with image URL: {image_url}")
                        else:
                            print("Warning: No ID field found in news item, skipping update")
                            print(f"Available fields: {news_item.dict().keys()}")
                            
                    except Exception as e:
                        print(f"Failed to update news item: {e}")
                        import traceback
                        traceback.print_exc()
                       

                    # Save metadata to history
                    self.history_manager.add_entry(
                        title=news_item.title,
                        summaryEn=news_item.summaryEn,
                        
                        prompt=prompt,
                        negative_prompt=negative_prompt,
                        tags=news_item.tag,
                        cluster=(news_item.cluster_info.cluster_category 
                            if news_item.cluster_info and news_item.cluster_info.cluster_category 
                            else "uncategorized"),
                        filepath=filepath
                    )
                    
                    # Collect for display
                    images.append(image)
                    fig_titles.append(news_item.title)
                    
                except Exception as e:
                    print(f"Error processing '{news_item.title}': {e}")
                    continue
            
            print(f"\nSummary: Generated {len(images)} new images, skipped {skipped_count} already generated")
            
            # Display results
            if images:
                self._display_images(images, fig_titles)
                
        finally:
            # Always unload pipeline after generation is complete
            self.pipeline_manager.unload_pipeline()
            
    def export_history_report(self, report_file: str = "generation_report.json"):
        """Export a detailed report of all generated images"""
        entries = self.history_manager.get_all_entries()
        report = {
            "total_generated": len(entries),
            "last_updated": datetime.now().isoformat(),
            "entries": entries
        }
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Exported history report to {report_file}")  
        
    def _display_images(self, images: List[Image.Image], titles: List[str]):
        """Display generated images with matplotlib"""
        if not images:
            print("No images to display")
            return
        
        # Calculate grid dimensions
        n_images = len(images)
        cols = min(3, n_images)
        rows = (n_images + cols - 1) // cols
        
        plt.figure(figsize=(6 * cols, 5 * rows))
        for idx, (img, title) in enumerate(zip(images, titles)):
            plt.subplot(rows, cols, idx + 1)
            plt.imshow(img)
            plt.axis("off")
            # Truncate title for display
            display_title = title[:60] + "..." if len(title) > 60 else title
            plt.title(display_title, fontsize=9, wrap=True)
        plt.tight_layout()
        plt.show()

# =============================
# Utility Functions
# =============================

def parse_interval(interval_str: str) -> int:
    """Parse interval string (e.g., '2h', '30m', '1d') to seconds"""
    if not interval_str:
        return 0
    
    # Extract number and unit
    import re
    match = re.match(r'^(\d+)([hmd]?)$', interval_str.lower())
    if not match:
        raise ValueError(f"Invalid interval format: {interval_str}. Use format like '2h', '30m', or '1d'")
    
    number = int(match.group(1))
    unit = match.group(2) or 'h'  # Default to hours
    
    multipliers = {
        'm': 60,           # minutes
        'h': 60 * 60,      # hours
        'd': 60 * 60 * 24  # days
    }
    
    return number * multipliers[unit]

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Generate images for crypto news with custom styling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python makeNewsImage.py                    # Default: no style, 6 images, no repeat
  python makeNewsImage.py anime              # Anime style, 6 images, no repeat
  python makeNewsImage.py anime 10           # Anime style, 10 images, no repeat
  python makeNewsImage.py anime 10 2h        # Anime style, 10 images, repeat every 2 hours
  python makeNewsImage.py "" 10 30m          # No style, 10 images, repeat every 30 minutes
  python makeNewsImage.py cyberpunk 5 1d     # Cyberpunk style, 5 images, repeat daily
        """
    )
    
    parser.add_argument('style', nargs='?', default=None, 
                       help='Style for image generation (e.g., anime, cyberpunk, realistic). Use "" for no style.')
    parser.add_argument('count', nargs='?', type=int, default=6,
                       help='Number of news items to fetch and generate (default: 6)')
    parser.add_argument('interval', nargs='?', default=None,
                       help='Interval between fetches (e.g., 2h, 30m, 1d). If not provided, runs once.')
    
    args = parser.parse_args()
    
    # Handle empty string style
    if args.style == "":
        args.style = None
    
    return args

# =============================
# Main Function (UPDATED)
# =============================

def main():
    """Main function with command line argument support"""
    try:
        args = parse_arguments()
        
        # Parse interval if provided
        interval_seconds = 0
        if args.interval:
            try:
                interval_seconds = parse_interval(args.interval)
                print(f"Will repeat every {args.interval}")
            except ValueError as e:
                print(f"Error: {e}")
                sys.exit(1)
        
        # Create pipeline manager
        pipeline_manager = PipelineManager()
        
        # Create configuration
        config = Config(
            news_api_token="d4735e3a265e16ee2393953",
            max_titles=args.count,
            output_dir="crypto_news_images",
            style=args.style
        )
        
        if args.style:
            print(f"Using style: {args.style}")
        print(f"Will generate {args.count} images per run")
        
        # Create news parameters
        news_params = NewsApiRequest(
            symbols="all",
            startDate=1716373411,
            category="cryptocurrencies",
            llmOnly=True,
            language="en",
            page=1,
            pageLimit=args.count,
            sortBy="pubDate",
            sortValue="-1"
        )
        
        # Initialize generator with pipeline manager
        app = CryptoNewsImageGenerator(config, pipeline_manager)
        
        # Run once or in a loop
        if interval_seconds > 0:
            print(f"\nStarting continuous generation with {args.interval} intervals...")
            print("Note: Pipeline will be unloaded between runs to free memory")
            
            while True:
                try:
                    print(f"\n{'='*60}")
                    print(f"Run started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"{'='*60}")
                    
                    app.run(news_params)
                    
                    print(f"\nPipeline unloaded. Memory is now free for other tasks.")
                    print(f"Waiting {args.interval} until next run...")
                    print(f"Next run at: {(datetime.now() + timedelta(seconds=interval_seconds)).strftime('%Y-%m-%d %H:%M:%S')}")
                    print("Press Ctrl+C to stop")
                    
                    time.sleep(interval_seconds)
                    
                except KeyboardInterrupt:
                    print("\n\nStopping continuous generation...")
                    break
                except Exception as e:
                    print(f"\nError during run: {e}")
                    import traceback
                    traceback.print_exc()
                    print(f"Waiting {args.interval} before retry...")
                    time.sleep(interval_seconds)
        else:
            # Run once
            app.run(news_params)
            print("\nGeneration complete. Pipeline unloaded and memory freed.")
            
    except Exception as e:
        print(f"\nFATAL ERROR in main: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()