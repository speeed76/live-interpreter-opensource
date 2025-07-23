# backend/config.py
import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # App settings
    LOG_LEVEL: str = "INFO"
    TARGET_LANGUAGES: List[str] = ["en", "pl"]

    # Device settings
    DEVICE: str = "cuda"
    TORCH_DTYPE: str = "float16"
    COMPUTE_TYPE: str = "int8"

    # Model settings
    WHISPER_MODEL: str = "large-v2"
    NLLB_MODEL_EN: str = "Helsinki-NLP/opus-mt-pl-en"
    NLLB_MODEL_PL: str = "Helsinki-NLP/opus-mt-en-pl"
    
    # VAD settings
    VAD_THRESHOLD: float = 0.5
    VAD_SAMPLING_RATE: int = 16000
    VAD_MIN_SILENCE_DURATION_MS: int = 500 # ms of silence to consider end of speech

    # Model cache
    MODEL_CACHE_DIR: str = "/models"

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()
