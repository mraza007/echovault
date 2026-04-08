"""LLM-based compression provider for semantic summarization."""

import httpx
from typing import Optional, Protocol


class CompressionProvider(Protocol):
    """Protocol for compression/summarization providers."""
    
    def compress(self, text: str, max_chars: int = 500) -> str:
        """Compress text to semantic summary."""
        ...


class TruncationCompressor:
    """Fallback: simple truncation + key paragraph extraction."""
    
    def compress(self, text: str, max_chars: int = 500) -> str:
        """Compress by taking first and last paragraphs."""
        if len(text) <= max_chars:
            return text
        
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(paragraphs) <= 2:
            return text[:max_chars] + "..."
        
        first = paragraphs[0]
        last = paragraphs[-1]
        
        summary = f"{first}\n\n...\n\n{last}"
        if len(summary) > max_chars:
            summary = summary[:max_chars] + "..."
        
        return summary


class OllamaCompressor:
    """LLM-based compression using Ollama API."""
    
    DEFAULT_PROMPT = """Summarize the following text concisely while preserving key information:

{text}

Summary (max {max_chars} chars):"""
    
    def __init__(
        self,
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
        prompt_template: Optional[str] = None,
        timeout: float = 30.0,
        max_tokens: int = 200,
    ):
        """Initialize Ollama compressor.
        
        Args:
            model: Model name for summarization
            base_url: Ollama API base URL
            prompt_template: Custom prompt template (use {text} and {max_chars})
            timeout: Request timeout
            max_tokens: Max tokens in response
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.prompt_template = prompt_template or self.DEFAULT_PROMPT
        self.timeout = timeout
        self.max_tokens = max_tokens
        self._fallback = TruncationCompressor()
    
    def compress(self, text: str, max_chars: int = 500) -> str:
        """Compress text using LLM summarization.
        
        Falls back to truncation if LLM fails.
        """
        # Quick return for short texts
        if len(text) <= max_chars:
            return text
        
        try:
            prompt = self.prompt_template.format(
                text=text[:4000],  # Limit input context
                max_chars=max_chars
            )
            
            resp = httpx.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": self.max_tokens,
                    }
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            
            summary = resp.json()["response"].strip()
            
            # Enforce length limit
            if len(summary) > max_chars:
                summary = summary[:max_chars].rsplit(" ", 1)[0] + "..."
            
            return summary
            
        except Exception as e:
            print(f"[OllamaCompressor] LLM failed: {e}, using fallback")
            return self._fallback.compress(text, max_chars)


class OpenAICompressor:
    """LLM-based compression using OpenAI API."""
    
    DEFAULT_PROMPT = """Summarize the following text concisely while preserving key information. 
Keep the summary under {max_chars} characters.

Text:
{text}

Summary:"""
    
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        prompt_template: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """Initialize OpenAI compressor.
        
        Args:
            model: OpenAI model name
            api_key: API key (or use OPENAI_API_KEY env var)
            base_url: Optional custom base URL
            prompt_template: Custom prompt template
            timeout: Request timeout
        """
        self.model = model
        self.api_key = api_key or ""
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.prompt_template = prompt_template or self.DEFAULT_PROMPT
        self.timeout = timeout
        self._fallback = TruncationCompressor()
    
    def compress(self, text: str, max_chars: int = 500) -> str:
        """Compress text using OpenAI API.
        
        Falls back to truncation if API fails.
        """
        if len(text) <= max_chars:
            return text
        
        if not self.api_key:
            return self._fallback.compress(text, max_chars)
        
        try:
            prompt = self.prompt_template.format(
                text=text[:4000],
                max_chars=max_chars
            )
            
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a text summarization assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 200,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            
            summary = resp.json()["choices"][0]["message"]["content"].strip()
            
            if len(summary) > max_chars:
                summary = summary[:max_chars].rsplit(" ", 1)[0] + "..."
            
            return summary
            
        except Exception as e:
            print(f"[OpenAICompressor] API failed: {e}, using fallback")
            return self._fallback.compress(text, max_chars)
