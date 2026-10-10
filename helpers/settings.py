from __future__ import annotations
from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Settings(BaseSettings):
    

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "Knowledge_Workers_Agent"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    LOG_LEVEL: str = "INFO"

    # Generation Specs
    GENERATION_PROVIDER: str = "OLLAMA"
    GENERATION_MODEL_NAME: str = "gemma4:31b-cloud"
    GENERATION_DEFAULT_MAX_TOKENS: int = 20000
    GENERATION_DEFAULT_TEMPERATURE: float = 0.2
    #OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    GENERATION_NUM_CTX: int = 8192


    @property
    def is_local(self) -> bool:
        return self.ENVIRONMENT == "local"

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
