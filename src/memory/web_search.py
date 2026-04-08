"""Web search integration for Collective Wisdom.

Provides hybrid search capabilities by combining local memory (EchoVault)
with web search APIs (Serper, Brave, etc.) when local results are insufficient.

Feature flag: Set ECHOVAULT_WEB_SEARCH=disabled to disable web search entirely.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class WebSearchResult:
    """Single web search result."""
    title: str
    url: str
    snippet: str
    source: str = "web"
    date: Optional[str] = None


class WebSearchProvider:
    """Base class for web search providers."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
    
    async def search(self, query: str, num_results: int = 5) -> list[WebSearchResult]:
        """Execute web search and return results."""
        raise NotImplementedError


class SerperProvider(WebSearchProvider):
    """Serper.dev Google Search API provider."""
    
    API_URL = "https://google.serper.dev/search"
    
    async def search(self, query: str, num_results: int = 5) -> list[WebSearchResult]:
        """Search via Serper.dev."""
        if not self.api_key:
            return []
        
        try:
            import httpx
        except ImportError:
            return []
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.API_URL,
                    headers={"X-API-KEY": self.api_key},
                    json={"q": query, "num": num_results},
                )
                response.raise_for_status()
                data = response.json()
        except Exception:
            return []
        
        results = []
        for item in data.get("organic", [])[:num_results]:
            results.append(
                WebSearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    source="serper",
                    date=item.get("date"),
                )
            )
        return results


class BraveProvider(WebSearchProvider):
    """Brave Search API provider."""
    
    API_URL = "https://api.search.brave.com/res/v1/web/search"
    
    async def search(self, query: str, num_results: int = 5) -> list[WebSearchResult]:
        """Search via Brave Search API."""
        if not self.api_key:
            return []
        
        try:
            import httpx
        except ImportError:
            return []
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.API_URL,
                    headers={
                        "Accept": "application/json",
                        "X-Subscription-Token": self.api_key,
                    },
                    params={"q": query, "count": num_results},
                )
                response.raise_for_status()
                data = response.json()
        except Exception:
            return []
        
        results = []
        for item in data.get("web", {}).get("results", [])[:num_results]:
            results.append(
                WebSearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                    source="brave",
                    date=item.get("age"),
                )
            )
        return results


class WebSearchManager:
    """Manager for web search operations with fallback support."""
    
    # Keywords that suggest need for fresh data
    FRESH_DATA_KEYWORDS = {
        "latest", "recent", "new", "2024", "2025", "2026",
        "новый", "новая", "новое", "последний", "актуальный",
        "update", "release", "version", "deprecated",
    }
    
    # Keywords that suggest technical documentation search
    TECH_DOC_KEYWORDS = {
        "documentation", "docs", "api", "reference", "guide",
        "how to", "tutorial", "example", "stackoverflow",
    }
    
    def __init__(self):
        self._provider: Optional[WebSearchProvider] = None
        self._enabled = self._check_enabled()
        self._min_local_results = int(os.getenv("ECHOVAULT_WEB_MIN_LOCAL", "3"))
        self._max_web_results = int(os.getenv("ECHOVAULT_WEB_MAX_RESULTS", "5"))
    
    def _check_enabled(self) -> bool:
        """Check if web search is enabled via feature flag."""
        flag = os.getenv("ECHOVAULT_WEB_SEARCH", "enabled").lower()
        return flag not in ("disabled", "false", "0", "no")
    
    @property
    def provider(self) -> Optional[WebSearchProvider]:
        """Get or create web search provider."""
        if self._provider is not None:
            return self._provider
        
        if not self._enabled:
            return None
        
        # Try Serper first, then Brave
        serper_key = os.getenv("SERPER_API_KEY")
        if serper_key:
            self._provider = SerperProvider(api_key=serper_key)
            return self._provider
        
        brave_key = os.getenv("BRAVE_API_KEY")
        if brave_key:
            self._provider = BraveProvider(api_key=brave_key)
            return self._provider
        
        return None
    
    def needs_web_search(self, query: str, local_results_count: int) -> bool:
        """Determine if web search is needed based on query and local results."""
        if not self._enabled:
            return False
        
        if self.provider is None:
            return False
        
        # Always search web if local results are sparse
        if local_results_count < self._min_local_results:
            return True
        
        # Search web if query suggests need for fresh data
        query_lower = query.lower()
        if any(kw in query_lower for kw in self.FRESH_DATA_KEYWORDS):
            return True
        
        return False
    
    async def search(self, query: str) -> list[WebSearchResult]:
        """Execute web search if provider is available."""
        provider = self.provider
        if provider is None:
            return []
        
        return await provider.search(query, num_results=self._max_web_results)
    
    def format_results_for_collective(
        self, results: list[WebSearchResult]
    ) -> list[dict]:
        """Format web results for collective solve response."""
        formatted = []
        for r in results:
            formatted.append({
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet[:200] + "..." if len(r.snippet) > 200 else r.snippet,
                "source": r.source,
                "date": r.date,
            })
        return formatted


# Global instance for reuse
_web_search_manager: Optional[WebSearchManager] = None


def get_web_search_manager() -> WebSearchManager:
    """Get or create global web search manager instance."""
    global _web_search_manager
    if _web_search_manager is None:
        _web_search_manager = WebSearchManager()
    return _web_search_manager


def reset_web_search_manager() -> None:
    """Reset global instance (useful for testing)."""
    global _web_search_manager
    _web_search_manager = None
