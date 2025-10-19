from pathlib import Path
from typing import Any
import tomllib


class Config:
    """Configuration manager for loading and accessing TOML config files."""

    _instance: "Config | None" = None
    _config_data: dict[str, Any] = {}

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

    def get(self, key: str, default: Any = None):
        """
        Get a configuration value using dot notation.

        Examples:
            config.get("ai.openrouter_api_key")
            config.get("jina.api_key")
        """
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
    """
    if config_path is None:
        # Default to config.toml in project root
        project_root = Path(__file__).parent.parent
        config_path = project_root / "config.toml"

    return CONFIG.load(config_path)


# Auto-load configuration when module is imported
load_config()


__all__ = ["CONFIG"]
