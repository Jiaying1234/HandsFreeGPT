"""Local wake-word detection for the custom "yo pikachu" and "hi gpt" models."""

from pathlib import Path
import queue
import threading

import numpy as np
import sounddevice as sd
from openwakeword.model import Model


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
MELSPECTROGRAM_PATH = MODELS_DIR / "melspectrogram.onnx"
EMBEDDING_PATH = MODELS_DIR / "embedding_model.onnx"
SAMPLE_RATE = 16_000
CHUNK_SAMPLES = 1_280
WAKE_WORDS = {
    "yo_pikachu": {
        "label": "yo pikachu",
        "path": MODELS_DIR / "yo_pee_kah_choo.onnx",
    },
    "hi_gpt": {
        "label": "hi gpt",
        "path": MODELS_DIR / "hi_G_P_T.onnx",
    },
}


def wake_word_label(wake_word: str) -> str:
    """Return the spoken phrase for a wake-word setting."""
    return WAKE_WORDS.get(wake_word, WAKE_WORDS["yo_pikachu"])["label"]


def wait_for_wake_word(
    stop_event: threading.Event,
    wake_word: str = "yo_pikachu",
    get_wake_word=None,
    threshold: float = 0.5,
) -> bool:
    """Listen locally until the selected wake word is detected or listening stops.

    Returns False when listening is stopped or the selected wake word changes,
    so the caller can reload the matching model.
    """
    selected = WAKE_WORDS.get(wake_word, WAKE_WORDS["yo_pikachu"])
    model_path = selected["path"]
    for path in (model_path, MELSPECTROGRAM_PATH, EMBEDDING_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Wake-word model file not found: {path}")

    detector = Model(
        wakeword_models=[str(model_path)],
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
            if get_wake_word is not None and get_wake_word() != wake_word:
                return False
            try:
                audio = audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            scores = detector.predict(audio)
            if max(scores.values(), default=0.0) >= threshold:
                return True

    return False
