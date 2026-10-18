"""Local wake-word detection for the custom "yo pikachu" model."""

from pathlib import Path
import queue
import threading

import numpy as np
import sounddevice as sd
from openwakeword.model import Model


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "yo_pee_kah_choo.onnx"
MELSPECTROGRAM_PATH = PROJECT_ROOT / "models" / "melspectrogram.onnx"
EMBEDDING_PATH = PROJECT_ROOT / "models" / "embedding_model.onnx"
SAMPLE_RATE = 16_000
CHUNK_SAMPLES = 1_280


def wait_for_wake_word(
    stop_event: threading.Event,
    threshold: float = 0.5,
) -> bool:
    """Listen locally until the wake word is detected or listening is stopped."""
    for model_path in (MODEL_PATH, MELSPECTROGRAM_PATH, EMBEDDING_PATH):
        if not model_path.is_file():
            raise FileNotFoundError(f"Wake-word model file not found: {model_path}")

    detector = Model(
        wakeword_models=[str(MODEL_PATH)],
        inference_framework="onnx",
        melspec_model_path=str(MELSPECTROGRAM_PATH),
        embedding_model_path=str(EMBEDDING_PATH),
    )
    audio_queue: queue.Queue[np.ndarray] = queue.Queue()

    def receive_audio(indata, frames, time, status) -> None:
        if status:
            print(f"Microphone status: {status}")
        audio_queue.put(indata[:, 0].copy())

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=CHUNK_SAMPLES,
        channels=1,
        dtype="int16",
        callback=receive_audio,
    ):
        while not stop_event.is_set():
            try:
                audio = audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            scores = detector.predict(audio)
            if max(scores.values(), default=0.0) >= threshold:
                return True

    return False
