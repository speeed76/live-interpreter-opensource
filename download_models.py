# download_models.py
import os
import torch
from backend.config import settings

def download_all_models():
    """
    Downloads and caches all required models to the directory specified in settings.
    """
    print(f"Starting model download to cache directory: {settings.MODEL_CACHE_DIR}")
    os.makedirs(settings.MODEL_CACHE_DIR, exist_ok=True)

    # --- Download WhisperX Model ---
    try:
        print(f"Downloading Whisper model: {settings.WHISPER_MODEL}...")
        import whisperx
        whisperx.load_model(
            settings.WHISPER_MODEL,
            device="cpu", # Use CPU for downloading to avoid VRAM usage
            cache_dir=settings.MODEL_CACHE_DIR,
            compute_type="int8" # Needs a compute type to load
        )
        print("Whisper model downloaded successfully.")
    except Exception as e:
        print(f"Error downloading Whisper model: {e}")

    # --- Download Translation Models ---
    try:
        from transformers import pipeline
        print(f"Downloading English translation model: {settings.NLLB_MODEL_EN}...")
        pipeline("translation", model=settings.NLLB_MODEL_EN, cache_dir=settings.MODEL_CACHE_DIR)
        print("English translation model downloaded successfully.")

        print(f"Downloading Polish translation model: {settings.NLLB_MODEL_PL}...")
        pipeline("translation", model=settings.NLLB_MODEL_PL, cache_dir=settings.MODEL_CACHE_DIR)
        print("Polish translation model downloaded successfully.")
    except Exception as e:
        print(f"Error downloading translation models: {e}")

    # --- Download Silero VAD Model ---
    try:
        print("Downloading Silero VAD model...")
        torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False,
            trust_repo=True
        )
        print("Silero VAD model downloaded successfully.")
    except Exception as e:
        print(f"Error downloading Silero VAD model: {e}")

    print("\nModel download process complete.")

if __name__ == "__main__":
    download_all_models()
