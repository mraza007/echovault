import os
import tempfile
from pathlib import Path

import pytest
import yaml

from memory.config import (
    EmbeddingConfig,
    MemoryConfig,
    clear_persisted_memory_home,
    get_memory_home,
    get_persisted_memory_home,
    load_config,
    resolve_memory_home,
    set_persisted_memory_home,
)


def test_default_config_has_correct_defaults():
    """Test that default config has expected default values."""
    config = MemoryConfig()

    assert config.embedding.provider == "ollama"
    assert config.embedding.model == "nomic-embed-text"
    assert config.embedding.base_url == "http://localhost:11434"
    assert config.embedding.api_key is None


def test_load_config_with_all_fields():
    """Test loading config from YAML with all fields populated."""
    config_data = {
        "embedding": {
            "provider": "openai",
            "model": "text-embedding-3-small",
            "base_url": "https://api.openai.com/v1",
            "api_key": "openai-key",
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        config = load_config(config_path)

        assert config.embedding.provider == "openai"
        assert config.embedding.model == "text-embedding-3-small"
        assert config.embedding.base_url == "https://api.openai.com/v1"
        assert config.embedding.api_key == "openai-key"
    finally:
        os.unlink(config_path)


def test_load_config_missing_file_returns_defaults():
    """Test that loading a non-existent file returns default config."""
    config = load_config("/nonexistent/path/to/config.yaml")

    assert config.embedding.provider == "ollama"
    assert config.embedding.model == "nomic-embed-text"


def test_load_config_partial_fields():
    """Test loading config with only some fields specified."""
    config_data = {
        "embedding": {
            "provider": "ollama",
            "model": "nomic-embed-text",
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        config = load_config(config_path)

        assert config.embedding.provider == "ollama"
        assert config.embedding.model == "nomic-embed-text"
        assert config.embedding.base_url == "http://localhost:11434"
        assert config.embedding.api_key is None
    finally:
        os.unlink(config_path)


def test_load_config_empty_file():
    """Test loading an empty YAML file returns defaults."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("")
        config_path = f.name

    try:
        config = load_config(config_path)

        assert config.embedding.provider == "ollama"
        assert config.embedding.model == "nomic-embed-text"
    finally:
        os.unlink(config_path)


def test_get_memory_home_defaults_to_home_directory():
    """Test that get_memory_home defaults to ~/.memory."""
    # Temporarily remove MEMORY_HOME if it exists
    old_value = os.environ.get("MEMORY_HOME")
    if "MEMORY_HOME" in os.environ:
        del os.environ["MEMORY_HOME"]

    try:
        memory_home = get_memory_home()
        expected = os.path.join(os.path.expanduser("~"), ".memory")
        assert memory_home == expected
    finally:
        if old_value is not None:
            os.environ["MEMORY_HOME"] = old_value


def test_get_memory_home_respects_env_var():
    """Test that get_memory_home respects MEMORY_HOME env var."""
    custom_path = "/custom/memory/path"
    old_value = os.environ.get("MEMORY_HOME")

    try:
        os.environ["MEMORY_HOME"] = custom_path
        memory_home = get_memory_home()
        assert memory_home == custom_path
    finally:
        if old_value is not None:
            os.environ["MEMORY_HOME"] = old_value
        else:
            del os.environ["MEMORY_HOME"]


def test_get_memory_home_respects_persisted_config(monkeypatch, tmp_path):
    """Test that persisted config is used when MEMORY_HOME is unset."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("MEMORY_HOME", raising=False)

    target = tmp_path / "custom-memory-home"
    set_persisted_memory_home(str(target))

    assert get_persisted_memory_home() == str(target.resolve())
    assert get_memory_home() == str(target.resolve())


def test_resolve_memory_home_env_has_priority(monkeypatch, tmp_path):
    """Test that MEMORY_HOME takes priority over persisted config."""
    monkeypatch.setenv("HOME", str(tmp_path))
    persisted = tmp_path / "persisted-home"
    set_persisted_memory_home(str(persisted))

    env_path = tmp_path / "env-home"
    monkeypatch.setenv("MEMORY_HOME", str(env_path))

    resolved, source = resolve_memory_home()
    assert resolved == str(env_path.resolve())
    assert source == "env"


def test_clear_persisted_memory_home(monkeypatch, tmp_path):
    """Test clearing persisted memory home removes the setting."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("MEMORY_HOME", raising=False)

    target = tmp_path / "persisted-home"
    set_persisted_memory_home(str(target))
    assert get_persisted_memory_home() == str(target.resolve())

    assert clear_persisted_memory_home() is True
    assert get_persisted_memory_home() is None
    assert clear_persisted_memory_home() is False
