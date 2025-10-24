"""Ollama LLM client with streaming support and hallucination detection."""
import json
import logging
import requests
from typing import Optional, Dict, Any, Iterator, Callable

from .hallu_detect import get_detector, HallucinationResult

logger = logging.getLogger("crawllama")


class OllamaClient:
    """Client for interacting with Ollama LLM."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen2.5:3b",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        hallu_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Ollama client.

        Args:
            base_url: Ollama API base URL
            model: Model name
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            hallu_config: Hallucination detection configuration
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Initialize hallucination detector
        self.hallu_detector = get_detector(hallu_config) if hallu_config else None
        self.hallu_enabled = hallu_config is not None and hallu_config.get("enabled", False)
        
        logger.info(f"Ollama client initialized: {model} @ {base_url} (hallu_detection: {self.hallu_enabled})")

    def _ensure_connection(self) -> bool:
        """
        Check if Ollama is running and accessible.

        Returns:
            True if connected, False otherwise
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            logger.debug("Ollama connection successful")
            return True
        except requests.RequestException as e:
            logger.error(f"Ollama connection failed: {e}")
            return False

    def generate(
        self,
        prompt: str,
        stream: bool = False,
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """
        Generate completion from prompt.

        Args:
            prompt: Input prompt
            stream: Whether to stream response
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        if not self._ensure_connection():
            raise ConnectionError("Ollama is not running or not accessible")

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
                "num_predict": kwargs.get("max_tokens", self.max_tokens)
            }
        }

        if system_prompt:
            payload["system"] = system_prompt

        try:
            if stream:
                generated_text = self._stream_generate(payload)
            else:
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=120
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

        except requests.RequestException as e:
            logger.error(f"Generation failed: {e}")
            raise

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
                timeout=120
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

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
                "num_predict": kwargs.get("max_tokens", self.max_tokens)
            }
        }

        if system_prompt:
            payload["system"] = system_prompt

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                stream=True,
                timeout=120
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
        if not self._ensure_connection():
            raise ConnectionError("Ollama is not running")

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
                "num_predict": kwargs.get("max_tokens", self.max_tokens)
            }
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=120
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
