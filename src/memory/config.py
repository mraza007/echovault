import os
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class EmbeddingConfig:
    provider: str = "ollama"
    model: str = "nomic-embed-text"
    base_url: Optional[str] = "http://localhost:11434"
    api_key: Optional[str] = None


@dataclass
class ContextConfig:
    semantic: str = "auto"
    topup_recent: bool = True


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
            base_url=e.get("base_url", "http://localhost:11434"),
            api_key=e.get("api_key"),
        )
    if "context" in data:
        cx = data["context"]
        config.context = ContextConfig(
            semantic=cx.get("semantic", "auto"),
            topup_recent=cx.get("topup_recent", True),
        )
    return config
