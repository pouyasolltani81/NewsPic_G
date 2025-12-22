"""
Enhanced Model Service with Async Queue System and Multiple Model Instances
Run with: uvicorn model_service:app --host 0.0.0.0 --port 8001 --workers 1

ARCHITECTURE:
- 2 Model instances on GPU (~8GB each = 16GB total on 24GB RTX 3090)
- Async queue distributes requests to available workers
- File-based cache for duplicate request optimization
- Non-blocking async I/O throughout
"""
import os

# GPU optimization settings
os.environ['PYTORCH_DISABLE_CUDA_GRAPHS'] = '1'
os.environ['TORCH_CUDNN_V8_API_DISABLED'] = '1'
os.environ['TORCH_COMPILE_DISABLE'] = '1'
os.environ['TORCHINDUCTOR_DISABLE'] = '1'

import json
import torch
import gc
import traceback
import psutil
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union, Tuple
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('/home/anews/NewsPic_G/translate_services/fastapi_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# PART A: DATA CLASSES FOR QUEUE ITEMS
# ============================================================================

@dataclass
class TranslationTask:
    """
    Represents a single translation task in the queue.
    
    This is what gets put INTO the queue and what workers pull OUT.
    The Future allows the original requester to wait for the result.
    """
    task_id: str                          # Unique ID for tracking
    text: str                             # Text to translate
    target_languages: List[str]           # Languages to translate to
    is_json: bool                         # Whether to parse result as JSON
    future: asyncio.Future                # Allows awaiting the result
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/display"""
        return {
            "task_id": self.task_id,
            "text_length": len(self.text),
            "target_languages": self.target_languages,
            "is_json": self.is_json,
            "created_at": self.created_at.isoformat(),
            "age_seconds": (datetime.now() - self.created_at).total_seconds()
        }


# ============================================================================
# PART B: ASYNC TRANSLATION QUEUE
# ============================================================================

class AsyncTranslationQueue:
    """
    The core queue system that manages translation requests.
    
    HOW IT WORKS:
    1. Request comes in via /translate endpoint
    2. Request is wrapped in TranslationTask with a Future
    3. Task is put into asyncio.Queue
    4. Endpoint awaits the Future (non-blocking wait)
    5. Worker pulls task from queue
    6. Worker processes translation
    7. Worker sets Future result
    8. Original endpoint receives result and returns to client
    
    DIFFERENCE FROM ORIGINAL:
    - Original: Used threading.RLock which BLOCKED the thread
    - New: Uses asyncio.Queue which YIELDS control while waiting
    
    WHAT THIS MEANS:
    - Original: If 10 requests came in, 9 threads sat doing nothing
    - New: If 10 requests come in, all 10 can do preprocessing while waiting
    """
    
    def __init__(self, maxsize: int = 100):
        # The actual queue - holds TranslationTask objects
        self.queue: asyncio.Queue[TranslationTask] = asyncio.Queue(maxsize=maxsize)
        
        # Statistics tracking
        self.stats = {
            "total_enqueued": 0,
            "total_completed": 0,
            "total_failed": 0,
            "current_queue_size": 0,
            "peak_queue_size": 0,
            "total_wait_time_ms": 0,
            "avg_wait_time_ms": 0
        }
        
        # For tracking what's currently being processed
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.lock = asyncio.Lock()  # Protects stats and active_tasks
        
        logger.info(f"AsyncTranslationQueue initialized with maxsize={maxsize}")
    
    async def enqueue(self, text: str, target_languages: List[str], 
                      is_json: bool = False) -> TranslationTask:
        """
        Add a translation request to the queue.
        
        Returns a TranslationTask that can be awaited for the result.
        
        FLOW:
        1. Create unique task ID
        2. Create Future (a placeholder for the eventual result)
        3. Wrap everything in TranslationTask
        4. Put task in queue
        5. Return task (caller will await task.future)
        """
        task_id = str(uuid.uuid4())[:8]
        
        # Create a Future - this is like a "promise" that will hold the result later
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        
        # Create the task object
        task = TranslationTask(
            task_id=task_id,
            text=text,
            target_languages=target_languages,
            is_json=is_json,
            future=future
        )
        
        # Put in queue (this might wait if queue is full, but it yields, doesn't block)
        await self.queue.put(task)
        
        # Update statistics
        async with self.lock:
            self.stats["total_enqueued"] += 1
            self.stats["current_queue_size"] = self.queue.qsize()
            if self.stats["current_queue_size"] > self.stats["peak_queue_size"]:
                self.stats["peak_queue_size"] = self.stats["current_queue_size"]
        
        logger.info(f"[QUEUE] Task {task_id} enqueued. Queue size: {self.queue.qsize()}")
        
        return task
    
    async def dequeue(self) -> TranslationTask:
        """
        Get the next task from the queue.
        
        This is called by worker coroutines.
        If queue is empty, this waits (yields) until a task is available.
        """
        task = await self.queue.get()
        
        async with self.lock:
            self.stats["current_queue_size"] = self.queue.qsize()
            self.active_tasks[task.task_id] = {
                "task_id": task.task_id,
                "text_length": len(task.text),
                "languages": task.target_languages,
                "dequeued_at": datetime.now().isoformat()
            }
        
        wait_time = (datetime.now() - task.created_at).total_seconds() * 1000
        logger.info(f"[QUEUE] Task {task.task_id} dequeued after {wait_time:.1f}ms wait")
        
        return task
    
    async def mark_completed(self, task_id: str, success: bool = True):
        """Mark a task as completed and update stats"""
        async with self.lock:
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
            
            if success:
                self.stats["total_completed"] += 1
            else:
                self.stats["total_failed"] += 1
        
        self.queue.task_done()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        return {
            "queue_size": self.queue.qsize(),
            "active_tasks": list(self.active_tasks.values()),
            "stats": self.stats.copy()
        }


# ============================================================================
# PART C: ASYNC CACHE MANAGER
# ============================================================================

class AsyncCacheManager:
    """
    Manages the translation cache with async file I/O.
    
    WHY ASYNC FILE I/O MATTERS:
    - Original: open(file).read() BLOCKS the event loop
    - New: run_in_executor() runs file I/O in a thread pool
    
    WHAT BLOCKING MEANS:
    - When you call open().read(), Python stops and waits
    - In async code, this stops ALL coroutines, not just yours
    - With run_in_executor, other coroutines can run while file I/O happens
    
    CACHE STRUCTURE:
    {
        "cache": {
            "md5_hash": {
                "result": {...translation result...},
                "timestamp": "2024-01-15T10:30:00",
                "text_length": 150,
                "languages": ["Persian", "Spanish"]
            }
        },
        "stats": {"hits": 0, "misses": 0}
    }
    """
    
    def __init__(self, cache_path: str = "/home/anews/NewsPic_G/translate_services/translation_cache.json"):
        self.cache_path = cache_path
        self.lock = asyncio.Lock()  # Async lock for thread-safe cache access
        self._ensure_file_exists()
        logger.info(f"AsyncCacheManager initialized at {cache_path}")
    
    def _ensure_file_exists(self):
        """Create cache file if it doesn't exist"""
        if not os.path.exists(self.cache_path):
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump({"cache": {}, "stats": {"hits": 0, "misses": 0}}, f)
            logger.info(f"Created new cache file: {self.cache_path}")
    
    def _generate_key(self, text: str, target_languages: List[str], is_json: bool) -> str:
        """
        Generate a unique cache key for this translation request.
        
        Uses MD5 hash of: text + sorted languages + is_json flag
        This ensures same request always gets same key.
        """
        # Sort languages so ["Spanish", "Persian"] == ["Persian", "Spanish"]
        content = f"{text}|{'|'.join(sorted(target_languages))}|{is_json}"
        return hashlib.md5(content.encode()).hexdigest()
    
    # -------------------------------------------------------------------------
    # ASYNC FILE I/O METHODS
    # These use run_in_executor to avoid blocking the event loop
    # -------------------------------------------------------------------------
    
    async def _read_cache_file(self) -> Dict[str, Any]:
        """
        Read cache file without blocking the event loop.
        
        HOW run_in_executor WORKS:
        1. Python has a ThreadPoolExecutor for background work
        2. run_in_executor runs _sync_read in a thread
        3. While the thread reads the file, other async code can run
        4. When file read completes, this coroutine resumes
        """
        loop = asyncio.get_event_loop()
        # None = use default executor (ThreadPoolExecutor)
        return await loop.run_in_executor(None, self._sync_read)
    
    def _sync_read(self) -> Dict[str, Any]:
        """Synchronous file read - runs in thread pool"""
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {
                    "cache": data.get("cache", {}),
                    "stats": data.get("stats", {"hits": 0, "misses": 0})
                }
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning(f"Cache read error: {e}, returning empty cache")
            return {"cache": {}, "stats": {"hits": 0, "misses": 0}}
    
    async def _write_cache_file(self, data: Dict[str, Any]):
        """Write cache file without blocking the event loop"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync_write, data)
    
    def _sync_write(self, data: Dict[str, Any]):
        """Synchronous file write - runs in thread pool"""
        with open(self.cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    # -------------------------------------------------------------------------
    # CACHE OPERATIONS
    # -------------------------------------------------------------------------
    
    async def get(self, text: str, target_languages: List[str], 
                  is_json: bool) -> Optional[Dict[str, Any]]:
        """
        Check if translation is in cache.
        
        Returns cached result if:
        1. Key exists in cache
        2. Cache entry is less than 24 hours old
        """
        cache_key = self._generate_key(text, target_languages, is_json)
        
        async with self.lock:
            data = await self._read_cache_file()
            
            if cache_key in data["cache"]:
                entry = data["cache"][cache_key]
                
                # Check age
                if "timestamp" in entry:
                    cached_time = datetime.fromisoformat(entry["timestamp"])
                    age = datetime.now() - cached_time
                    
                    if age < timedelta(hours=24):
                        # Cache hit!
                        data["stats"]["hits"] = data["stats"].get("hits", 0) + 1
                        await self._write_cache_file(data)
                        
                        logger.info(f"[CACHE] HIT for key {cache_key[:8]}... (age: {age})")
                        return entry["result"]
                    else:
                        logger.info(f"[CACHE] EXPIRED for key {cache_key[:8]}... (age: {age})")
            
            # Cache miss
            data["stats"]["misses"] = data["stats"].get("misses", 0) + 1
            await self._write_cache_file(data)
            
            logger.debug(f"[CACHE] MISS for key {cache_key[:8]}...")
            return None
    
    async def set(self, text: str, target_languages: List[str], 
                  is_json: bool, result: Dict[str, Any]):
        """
        Store translation result in cache.
        
        Also handles cache cleanup if size exceeds 1000 entries.
        """
        cache_key = self._generate_key(text, target_languages, is_json)
        
        async with self.lock:
            data = await self._read_cache_file()
            
            # Cleanup if too many entries
            if len(data["cache"]) > 1000:
                # Sort by timestamp, keep newest 900
                sorted_entries = sorted(
                    data["cache"].items(),
                    key=lambda x: x[1].get("timestamp", ""),
                    reverse=True
                )
                data["cache"] = dict(sorted_entries[:900])
                logger.info(f"[CACHE] Cleaned up, kept 900 newest entries")
            
            # Store new entry
            data["cache"][cache_key] = {
                "result": result,
                "timestamp": datetime.now().isoformat(),
                "text_length": len(text),
                "languages": target_languages
            }
            
            await self._write_cache_file(data)
            logger.info(f"[CACHE] Stored result for key {cache_key[:8]}...")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        async with self.lock:
            data = await self._read_cache_file()
            hits = data["stats"].get("hits", 0)
            misses = data["stats"].get("misses", 0)
            total = hits + misses
            
            return {
                "total_entries": len(data["cache"]),
                "hits": hits,
                "misses": misses,
                "hit_rate": hits / max(1, total),
                "cache_file": self.cache_path
            }
    
    async def clear(self):
        """Clear all cache entries"""
        async with self.lock:
            await self._write_cache_file({
                "cache": {},
                "stats": {"hits": 0, "misses": 0}
            })
            logger.info("[CACHE] Cleared all entries")


# ============================================================================
# PART D: ASYNC STORAGE FOR LONG-RUNNING TRANSLATIONS
# ============================================================================

class AsyncTranslationStorage:
    """
    Stores results of async translation requests (/translate/async endpoint).
    
    This is DIFFERENT from the cache:
    - Cache: Automatic, keyed by content hash, for duplicate detection
    - Storage: Explicit, keyed by UUID, for async request results
    
    FLOW:
    1. Client calls /translate/async with text
    2. Server returns UUID immediately
    3. Server processes in background, stores result here
    4. Client polls /translate/async/{uuid} to get result
    """
    
    def __init__(self, storage_path: str = "/home/anews/NewsPic_G/translate_services/async_translations.json",
                 max_entries: int = 500):
        self.storage_path = storage_path
        self.max_entries = max_entries
        self.lock = asyncio.Lock()
        self._ensure_file_exists()
        logger.info(f"AsyncTranslationStorage initialized at {storage_path}")
    
    def _ensure_file_exists(self):
        """Create storage file if it doesn't exist"""
        if not os.path.exists(self.storage_path):
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    async def _read_file(self) -> Dict[str, Any]:
        """Read storage file asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_read)
    
    def _sync_read(self) -> Dict[str, Any]:
        """Synchronous read"""
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    async def _write_file(self, data: Dict[str, Any]):
        """Write storage file asynchronously"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync_write, data)
    
    def _sync_write(self, data: Dict[str, Any]):
        """Synchronous write"""
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    async def save(self, translation_id: str, text: Union[str, List[str]],
                   translations: Dict[str, Any], target_languages: List[str],
                   metadata: Dict[str, Any] = None) -> bool:
        """Save a translation result"""
        async with self.lock:
            try:
                data = await self._read_file()
                
                # Cleanup old entries if needed
                if len(data) >= self.max_entries:
                    sorted_entries = sorted(
                        data.items(),
                        key=lambda x: x[1].get("timestamp", ""),
                        reverse=True
                    )
                    data = dict(sorted_entries[:self.max_entries - 1])
                
                data[translation_id] = {
                    "id": translation_id,
                    "original_text": text,
                    "translations": translations,
                    "target_languages": target_languages,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": metadata or {}
                }
                
                await self._write_file(data)
                logger.info(f"[STORAGE] Saved translation {translation_id}")
                return True
                
            except Exception as e:
                logger.error(f"[STORAGE] Error saving {translation_id}: {e}")
                return False
    
    async def get(self, translation_id: str) -> Optional[Dict[str, Any]]:
        """Get a translation by ID"""
        async with self.lock:
            data = await self._read_file()
            return data.get(translation_id)
    
    async def delete(self, translation_id: str) -> bool:
        """Delete a translation"""
        async with self.lock:
            data = await self._read_file()
            if translation_id in data:
                del data[translation_id]
                await self._write_file(data)
                return True
            return False
    
    async def get_all_ids(self) -> List[str]:
        """Get all translation IDs"""
        async with self.lock:
            data = await self._read_file()
            return list(data.keys())
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        async with self.lock:
            data = await self._read_file()
            timestamps = [item.get("timestamp") for item in data.values() if item.get("timestamp")]
            return {
                "total_entries": len(data),
                "max_entries": self.max_entries,
                "oldest": min(timestamps) if timestamps else None,
                "newest": max(timestamps) if timestamps else None
            }


# ============================================================================
# PART E: REQUEST TRACKER
# ============================================================================

class AsyncRequestTracker:
    """
    Tracks active and completed requests for monitoring.
    
    This is separate from the queue - it's for observability.
    """
    
    def __init__(self, history_size: int = 100):
        self.active: Dict[str, Dict[str, Any]] = {}
        self.history: deque = deque(maxlen=history_size)
        self.lock = asyncio.Lock()
    
    async def start(self, request_id: str, text_length: int, 
                    languages: List[str], worker_id: int = None):
        """Record that a request has started processing"""
        async with self.lock:
            self.active[request_id] = {
                "request_id": request_id,
                "text_length": text_length,
                "languages": languages,
                "worker_id": worker_id,
                "started_at": datetime.now().isoformat(),
                "status": "processing"
            }
    
    async def end(self, request_id: str, status: str, 
                  error: str = None, result_summary: Dict = None):
        """Record that a request has completed"""
        async with self.lock:
            if request_id in self.active:
                record = self.active.pop(request_id)
                record["ended_at"] = datetime.now().isoformat()
                record["status"] = status
                record["error"] = error
                record["result_summary"] = result_summary
                
                # Calculate duration
                started = datetime.fromisoformat(record["started_at"])
                record["duration_ms"] = (datetime.now() - started).total_seconds() * 1000
                
                self.history.append(record)
    
    async def get_active(self) -> List[Dict]:
        """Get currently active requests"""
        async with self.lock:
            return list(self.active.values())
    
    async def get_history(self, limit: int = 20) -> List[Dict]:
        """Get recent request history"""
        async with self.lock:
            return list(self.history)[-limit:]


# ============================================================================
# PART F: EXCEPTIONS
# ============================================================================

class ModelNotLoadedError(Exception):
    """Model is not loaded or unhealthy"""
    pass

class TokenLimitError(Exception):
    """Input exceeds token limit"""
    pass

class ModelMemoryError(Exception):
    """Out of GPU memory"""
    pass


# ============================================================================
# PART G: SUPPORTED LANGUAGES
# ============================================================================

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


# ============================================================================
# PART H: PYDANTIC MODELS
# ============================================================================

class StandardResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    return_: bool = Field(..., alias="return", description="Success status")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    message: Optional[str] = Field(None, description="Message")
    errors: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Errors")


class TranslationRequest(BaseModel):
    text: str = Field(..., description="Text to translate", max_length=50000)
    target_languages: List[SupportedLanguage] = Field(..., description="Target languages")
    is_json: bool = Field(False, description="Whether text is JSON")
    
    @field_validator('target_languages')
    @classmethod
    def validate_languages(cls, v):
        if not v:
            raise ValueError("At least one target language required")
        return v


class AsyncTranslationRequest(BaseModel):
    text: str = Field(..., description="Text to translate")
    target_languages: List[SupportedLanguage] = Field(..., description="Target languages")
    is_json: bool = Field(False, description="Whether text is JSON")
    
    @field_validator('target_languages')
    @classmethod
    def validate_languages(cls, v):
        if not v:
            raise ValueError("At least one target language required")
        return v


class BatchTranslationRequest(BaseModel):
    texts: List[str] = Field(..., description="List of texts")
    target_languages: List[SupportedLanguage] = Field(..., description="Target languages")
    is_json: bool = Field(False, description="Whether texts are JSON")
    
    @field_validator('target_languages')
    @classmethod
    def validate_languages(cls, v):
        if not v:
            raise ValueError("At least one target language required")
        return v


class AsyncBatchTranslationRequest(BaseModel):
    texts: List[str] = Field(..., description="List of texts")
    target_languages: List[SupportedLanguage] = Field(..., description="Target languages")
    is_json: bool = Field(False, description="Whether texts are JSON")
    
    @field_validator('target_languages')
    @classmethod
    def validate_languages(cls, v):
        if not v:
            raise ValueError("At least one target language required")
        return v


class ConfigUpdate(BaseModel):
    config: Dict[str, Any]


class GlossaryUpdate(BaseModel):
    terms: Dict[str, str]


class GenerationParams(BaseModel):
    max_new_tokens: Optional[int] = Field(None, ge=1, le=4096)
    temperature: Optional[float] = Field(None, ge=0.1, le=2.0)
    do_sample: Optional[bool] = None
    top_p: Optional[float] = Field(None, ge=0.1, le=1.0)
    top_k: Optional[int] = Field(None, ge=1, le=100)


# ============================================================================
# PART I: SINGLE MODEL INSTANCE
# ============================================================================

class ModelInstance:
    """
    A single model instance that can process translations.
    
    Each instance:
    - Has its own copy of the model on GPU
    - Has its own ID for tracking
    - Shares tokenizer (tokenizers are stateless)
    - Tracks its own statistics
    """
    
    def __init__(self, instance_id: int, model: Any, tokenizer: Any, 
                 device: torch.device, config: Dict[str, Any]):
        self.instance_id = instance_id
        self.model = model
        self.tokenizer = tokenizer
        self.device = device
        self.config = config
        self.is_busy = False
        self.stats = {
            "translations_completed": 0,
            "translations_failed": 0,
            "total_tokens_processed": 0,
            "total_time_ms": 0
        }
        logger.info(f"ModelInstance {instance_id} initialized on {device}")
    
    def translate(self, text: str, target_language: str, is_json: bool = False) -> Dict[str, Any]:
        """
        Translate text to a single language.
        
        This is the core translation logic.
        """
        result = {"success": False, "translation": None, "error": None, "error_type": None}
        
        try:
            # Build system prompt
            trans_config = self.config.get('translation', {})
            system_parts = [f"Translate the user's text to {target_language}."]
            
            if 'context' in trans_config:
                for key, value in trans_config['context'].items():
                    system_parts.append(f"{key.capitalize()}: {value}")
            
            glossary = self.config.get('glossary', {})
            if glossary and target_language == trans_config.get('target_language'):
                system_parts.append("Glossary:")
                for term, translation in glossary.items():
                    system_parts.append(f"- {term} -> {translation}")
            
            system_parts.append("Provide the final translation immediately without any other text.")
            
            messages = [
                {"role": "system", "content": "\n".join(system_parts)},
                {"role": "user", "content": text}
            ]
            
            # Tokenize
            prompt = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            
            max_input = self.config.get('translation', {}).get('max_input_tokens', 2048)
            inputs = self.tokenizer(
                prompt, return_tensors="pt", max_length=max_input, truncation=True
            ).to(self.device)
            
            input_length = inputs["input_ids"].shape[1]
            
            # Generate
            gen_params = trans_config.get('generation_params', {})
            max_new = min(gen_params.get('max_new_tokens', 512), max_input - input_length)
            
            with torch.inference_mode():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new,
                    temperature=gen_params.get('temperature', 0.7),
                    do_sample=gen_params.get('do_sample', True),
                    top_p=gen_params.get('top_p', 0.9),
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id
                )
            
            # Decode
            generated_tokens = outputs[0][input_length:]
            translation = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
            
            # Update stats
            self.stats["translations_completed"] += 1
            self.stats["total_tokens_processed"] += len(generated_tokens)
            
            # Cleanup
            del outputs, inputs
            
            # Parse JSON if requested
            if is_json:
                try:
                    translation = json.loads(translation)
                except json.JSONDecodeError:
                    pass
            
            result["success"] = True
            result["translation"] = translation
            
        except torch.cuda.OutOfMemoryError as e:
            result["error"] = f"GPU OOM: {e}"
            result["error_type"] = "GPU_OOM"
            self.stats["translations_failed"] += 1
            torch.cuda.empty_cache()
            
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = "TRANSLATION_ERROR"
            self.stats["translations_failed"] += 1
            logger.error(f"[Instance {self.instance_id}] Translation error: {e}")
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get instance statistics"""
        return {
            "instance_id": self.instance_id,
            "device": str(self.device),
            "is_busy": self.is_busy,
            **self.stats
        }


# ============================================================================
# PART J: MULTI-INSTANCE MODEL MANAGER
# ============================================================================

class MultiInstanceModelManager:
    """
    Manages multiple model instances and distributes work via queue.
    
    ARCHITECTURE:
    - Loads N model instances on GPU (default: 2)
    - Each instance is ~8GB VRAM
    - Worker coroutines pull from shared queue
    - Results are returned via Futures
    
    FLOW:
    1. Request comes in
    2. Enqueue translation task with Future
    3. Worker (running in background) pulls task
    4. Worker processes with its model instance
    5. Worker sets Future result
    6. Original request receives result
    """
    
    def __init__(self, config_path: str = "/home/anews/NewsPic_G/translate_services/config.json",
                 num_instances: int = 2):
        logger.info("=" * 60)
        logger.info(f"Initializing MultiInstanceModelManager with {num_instances} instances")
        logger.info("=" * 60)
        
        self.config_path = config_path
        self.num_instances = num_instances
        self.config = None
        self.tokenizer = None
        self.instances: List[ModelInstance] = []
        self.supported_languages = [lang.value for lang in SupportedLanguage]
        self.model_load_error = None
        self.max_input_tokens = 2048
        self.max_batch_size = 10
        
        # Queue and cache
        self.queue = AsyncTranslationQueue(maxsize=100)
        self.cache = AsyncCacheManager()
        self.storage = AsyncTranslationStorage()
        self.request_tracker = AsyncRequestTracker()
        
        # Worker tasks (will be created after loading)
        self.worker_tasks: List[asyncio.Task] = []
        self.shutdown_event = asyncio.Event()
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "queue_submissions": 0,
            "start_time": datetime.now().isoformat()
        }
        
        # Load config
        self.load_config()
        
        # Initialize GPU
        self._initialize_gpu()
    
    def _initialize_gpu(self):
        """Initialize GPU"""
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA not available!")
        
        torch.cuda.set_device(0)
        torch.cuda.empty_cache()
        
        props = torch.cuda.get_device_properties(0)
        total_memory = props.total_memory / 1024**3
        
        logger.info(f"GPU: {props.name}")
        logger.info(f"GPU Memory: {total_memory:.1f} GB")
        logger.info(f"Planned instances: {self.num_instances} x ~8GB = ~{self.num_instances * 8}GB")
        
        if total_memory < self.num_instances * 8:
            logger.warning(f"GPU might not have enough memory for {self.num_instances} instances!")
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                self.config = self._get_default_config()
                self.save_config(self.config)
            
            # Force full GPU mode
            if 'model' in self.config:
                self.config['model']['device_map'] = {"": 0}
                self.config['model'].pop('max_memory', None)
                self.config['model'].pop('offload_folder', None)
                self.config['model'].pop('offload_state_dict', None)
            
            if 'translation' in self.config:
                self.max_input_tokens = self.config['translation'].get('max_input_tokens', 2048)
                self.max_batch_size = self.config['translation'].get('max_batch_size', 10)
            
            return self.config
            
        except Exception as e:
            logger.error(f"Config load error: {e}")
            self.config = self._get_default_config()
            return self.config
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "model": {
                "model_id": "CohereForAI/aya-23-8B",
                "torch_dtype": "bfloat16",
                "device_map": {"": 0},
                "low_cpu_mem_usage": True
            },
            "translation": {
                "target_language": "Persian",
                "context": {"domain": "general", "style": "formal"},
                "generation_params": {
                    "max_new_tokens": 512,
                    "temperature": 0.7,
                    "do_sample": True,
                    "top_p": 0.9
                },
                "max_input_tokens": 2048,
                "max_batch_size": 10
            },
            "glossary": {},
            "instances": {"count": 2}
        }
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """Save configuration"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self.config = config
            return True
        except Exception as e:
            logger.error(f"Config save error: {e}")
            return False
    
    async def load_models(self) -> bool:
        """
        Load multiple model instances.
        
        IMPORTANT: This loads the model N times on GPU!
        Each instance gets its own copy.
        """
        logger.info("=" * 60)
        logger.info(f"Loading {self.num_instances} model instances - FULL GPU")
        logger.info("=" * 60)
        
        try:
            # Free existing instances
            await self.free_memory()
            
            model_config = self.config.get('model', {})
            model_id = model_config.get('model_id', 'CohereForAI/aya-23-8B')
            
            dtype_map = {
                'bfloat16': torch.bfloat16,
                'float16': torch.float16,
                'float32': torch.float32
            }
            torch_dtype = dtype_map.get(model_config.get('torch_dtype', 'bfloat16'), torch.bfloat16)
            
            logger.info(f"Model: {model_id}")
            logger.info(f"Dtype: {torch_dtype}")
            
            # Load tokenizer once (shared)
            logger.info("Loading tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            logger.info("✓ Tokenizer loaded")
            
            # Load each model instance
            for i in range(self.num_instances):
                logger.info(f"Loading model instance {i}...")
                
                model = AutoModelForCausalLM.from_pretrained(
                    model_id,
                    torch_dtype=torch_dtype,
                    device_map={"": 0},  # Full GPU
                    low_cpu_mem_usage=True,
                    trust_remote_code=True
                )
                model.eval()
                
                instance = ModelInstance(
                    instance_id=i,
                    model=model,
                    tokenizer=self.tokenizer,
                    device=torch.device("cuda:0"),
                    config=self.config
                )
                
                self.instances.append(instance)
                
                # Log memory after each instance
                allocated = torch.cuda.memory_allocated(0) / 1024**3
                logger.info(f"✓ Instance {i} loaded. GPU Memory: {allocated:.2f} GB")
            
            self.model_load_error = None
            
            # Start worker tasks
            await self._start_workers()
            
            logger.info("=" * 60)
            logger.info(f"All {self.num_instances} instances loaded successfully!")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            self.model_load_error = str(e)
            logger.error(f"Model loading failed: {e}")
            logger.error(traceback.format_exc())
            
            # Cleanup
            for instance in self.instances:
                del instance.model
            self.instances.clear()
            
            gc.collect()
            torch.cuda.empty_cache()
            
            return False
    
    async def _start_workers(self):
        """
        Start worker coroutines for each model instance.
        
        Each worker:
        1. Runs in an infinite loop
        2. Pulls tasks from shared queue
        3. Processes with its model instance
        4. Sets result on task's Future
        """
        logger.info(f"Starting {len(self.instances)} worker tasks...")
        
        for instance in self.instances:
            task = asyncio.create_task(self._worker(instance))
            self.worker_tasks.append(task)
            logger.info(f"Worker {instance.instance_id} started")
    
    async def _worker(self, instance: ModelInstance):
        """
        Worker coroutine that processes translation tasks.
        
        This runs continuously, pulling from the queue and processing.
        """
        worker_id = instance.instance_id
        logger.info(f"[Worker {worker_id}] Started and waiting for tasks")
        
        while not self.shutdown_event.is_set():
            try:
                # Wait for a task (this yields, doesn't block)
                try:
                    task = await asyncio.wait_for(
                        self.queue.dequeue(),
                        timeout=1.0  # Check shutdown every second
                    )
                except asyncio.TimeoutError:
                    continue  # Check shutdown flag and retry
                
                instance.is_busy = True
                start_time = time.perf_counter()
                
                # Track this request
                await self.request_tracker.start(
                    task.task_id, len(task.text), task.target_languages, worker_id
                )
                
                logger.info(f"[Worker {worker_id}] Processing task {task.task_id}")
                
                try:
                    # Process all languages
                    result = await self._process_task(instance, task)
                    
                    # Set the Future result (this unblocks the original awaiter)
                    if not task.future.done():
                        task.future.set_result(result)
                    
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    instance.stats["total_time_ms"] += elapsed_ms
                    
                    await self.request_tracker.end(
                        task.task_id, 
                        "success" if result["success"] else "partial",
                        result_summary={"languages": result.get("successful_languages", [])}
                    )
                    
                    await self.queue.mark_completed(task.task_id, success=result["success"])
                    
                    logger.info(f"[Worker {worker_id}] Completed task {task.task_id} in {elapsed_ms:.1f}ms")
                    
                except Exception as e:
                    logger.error(f"[Worker {worker_id}] Error processing task {task.task_id}: {e}")
                    
                    if not task.future.done():
                        task.future.set_exception(e)
                    
                    await self.request_tracker.end(task.task_id, "failed", str(e))
                    await self.queue.mark_completed(task.task_id, success=False)
                
                finally:
                    instance.is_busy = False
                    
            except asyncio.CancelledError:
                logger.info(f"[Worker {worker_id}] Cancelled")
                break
            except Exception as e:
                logger.error(f"[Worker {worker_id}] Unexpected error: {e}")
                instance.is_busy = False
                await asyncio.sleep(1)  # Prevent tight loop on errors
        
        logger.info(f"[Worker {worker_id}] Shutdown")
    
    async def _process_task(self, instance: ModelInstance, task: TranslationTask) -> Dict[str, Any]:
        """
        Process a translation task for all requested languages.
        
        This runs the actual translation using the model instance.
        """
        translations = {}
        errors = []
        successful = []
        failed = []
        
        for lang in task.target_languages:
            # Run translation in executor to not block event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                instance.translate,
                task.text,
                lang,
                task.is_json
            )
            
            if result["success"]:
                translations[lang] = result["translation"]
                successful.append(lang)
            else:
                translations[lang] = None
                failed.append(lang)
                errors.append({
                    "language": lang,
                    "error": result["error"],
                    "error_type": result["error_type"]
                })
        
        return {
            "translations": translations,
            "successful_languages": successful,
            "failed_languages": failed,
            "errors": errors,
            "success": len(failed) == 0
        }
    
    async def translate(self, text: str, target_languages: List[str], 
                        is_json: bool = False) -> Dict[str, Any]:
        """
        Main translation entry point.
        
        FLOW:
        1. Check cache
        2. If not cached, enqueue task
        3. Wait for worker to process
        4. Cache and return result
        """
        self.stats["total_requests"] += 1
        
        # Check cache first
        cached = await self.cache.get(text, target_languages, is_json)
        if cached:
            self.stats["cache_hits"] += 1
            logger.info(f"[TRANSLATE] Cache hit!")
            return cached
        
        # Not in cache, need to process
        if not self.instances:
            return {
                "translations": {},
                "successful_languages": [],
                "failed_languages": target_languages,
                "errors": [{"error": "No model instances loaded", "error_type": "NO_MODEL"}],
                "success": False
            }
        
        # Enqueue and wait
        self.stats["queue_submissions"] += 1
        task = await self.queue.enqueue(text, target_languages, is_json)
        
        logger.info(f"[TRANSLATE] Task {task.task_id} submitted to queue")
        
        # Wait for result (this yields until worker sets the Future)
        try:
            result = await task.future
            
            # Cache successful results
            if result.get("success"):
                await self.cache.set(text, target_languages, is_json, result)
            
            return result
            
        except Exception as e:
            logger.error(f"[TRANSLATE] Task {task.task_id} failed: {e}")
            return {
                "translations": {},
                "successful_languages": [],
                "failed_languages": target_languages,
                "errors": [{"error": str(e), "error_type": "PROCESSING_ERROR"}],
                "success": False
            }
    
    async def free_memory(self) -> Dict[str, Any]:
        """Free all GPU memory"""
        logger.info("Freeing GPU memory...")
        result = {"steps": []}
        
        # Stop workers
        self.shutdown_event.set()
        for task in self.worker_tasks:
            task.cancel()
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        self.worker_tasks.clear()
        self.shutdown_event.clear()
        result["steps"].append("Workers stopped")
        
        # Delete model instances
        for instance in self.instances:
            del instance.model
            result["steps"].append(f"Instance {instance.instance_id} deleted")
        self.instances.clear()
        
        # Clear tokenizer
        if self.tokenizer:
            del self.tokenizer
            self.tokenizer = None
            result["steps"].append("Tokenizer deleted")
        
        # Clear GPU
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            result["steps"].append("GPU cache cleared")
        
        result["status"] = "completed"
        return result
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage statistics"""
        info = {
            "num_instances": len(self.instances),
            "instances_loaded": len(self.instances) > 0,
            "model_load_error": self.model_load_error,
            "supported_languages": self.supported_languages,
            "max_input_tokens": self.max_input_tokens,
            "stats": self.stats,
            "queue": self.queue.get_status(),
            "instances": [inst.get_stats() for inst in self.instances]
        }
        
        if torch.cuda.is_available():
            info["gpu"] = {
                "allocated_gb": torch.cuda.memory_allocated(0) / 1024**3,
                "reserved_gb": torch.cuda.memory_reserved(0) / 1024**3,
                "total_gb": torch.cuda.get_device_properties(0).total_memory / 1024**3
            }
            info["gpu"]["free_gb"] = info["gpu"]["total_gb"] - info["gpu"]["allocated_gb"]
            info["gpu"]["utilization_percent"] = (info["gpu"]["allocated_gb"] / info["gpu"]["total_gb"]) * 100
        
        try:
            process = psutil.Process()
            info["cpu"] = {
                "process_gb": process.memory_info().rss / 1024**3,
                "system_available_gb": psutil.virtual_memory().available / 1024**3
            }
        except Exception:
            pass
        
        return info
    
    def estimate_completion_time(self, text_length: int, num_languages: int) -> datetime:
        """Estimate completion time"""
        # ~200 chars/sec with full GPU, divided by number of instances
        chars_per_sec = 200 * max(1, len(self.instances))
        seconds = max(2, (text_length / chars_per_sec) * num_languages)
        return datetime.now() + timedelta(seconds=seconds)


# ============================================================================
# PART K: GLOBAL INSTANCES
# ============================================================================

model_manager: Optional[MultiInstanceModelManager] = None


# ============================================================================
# PART L: FASTAPI APP
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model_manager
    
    logger.info("=" * 60)
    logger.info("STARTING TRANSLATION SERVICE - MULTI-INSTANCE GPU MODE")
    logger.info("=" * 60)
    
    try:
        model_manager = MultiInstanceModelManager(num_instances=2)
        
        success = await model_manager.load_models()
        
        if success:
            logger.info("✓ Service started with multiple model instances")
        else:
            logger.warning("⚠ Service started but models failed to load")
            
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        model_manager = None
    
    yield
    
    logger.info("Shutting down...")
    if model_manager:
        await model_manager.free_memory()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Translation Service",
    version="6.0.0",
    description="Multi-instance GPU translation with async queue",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# PART M: HELPER FUNCTIONS
# ============================================================================

def create_response(success: bool, data: Dict = None, 
                    message: str = None, errors: List = None) -> StandardResponse:
    return StandardResponse(**{
        "return": success,
        "data": data,
        "message": message,
        "errors": errors or []
    })


# ============================================================================
# PART N: API ENDPOINTS
# ============================================================================

@app.get("/", response_model=StandardResponse)
async def root():
    """Service information"""
    cache_stats = await model_manager.cache.get_stats() if model_manager else {}
    
    return create_response(
        success=model_manager is not None and len(model_manager.instances) > 0,
        data={
            "service": "Translation Service",
            "version": "6.0.0",
            "mode": "MULTI_INSTANCE_GPU",
            "instances_loaded": len(model_manager.instances) if model_manager else 0,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "cache_stats": cache_stats
        },
        message="Multi-instance GPU translation service"
    )


@app.get("/health", response_model=StandardResponse)
async def health():
    """Health check"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    
    cache_stats = await model_manager.cache.get_stats()
    storage_stats = await model_manager.storage.get_stats()
    active = await model_manager.request_tracker.get_active()
    
    return create_response(
        success=len(model_manager.instances) > 0,
        data={
            "status": "healthy" if model_manager.instances else "degraded",
            "instances": len(model_manager.instances),
            "memory": model_manager.get_memory_usage(),
            "cache": cache_stats,
            "storage": storage_stats,
            "active_requests": active
        }
    )


