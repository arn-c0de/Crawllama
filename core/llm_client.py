"""Ollama LLM client with streaming support, retry logic, and hallucination detection."""
import json
import logging
import requests
import time
from typing import Optional, Dict, Any, Iterator, Callable
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from .hallu_detect import get_detector, HallucinationResult

logger = logging.getLogger("crawllama")


class OllamaClient:
    """Client for interacting with Ollama LLM."""

    @staticmethod
    def _validate_base_url(base_url: str) -> str:
        """Validate the configured Ollama base URL.

        The backend URL is operator-controlled config, but rejecting non-HTTP(S)
        schemes prevents misconfiguration (e.g. file:// / gopher://) from turning
        the LLM channel into an unexpected request sink.
        """
        from urllib.parse import urlparse
        parsed = urlparse(str(base_url))
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(
                f"Invalid Ollama base_url '{base_url}': must be an http(s) URL"
            )
        return str(base_url)

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen2.5:3b",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        hallu_config: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        retry_min_wait: int = 1,
        retry_max_wait: int = 10,
        timeout: int = 120,
        max_requests_per_minute: int = 60,
        num_ctx: int = 0
    ):
        """
        Initialize Ollama client with retry capabilities.

        Args:
            base_url: Ollama API base URL
            model: Model name
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            hallu_config: Hallucination detection configuration
            max_retries: Maximum number of retry attempts (default: 3)
            retry_min_wait: Minimum wait time between retries in seconds (default: 1)
            retry_max_wait: Maximum wait time between retries in seconds (default: 10)
            timeout: Request timeout in seconds (default: 120)
            max_requests_per_minute: Maximum requests per minute (default: 60)
            num_ctx: Ollama context window size (0 = use model default)
        """
        self.base_url = self._validate_base_url(base_url).rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.retry_min_wait = retry_min_wait
        self.retry_max_wait = retry_max_wait
        self.timeout = timeout
        self.num_ctx = num_ctx if num_ctx > 0 else 0

        # Connection pooling
        import requests
        self.session = requests.Session()

        # Rate limiting setup
        self.max_requests_per_minute = max_requests_per_minute
        from collections import deque
        self.request_timestamps = deque()
        self.min_request_interval = 60.0 / max_requests_per_minute if max_requests_per_minute > 0 else 0

        # Initialize hallucination detector
        self.hallu_detector = get_detector(hallu_config) if hallu_config else None
        self.hallu_enabled = hallu_config is not None and hallu_config.get("enabled", False)

        logger.info(
            f"Ollama client initialized: {model} @ {base_url} "
            f"(hallu_detection: {self.hallu_enabled}, max_retries: {max_retries}, "
            f"rate_limit: {max_requests_per_minute}/min, num_ctx: {self.num_ctx or 'model default'})"
        )

    def _build_options(self, **kwargs) -> dict:
        """Build Ollama options dict, including num_ctx when configured."""
        options = {
            "temperature": kwargs.get("temperature", self.temperature),
            "num_predict": kwargs.get("max_tokens", self.max_tokens),
        }
        if self.num_ctx > 0:
            options["num_ctx"] = kwargs.get("num_ctx", self.num_ctx)
        return options

    def _preflight_token_check(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> str:
        """Rough pre-flight check: truncate prompt if it would overflow num_ctx.

        Uses a fast 4-chars-per-token estimate to avoid importing tiktoken
        in the LLM client layer.

        Args:
            prompt: The prompt text
            system_prompt: Optional system prompt

        Returns:
            Possibly truncated prompt
        """
        if self.num_ctx <= 0:
            return prompt  # no limit configured

        total_chars = len(prompt) + (len(system_prompt) if system_prompt else 0)
        estimated_tokens = total_chars // 4
        max_input_tokens = self.num_ctx - self.max_tokens  # reserve for response

        if estimated_tokens > max_input_tokens > 0:
            logger.warning(
                "Pre-flight: prompt (~%d tokens) exceeds input budget (%d). Truncating.",
                estimated_tokens, max_input_tokens,
            )
            max_chars = max_input_tokens * 4
            prompt = prompt[:max_chars]

        return prompt

    def _wait_for_rate_limit(self):
        """Enforce rate limiting by waiting if necessary."""
        if self.max_requests_per_minute <= 0:
            return  # No rate limiting
            
        current_time = time.time()
        
        # Remove timestamps older than 1 minute
        while self.request_timestamps and current_time - self.request_timestamps[0] > 60:
            self.request_timestamps.popleft()
        
        # Check if we need to wait
        if len(self.request_timestamps) >= self.max_requests_per_minute:
            # Calculate wait time until oldest request is 1 minute old
            oldest_request = self.request_timestamps[0]
            wait_time = 60 - (current_time - oldest_request)
            if wait_time > 0:
                logger.debug(f"Rate limit reached, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                # Update current time after waiting
                current_time = time.time()
        
        # Also enforce minimum interval between requests
        if self.request_timestamps and self.min_request_interval > 0:
            last_request = self.request_timestamps[-1]
            time_since_last = current_time - last_request
            if time_since_last < self.min_request_interval:
                wait_time = self.min_request_interval - time_since_last
                logger.debug(f"Enforcing min interval, waiting {wait_time:.2f}s")
                time.sleep(wait_time)
                current_time = time.time()
        
        # Record this request
        self.request_timestamps.append(current_time)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(requests.RequestException),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    def _ensure_connection(self) -> bool:
        """
        Check if Ollama is running and accessible with retry logic.

        Returns:
            True if connected

        Raises:
            requests.RequestException: If connection fails after retries
        """
        response = requests.get(f"{self.base_url}/api/tags", timeout=5)
        response.raise_for_status()
        logger.debug("Ollama connection successful")
        return True

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    def generate(
        self,
        prompt: str,
        stream: bool = False,
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """
        Generate completion from prompt with automatic retry on failure.

        Args:
            prompt: Input prompt
            stream: Whether to stream response
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Returns:
            Generated text

        Raises:
            ConnectionError: If Ollama is not accessible after retries
            requests.RequestException: If request fails after retries
        """
        # Apply rate limiting
        self._wait_for_rate_limit()

        # Pre-flight token check
        prompt = self._preflight_token_check(prompt, system_prompt)

        self._ensure_connection()  # Will retry connection if needed

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": self._build_options(**kwargs),
        }

        if system_prompt:
            payload["system"] = system_prompt

        if stream:
            generated_text = self._stream_generate(payload)
        else:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            generated_text = result.get("response", "")

        # Hallucination detection
        if self.hallu_enabled and generated_text:
            hallu_result = self._check_hallucination(generated_text, prompt, system_prompt)
            if hallu_result.is_hallucination and hallu_result.risk_level == "high":
                logger.warning(f"High hallucination risk detected (score: {hallu_result.confidence_score:.2f})")
                # Optionally modify or flag the response
                generated_text += f"\n\n⚠️ [Quality Warning: Response may contain inaccuracies - confidence: {hallu_result.confidence_score:.2f}]"

        return generated_text

    def _stream_generate(self, payload: Dict[str, Any]) -> str:
        """
        Stream generation and collect full response.

        Args:
            payload: Request payload

        Returns:
            Complete generated text
        """
        full_response = []

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                stream=True,
                timeout=self.timeout
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    chunk_data = json.loads(line)
                    if "response" in chunk_data:
                        text = chunk_data["response"]
                        full_response.append(text)
                        # Removed print() to avoid double output
                        # print(text, end="", flush=True)

                    if chunk_data.get("done", False):
                        break

            # print()  # Newline after streaming - removed
            return "".join(full_response)

        except requests.RequestException as e:
            logger.error(f"Streaming failed: {e}")
            raise

    def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        callback: Optional[Callable[[str], None]] = None,
        **kwargs: Any
    ) -> Iterator[str]:
        """
        Stream generation with callback support.

        Args:
            prompt: Input prompt
            system_prompt: Optional system prompt
            callback: Optional callback for each chunk
            **kwargs: Additional parameters

        Yields:
            Text chunks
        """
        if not self._ensure_connection():
            raise ConnectionError("Ollama is not running")

        prompt = self._preflight_token_check(prompt, system_prompt)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": self._build_options(**kwargs),
        }

        if system_prompt:
            payload["system"] = system_prompt

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                stream=True,
                timeout=self.timeout
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    chunk_data = json.loads(line)
                    if "response" in chunk_data:
                        text = chunk_data["response"]
                        if callback:
                            callback(text)
                        yield text

                    if chunk_data.get("done", False):
                        break

        except requests.RequestException as e:
            logger.error(f"Streaming failed: {e}")
            raise

    def chat(
        self,
        messages: list,
        stream: bool = False,
        **kwargs: Any
    ) -> str:
        """
        Chat completion with message history.

        Args:
            messages: List of message dicts with 'role' and 'content'
            stream: Whether to stream response
            **kwargs: Additional parameters

        Returns:
            Assistant response
        """
        # Apply rate limiting
        self._wait_for_rate_limit()

        if not self._ensure_connection():
            raise ConnectionError("Ollama is not running")

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": self._build_options(**kwargs),
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            return result.get("message", {}).get("content", "")

        except requests.RequestException as e:
            logger.error(f"Chat failed: {e}")
            raise

    def get_embeddings(self, text: str) -> list:
        """
        Get embeddings for text.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        if not self._ensure_connection():
            raise ConnectionError("Ollama is not running")

        try:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            return result.get("embedding", [])

        except requests.RequestException as e:
            logger.error(f"Embeddings failed: {e}")
            raise

    def _check_hallucination(self, response: str, prompt: str, system_prompt: Optional[str] = None) -> HallucinationResult:
        """
        Check response for hallucinations.
        
        Args:
            response: Generated response
            prompt: Original prompt
            system_prompt: System prompt (if any)
            
        Returns:
            HallucinationResult
        """
        if not self.hallu_detector:
            # Return dummy result if detector not initialized
            from .hallu_detect import HallucinationResult
            return HallucinationResult(
                is_hallucination=False,
                confidence_score=0.0,
                risk_level="disabled",
                violations=[],
                context_alignment=1.0,
                fact_check_results=[],
                quality_metrics={},
                processing_time=0.0
            )
            
        # Combine prompt and system prompt as context
        context = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        
        return self.hallu_detector.detect(response, context, {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        })

    def get_hallucination_stats(self) -> Dict[str, Any]:
        """Get hallucination detection statistics."""
        if self.hallu_detector:
            return self.hallu_detector.get_statistics()
        return {}

    def enable_hallucination_detection(self, config: Dict[str, Any] = None):
        """Enable hallucination detection with optional configuration."""
        if config is None:
            config = {"enabled": True}
        else:
            config["enabled"] = True
            
        self.hallu_detector = get_detector(config)
        self.hallu_enabled = True
        logger.info("Hallucination detection enabled")

    def disable_hallucination_detection(self):
        """Disable hallucination detection."""
        self.hallu_enabled = False
        logger.info("Hallucination detection disabled")
