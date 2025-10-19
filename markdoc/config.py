from pathlib import Path
from typing import Any
import tomllib


class Config:
    """Configuration manager for loading and accessing TOML config files."""

    _instance: "Config | None" = None
    _config_data: dict[str, Any] = {}
    _use_streamlit_secrets: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, config_path: str | Path) -> "Config":
        """Load configuration from a TOML file."""
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "rb") as f:
            self._config_data = tomllib.load(f)

        return self

    def _get_streamlit_secrets(self):
        """Try to get streamlit secrets if available"""
        try:
            import streamlit as st

            if hasattr(st, "secrets") and len(st.secrets) > 0:
                return st.secrets
        except (ImportError, FileNotFoundError):
            pass
        return None

    def _deep_to_dict(self, obj):
        """Recursively convert objects to plain dict (handles Streamlit secrets)"""
        if isinstance(obj, dict):
            return {key: self._deep_to_dict(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_to_dict(item) for item in obj]
        elif hasattr(obj, "to_dict"):
            return obj.to_dict()
        else:
            return obj

    def get(self, key: str, default: Any = None):
        """
        Get a configuration value using dot notation.

        Examples:
            config.get("ai.openrouter_api_key")
            config.get("jina.api_key")

        Priority:
            1. Streamlit secrets (for cloud deployment)
            2. Local config file (for local development)
        """
        # Try streamlit secrets first
        secrets = self._get_streamlit_secrets()
        if secrets is not None:
            keys = key.split(".")
            value = secrets
            for k in keys:
                try:
                    # Use attribute access for streamlit secrets objects
                    if hasattr(value, k):
                        value = getattr(value, k)
                    elif hasattr(value, "__getitem__"):
                        value = value[k]
                    else:
                        value = None
                        break
                except (KeyError, AttributeError):
                    value = None
                    break

            if value is not None:
                # Convert to plain Python types before returning
                return self._deep_to_dict(value)

        # Fallback to local config
        keys = key.split(".")
        value = self._config_data

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    def __getitem__(self, key: str):
        """Access config using dictionary-style syntax."""
        return self._config_data[key]

    def __contains__(self, key: str):
        """Check if a top-level key exists in config."""
        return key in self._config_data

    @property
    def data(self):
        """Get the entire configuration dictionary."""
        return self._config_data


# Singleton instance
CONFIG = Config()


def load_config(config_path: str | Path = None):
    """
    Load configuration from TOML file.

    Args:
        config_path: Path to the config file. If None, looks for config.toml
                     in the project root.

    Note:
        In Streamlit Cloud, if config.toml doesn't exist, it will use st.secrets instead.
    """
    if config_path is None:
        # Default to config.toml in project root
        project_root = Path(__file__).parent.parent
        config_path = project_root / "config.toml"

    # Try to load local config file if it exists
    # In Streamlit Cloud, this might not exist, which is fine
    try:
        return CONFIG.load(config_path)
    except FileNotFoundError:
        # File not found - probably in Streamlit Cloud
        # Config.get() will automatically use st.secrets
        return CONFIG


# Auto-load configuration when module is imported
load_config()


__all__ = ["CONFIG"]