@app.get("/queue", response_model=StandardResponse)
async def queue_status():
    """Get queue status"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    
    active = await model_manager.request_tracker.get_active()
    history = await model_manager.request_tracker.get_history()
    
    return create_response(
        success=True,
        data={
            "queue": model_manager.queue.get_status(),
            "active_requests": active,
            "recent_history": history
        }
    )


@app.post("/translate", response_model=StandardResponse)
async def translate(request: TranslationRequest):
    """Translate text to multiple languages"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    
    if not model_manager.instances:
        return create_response(False, message="No models loaded")
    
    target_langs = [lang.value for lang in request.target_languages]
    
    try:
        result = await model_manager.translate(request.text, target_langs, request.is_json)
        
        return create_response(
            success=result["success"],
            data={
                "translations": result["translations"],
                "original": request.text,
                "target_languages": target_langs,
                "successful_languages": result["successful_languages"],
                "failed_languages": result.get("failed_languages", [])
            },
            message="Translation completed" if result["success"] else "Some translations failed",
            errors=result.get("errors", [])
        )
        
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return create_response(False, message=str(e))


@app.post("/translate/async", response_model=StandardResponse)
async def translate_async(request: AsyncTranslationRequest, background_tasks: BackgroundTasks):
    """Submit async translation"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    
    translation_id = str(uuid.uuid4())
    target_langs = [lang.value for lang in request.target_languages]
    estimated = model_manager.estimate_completion_time(len(request.text), len(target_langs))
    
    # Save initial status
    await model_manager.storage.save(
        translation_id=translation_id,
        text=request.text,
        translations={},
        target_languages=target_langs,
        metadata={"status": "processing", "started_at": datetime.now().isoformat()}
    )
    
    async def process():
        try:
            result = await model_manager.translate(request.text, target_langs, request.is_json)
            await model_manager.storage.save(
                translation_id=translation_id,
                text=request.text,
                translations=result["translations"],
                target_languages=target_langs,
                metadata={
                    "status": "completed" if result["success"] else "partial",
                    "successful_languages": result["successful_languages"],
                    "failed_languages": result.get("failed_languages", []),
                    "completed_at": datetime.now().isoformat()
                }
            )
        except Exception as e:
            await model_manager.storage.save(
                translation_id=translation_id,
                text=request.text,
                translations={},
                target_languages=target_langs,
                metadata={"status": "failed", "error": str(e)}
            )
    
    background_tasks.add_task(process)
    
    return create_response(
        success=True,
        data={
            "uuid": translation_id,
            "status": "processing",
            "estimated_completion": estimated.isoformat()
        }
    )


@app.get("/translate/async/{uuid}", response_model=StandardResponse)
async def get_async_translation(uuid: str):
    """Get async translation result"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    
    data = await model_manager.storage.get(uuid)
    
    if not data:
        return create_response(False, message=f"Translation {uuid} not found")
    
    status = data.get("metadata", {}).get("status", "unknown")
    
    return create_response(
        success=status in ["completed", "processing"],
        data={
            "uuid": uuid,
            "status": status,
            "original_text": data.get("original_text"),
            "translations": data.get("translations", {}),
            "target_languages": data.get("target_languages"),
            "metadata": data.get("metadata")
        }
    )


