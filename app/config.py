"""
Central configuration for Kraken AI.

Loads environment variables, validates settings, and exposes
a single application configuration object.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env before reading settings
load_dotenv()


class AppConfig(BaseSettings):
    """
    Application configuration.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --------------------------------------------------
    # Application
    # --------------------------------------------------

    app_name: str = Field(default="Krakken AI")
    app_version: str = Field(default="0.1.0")
    environment: str = Field(default="development")
    debug: bool = Field(default=True)

    # --------------------------------------------------
    # AI
    # --------------------------------------------------

    groq_api_key: str = ""
    openai_api_key: str = ""

    # --------------------------------------------------
    # Voice
    # --------------------------------------------------

    elevenlabs_api_key: str = ""

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    theme: str = "dark"
    language: str = "en"

    # --------------------------------------------------
    # Paths
    # --------------------------------------------------

    root_dir: Path = Path.cwd()

    logs_dir: Path = Path("logs")
    cache_dir: Path = Path("cache")
    database_dir: Path = Path("database")
    plugins_dir: Path = Path("plugins")

    assets_dir: Path = Path("ui/assets")
    themes_dir: Path = Path("ui/themes")

    def initialize_directories(self) -> None:
        """
        Create required directories.
        """

        directories = [
            self.logs_dir,
            self.cache_dir,
            self.database_dir,
            self.plugins_dir,
            self.assets_dir,
            self.themes_dir,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


config = AppConfig()

config.initialize_directories()