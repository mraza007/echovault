import os
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class EmbeddingConfig:
    provider: str = "ollama"
    model: str = "nomic-embed-text"
    base_url: Optional[str] = None
    api_key: Optional[str] = None


@dataclass
class ContextConfig:
    mode: str = "auto"
    semantic: str = "auto"
    topup_recent: bool = True
    token_budget: int = 1200
    min_relevance: float = 0.7
    min_vector_similarity: float = 0.05
    agent_modes: dict[str, str] = field(default_factory=dict)


@dataclass
class MemoryConfig:
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    context: ContextConfig = field(default_factory=ContextConfig)


def _global_config_path() -> str:
    return os.path.join(os.path.expanduser("~"), ".config", "echovault", "config.yaml")


def _normalize_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def get_persisted_memory_home() -> Optional[str]:
    """Return persisted memory home from global config, if set."""
    path = _global_config_path()
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return None

    value = data.get("memory_home")
    if not isinstance(value, str) or not value.strip():
        return None
    return _normalize_path(value.strip())


def set_persisted_memory_home(path: str) -> str:
    """Persist memory home in global config and return normalized value."""
    normalized = _normalize_path(path)
    cfg_path = _global_config_path()
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)

    data: dict = {}
    try:
        with open(cfg_path) as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        data = {}

    data["memory_home"] = normalized
    with open(cfg_path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False)

    return normalized


def clear_persisted_memory_home() -> bool:
    """Clear persisted memory home from global config; return True if changed."""
    cfg_path = _global_config_path()
    try:
        with open(cfg_path) as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return False

    if "memory_home" not in data:
        return False

    del data["memory_home"]
    if data:
        with open(cfg_path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)
    else:
        os.remove(cfg_path)
    return True


def resolve_memory_home() -> tuple[str, str]:
    """Resolve memory home and return (path, source)."""
    env_home = os.environ.get("MEMORY_HOME")
    if env_home:
        return _normalize_path(env_home), "env"

    persisted = get_persisted_memory_home()
    if persisted:
        return persisted, "config"

    default_home = os.path.join(os.path.expanduser("~"), ".memory")
    return default_home, "default"


def get_memory_home() -> str:
    return resolve_memory_home()[0]


def load_config(path: str) -> MemoryConfig:
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return MemoryConfig()

    config = MemoryConfig()
    if "embedding" in data:
        e = data["embedding"]
        config.embedding = EmbeddingConfig(
            provider=e.get("provider", "ollama"),
            model=e.get("model", "nomic-embed-text"),
            base_url=e.get("base_url"),
            api_key=e.get("api_key"),
        )
    if "context" in data:
        cx = data["context"]
        config.context = ContextConfig(
            mode=cx.get("mode", "auto"),
            semantic=cx.get("semantic", "auto"),
            topup_recent=cx.get("topup_recent", True),
            token_budget=int(cx.get("token_budget", 1200)),
            min_relevance=float(cx.get("min_relevance", 0.7)),
            min_vector_similarity=float(cx.get("min_vector_similarity", 0.05)),
            agent_modes=dict(cx.get("agent_modes", {}) or {}),
        )
    return config


def resolve_context_mode(config: MemoryConfig, agent: Optional[str] = None) -> tuple[str, str]:
    """Resolve automatic context policy and report where it came from.

    Precedence: ``MEMORY_CONTEXT`` session override, agent override, global mode.
    Invalid values degrade to ``auto`` rather than unexpectedly disabling memory.
    """
    env_mode = os.environ.get("MEMORY_CONTEXT", "").strip().lower()
    if env_mode in {"on", "off", "auto"}:
        return env_mode, "env"
    if agent:
        agent_mode = config.context.agent_modes.get(agent, "").strip().lower()
        if agent_mode in {"on", "off", "auto"}:
            return agent_mode, f"agent:{agent}"
    mode = str(config.context.mode).strip().lower()
    return (mode if mode in {"on", "off", "auto"} else "auto"), "config"