@app.post("/translate/batch", response_model=StandardResponse)
async def translate_batch(request: BatchTranslationRequest):
    """Translate multiple texts"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    
    if len(request.texts) > model_manager.max_batch_size:
        return create_response(False, message=f"Batch too large (max: {model_manager.max_batch_size})")
    
    target_langs = [lang.value for lang in request.target_languages]
    results = []
    all_errors = []
    
    for idx, text in enumerate(request.texts):
        result = await model_manager.translate(text, target_langs, request.is_json)
        results.append({
            "index": idx,
            "original": text,
            "translations": result["translations"],
            "success": result["success"]
        })
        all_errors.extend([{**e, "text_index": idx} for e in result.get("errors", [])])
    
    return create_response(
        success=len(all_errors) == 0,
        data={
            "results": results,
            "total": len(request.texts),
            "successful": sum(1 for r in results if r["success"])
        },
        errors=all_errors
    )


@app.post("/translate/batch/async", response_model=StandardResponse)
async def translate_batch_async(request: AsyncBatchTranslationRequest, background_tasks: BackgroundTasks):
    """Submit async batch translation"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    
    batch_id = str(uuid.uuid4())
    target_langs = [lang.value for lang in request.target_languages]
    
    await model_manager.storage.save(
        translation_id=batch_id,
        text=request.texts,
        translations={},
        target_languages=target_langs,
        metadata={"status": "processing", "is_batch": True, "count": len(request.texts)}
    )
    
    async def process():
        try:
            batch_results = {}
            for idx, text in enumerate(request.texts):
                result = await model_manager.translate(text, target_langs, request.is_json)
                batch_results[f"text_{idx}"] = {
                    "original": text,
                    "translations": result["translations"],
                    "success": result["success"]
                }
            
            await model_manager.storage.save(
                translation_id=batch_id,
                text=request.texts,
                translations=batch_results,
                target_languages=target_langs,
                metadata={"status": "completed", "is_batch": True}
            )
        except Exception as e:
            await model_manager.storage.save(
                translation_id=batch_id,
                text=request.texts,
                translations={},
                target_languages=target_langs,
                metadata={"status": "failed", "error": str(e)}
            )
    
    background_tasks.add_task(process)
    
    return create_response(
        success=True,
        data={"uuid": batch_id, "status": "processing", "count": len(request.texts)}
    )


