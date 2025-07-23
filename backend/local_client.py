# backend/local_client.py
import logging
import os
from typing import Callable, Dict
import torch
import whisperx
import numpy as np
from transformers import pipeline

from .config import settings

logger = logging.getLogger(__name__)

class LocalSpeechProcessor:
    def __init__(self, result_callback: Callable, error_callback: Callable):
        """
        Initializes the Local Speech Processor.
        :param result_callback: A function to call with transcription/translation results.
        :param error_callback: A function to call when an error occurs.
        """
        self.result_callback = result_callback
        self.error_callback = error_callback
        self.target_languages = settings.TARGET_LANGUAGES
        self.audio_buffer = bytearray()
        self.is_speaking = False
        self.silence_frames = 0
        self.is_ready = False
        self._load_models()

    def _load_models(self):
        """Loads all AI models with error handling."""
        try:
            logger.info(f"Loading models to device: {settings.DEVICE}")
            device = torch.device(settings.DEVICE)
            torch_dtype = torch.float16 if settings.TORCH_DTYPE == "float16" else torch.float32
            
            logger.info(f"Loading Whisper model: {settings.WHISPER_MODEL}")
            self.model = whisperx.load_model(
                settings.WHISPER_MODEL, 
                device, 
                compute_type=settings.COMPUTE_TYPE,
                cache_dir=settings.MODEL_CACHE_DIR
            )

            self.translation_pipelines = {}
            logger.info(f"Loading translation model for 'en': {settings.NLLB_MODEL_EN}")
            self.translation_pipelines['en'] = pipeline("translation", model=settings.NLLB_MODEL_EN, device=device)
            logger.info(f"Loading translation model for 'pl': {settings.NLLB_MODEL_PL}")
            self.translation_pipelines['pl'] = pipeline("translation", model=settings.NLLB_MODEL_PL, device=device)

            logger.info("Loading Silero VAD model.")
            self.vad_model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad', model='silero_vad', force_reload=False, onnx=False, trust_repo=True
            )
            (self.get_speech_timestamps, _, _, _, _) = utils
            self.is_ready = True
            logger.info("All models loaded successfully.")

        except Exception as e:
            logger.error(f"Fatal error during model loading: {e}", exc_info=True)
            self.error_callback("Failed to load AI models. Backend is not operational.")
            self.is_ready = False

    def on_recognized(self, text: str, lang: str):
        """Handles final recognition result and triggers translation."""
        translations = {}
        for target_lang in self.target_languages:
            if lang != target_lang and target_lang in self.translation_pipelines:
                try:
                    translation_result = self.translation_pipelines[target_lang](text)
                    translations[target_lang] = translation_result[0]['translation_text']
                except Exception as e:
                    logger.error(f"Error during translation to {target_lang}: {e}")
                    translations[target_lang] = "Translation error."
                    self.error_callback(f"Failed to translate to {target_lang}.")

        logger.info(f"LOCAL ({lang}): Final transcript: '{text}' -> Translations: {translations}")
        self.result_callback('final', text, translations, lang)

    def start(self):
        logger.info("LocalSpeechProcessor starting...")

    def stop(self):
        logger.info("LocalSpeechProcessor stopping...")

    def push_audio_chunk(self, chunk: bytes):
        """Receives an audio chunk and processes it with VAD."""
        if not self.is_ready:
            return
            
        self.audio_buffer.extend(chunk)
        
        # VAD works on 16kHz audio, 16-bit signed integers.
        # A chunk of 1536 samples is 3072 bytes.
        if len(self.audio_buffer) < 3072:
            return

        try:
            audio_int16 = np.frombuffer(self.audio_buffer, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0
            audio_tensor = torch.from_numpy(audio_float32)
            
            speech_prob = self.vad_model(audio_tensor, settings.VAD_SAMPLING_RATE).item()

            if speech_prob > settings.VAD_THRESHOLD:
                self.is_speaking = True
                self.silence_frames = 0
            else:
                if self.is_speaking:
                    self.silence_frames += 1
                
                # If we have enough silence after speech, process the buffer.
                # Each frame is ~96ms. 5 frames of silence is ~0.5s.
                if self.silence_frames > (settings.VAD_MIN_SILENCE_DURATION_MS / 96):
                    self.is_speaking = False
                    self.silence_frames = 0
                    self.process_audio()
                    self.audio_buffer = bytearray()

        except Exception as e:
            logger.error(f"Error during VAD processing: {e}")

    def process_audio(self):
        """Processes the entire audio buffer for transcription in-memory."""
        if not self.audio_buffer:
            return
            
        logger.info(f"Processing audio buffer of size {len(self.audio_buffer)} bytes.")
        try:
            audio_np = np.frombuffer(self.audio_buffer, dtype=np.int16).astype(np.float32) / 32768.0
            result = self.model.transcribe(audio_np, batch_size=16)
            
            if result and result["segments"]:
                full_transcript = " ".join([seg["text"] for seg in result["segments"]]).strip()
                if full_transcript:
                    detected_language = result["language"]
                    self.on_recognized(full_transcript, detected_language)
            else:
                logger.info("Transcription resulted in no segments.")

        except Exception as e:
            logger.error(f"Error during audio transcription: {e}", exc_info=True)
            self.error_callback("An error occurred during transcription.")