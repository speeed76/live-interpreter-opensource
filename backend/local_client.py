# backend/local_client.py
import logging
import os
from typing import Callable, List, Dict
import torch
import whisperx
import torchaudio
from transformers import pipeline

logger = logging.getLogger(__name__)

class LocalSpeechProcessor:
    def __init__(self,
                 result_callback: Callable[[str, str, Dict[str, str], str], None],
                 target_languages: List[str] = ['pl']):
        """
        Initializes the Local Speech Processor for transcription and translation.
        :param result_callback: A function to call with results.
        :param target_languages: A list of language codes to translate to.
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        self.model = whisperx.load_model("large-v2", self.device, compute_type="int8" if self.device == "cuda" else "int8")
        self.translation_pipelines = {}
        for lang in target_languages:
            if lang == "en":
                model_name = "Helsinki-NLP/opus-mt-pl-en"
            else:
                model_name = f"Helsinki-NLP/opus-mt-en-{lang}"
            self.translation_pipelines[lang] = pipeline("translation", model=model_name, device=self.device)

        self.result_callback = result_callback
        self.target_languages = target_languages
        self.audio_buffer = bytearray()

    def on_recognizing(self, text: str, lang: str):
        self.result_callback('interim', text, {}, lang)

    def on_recognized(self, text: str, lang: str):
        translations = {}
        for target_lang in self.target_languages:
            if lang != target_lang:
                if lang == "en":
                    # Translate from English to Polish
                    translations[target_lang] = self.translation_pipelines[target_lang](text)[0]['translation_text']
                else:
                    # Translate from Polish to English
                    translations[target_lang] = self.translation_pipelines[target_lang](text)[0]['translation_text']

        logger.info(f"LOCAL ({lang}): Final transcript: '{text}' -> Translations: {translations}")
        self.result_callback('final', text, translations, lang)

    def start(self):
        logger.info("LocalSpeechProcessor starting...")

    def stop(self):
        logger.info("LocalSpeechProcessor stopping...")

    def push_audio_chunk(self, chunk: bytes):
        self.audio_buffer.extend(chunk)
        # Process audio when buffer is large enough
        if len(self.audio_buffer) > 16000 * 5: # 5 seconds of audio
            self.process_audio()
            self.audio_buffer = bytearray()

    def process_audio(self):
        try:
            audio_tensor, sample_rate = torchaudio.load(self.audio_buffer)
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
                audio_tensor = resampler(audio_tensor)
            
            audio_float32 = audio_tensor.squeeze().to(torch.float32)
            result = self.model.transcribe(audio_float32, batch_size=16)
            
            if result and result["segments"]:
                for segment in result["segments"]:
                    self.on_recognized(segment["text"], result["language"])
            else:
                self.on_recognizing("...", "unknown")

        except Exception as e:
            logger.error(f"Error processing audio: {e}")