@app.delete("/translate/async/{uuid}", response_model=StandardResponse)
async def delete_async_translation(uuid: str):
    """Delete async translation"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    
    deleted = await model_manager.storage.delete(uuid)
    return create_response(deleted, message=f"Deleted {uuid}" if deleted else f"Not found: {uuid}")


@app.get("/translate/async", response_model=StandardResponse)
async def list_async_translations():
    """List all async translations"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    
    ids = await model_manager.storage.get_all_ids()
    stats = await model_manager.storage.get_stats()
    return create_response(True, data={"ids": ids, "stats": stats})


@app.get("/cache", response_model=StandardResponse)
async def cache_stats():
    """Get cache statistics"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    
    stats = await model_manager.cache.get_stats()
    return create_response(True, data=stats)


@app.post("/cache/clear", response_model=StandardResponse)
async def clear_cache():
    """Clear cache"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    
    await model_manager.cache.clear()
    return create_response(True, message="Cache cleared")


@app.get("/languages", response_model=StandardResponse)
async def get_languages():
    """Get supported languages"""
    return create_response(True, data={"languages": [l.value for l in SupportedLanguage]})


@app.get("/memory", response_model=StandardResponse)
async def get_memory():
    """Get memory usage"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    return create_response(True, data=model_manager.get_memory_usage())


@app.get("/stats", response_model=StandardResponse)
async def get_stats():
    """Get all statistics"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    
    cache_stats = await model_manager.cache.get_stats()
    storage_stats = await model_manager.storage.get_stats()
    history = await model_manager.request_tracker.get_history()
    
    return create_response(True, data={
        "service_stats": model_manager.stats,
        "memory": model_manager.get_memory_usage(),
        "cache": cache_stats,
        "storage": storage_stats,
        "recent_requests": history
    })


