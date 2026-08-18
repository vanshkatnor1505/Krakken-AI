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


# ==========================================================
# LOAD ENVIRONMENT
# ==========================================================

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

    # ======================================================
    # APPLICATION
    # ======================================================

    app_name: str = Field(
        default="Krakken AI"
    )

    app_version: str = Field(
        default="0.1.0"
    )

    environment: str = Field(
        default="development"
    )

    debug: bool = Field(
        default=True
    )

    # ======================================================
    # AI
    # ======================================================

    groq_api_key: str = Field(
        default=""
    )

    groq_model: str = Field(
        default="openai/gpt-oss-20b"
    )

    groq_stt_model: str = Field(
        default="whisper-large-v3-turbo"
    )

    voice_input_language: str = Field(
        default="en"
    )

    openai_api_key: str = Field(
        default=""
    )

    # ======================================================
    # VOICE
    # ======================================================

    elevenlabs_api_key: str = Field(
        default=""
    )

    # ======================================================
    # UI
    # ======================================================

    theme: str = "dark"

    language: str = "en"

    # ======================================================
    # PATHS
    # ======================================================

    root_dir: Path = Path.cwd()

    logs_dir: Path = Path("logs")

    cache_dir: Path = Path("cache")

    database_dir: Path = Path("database")

    plugins_dir: Path = Path("plugins")

    assets_dir: Path = Path("ui/assets")

    themes_dir: Path = Path("ui/themes")

    # ======================================================
    # DIRECTORIES
    # ======================================================

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

            directory.mkdir(
                parents=True,
                exist_ok=True,
            )


# ==========================================================
# GLOBAL CONFIGURATION
# ==========================================================

config = AppConfig()

config.initialize_directories()