@app.post("/reload", response_model=StandardResponse)
async def reload_models():
    """Reload models"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    
    success = await model_manager.load_models()
    return create_response(
        success=success,
        data=model_manager.get_memory_usage() if success else None,
        message="Models reloaded" if success else "Reload failed"
    )


@app.post("/free_memory", response_model=StandardResponse)
async def free_memory():
    """Free GPU memory"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    
    result = await model_manager.free_memory()
    return create_response(True, data=result)


@app.get("/config", response_model=StandardResponse)
async def get_config():
    """Get configuration"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    return create_response(True, data={"config": model_manager.config})


@app.post("/config", response_model=StandardResponse)
async def update_config(update: ConfigUpdate):
    """Update configuration"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    
    success = model_manager.save_config(update.config)
    return create_response(success, data={"config": model_manager.config})


@app.get("/glossary", response_model=StandardResponse)
async def get_glossary():
    """Get glossary"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    return create_response(True, data={"glossary": model_manager.config.get("glossary", {})})


@app.post("/glossary", response_model=StandardResponse)
async def update_glossary(update: GlossaryUpdate):
    """Update glossary"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    
    if "glossary" not in model_manager.config:
        model_manager.config["glossary"] = {}
    model_manager.config["glossary"].update(update.terms)
    success = model_manager.save_config(model_manager.config)
    return create_response(success, data={"glossary": model_manager.config["glossary"]})


@app.get("/generation_params", response_model=StandardResponse)
async def get_generation_params():
    """Get generation parameters"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    
    params = model_manager.config.get("translation", {}).get("generation_params", {})
    return create_response(True, data={"generation_params": params})


@app.post("/generation_params", response_model=StandardResponse)
async def update_generation_params(params: GenerationParams):
    """Update generation parameters"""
    if not model_manager:
        return create_response(False, message="Service not initialized")
    
    if "translation" not in model_manager.config:
        model_manager.config["translation"] = {}
    if "generation_params" not in model_manager.config["translation"]:
        model_manager.config["translation"]["generation_params"] = {}
    
    for key, value in params.model_dump(exclude_none=True).items():
        model_manager.config["translation"]["generation_params"][key] = value
    
    success = model_manager.save_config(model_manager.config)
    return create_response(success, data={
        "generation_params": model_manager.config["translation"]["generation_params"]
    })


# Signal handlers
def signal_handler(signum, frame):
    logger.info(f"Signal {signum} received, shutting down...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Translation Service - 2 Model Instances")
    logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
    logger.info(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    
    uvicorn.run(app, host="0.0.0.0", port=8001, workers=1, loop="asyncio")