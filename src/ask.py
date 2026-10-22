"""Ask questions about the fictional Sunrise Bakes documents."""

from pathlib import Path
import os
import queue
import sys
import tempfile
import time
import threading
import tkinter as tk
import wave
import winsound

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
import pyttsx3
import sounddevice as sd
import soundfile as sf
from wake_word import wait_for_wake_word


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def load_documents() -> str:
    """Combine the bakery's Markdown documents into one reference text."""
    documents = []
    for path in sorted(DATA_DIR.glob("*.md")):
        documents.append(f"\n--- {path.name} ---\n{path.read_text(encoding='utf-8')}")
    return "".join(documents)


def ask(question: str) -> str:
    """Send a question and the reference documents to the language model."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        raise RuntimeError("Set OPENAI_API_KEY in your local .env file first.")

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    reference_text = load_documents()

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the Sunrise Bakes assistant. Answer the user's question using only "
                    "the provided documents. Include relevant additional details from the "
                    "documents, such as item size, quantity, ingredients, availability, or "
                    "ordering requirements, when they helpfully clarify the answer. Do not add unrelated information or guess. If the "
                    "documents do not contain the answer, say you do not know. Answer "
                    "directly without repeating the user's question. For example, for the "
                    "question 'What are the main ingredients in the garlic herb focaccia?', "
                    "do not write 'The main ingredients in the garlic herb focaccia are ...'. "
                    "Instead, write 'Wheat flour, water, olive oil, garlic, herbs, yeast, and "
                    "salt.'\n\n"
                    f"DOCUMENTS:\n{reference_text}"
                ),
            },
            {"role": "user", "content": question},
        ],
    )
    return response.choices[0].message.content or "I could not generate an answer."


def speak_local(text: str) -> None:
    """Read the answer aloud using a voice installed on Windows."""
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()


def speak_cloud(text: str) -> None:
    """Generate and play speech through the OpenAI audio API."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        raise RuntimeError("Set OPENAI_API_KEY in your local .env file first.")

    client = OpenAI(api_key=api_key)
    response = client.audio.speech.create(
        model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
        voice=os.getenv("OPENAI_TTS_VOICE", "coral"),
        input=text,
        response_format="pcm",
        instructions="Speak clearly, warmly, and naturally.",
    )

    audio_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio_file:
            audio_path = audio_file.name
        with wave.open(audio_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(24_000)
            wav_file.writeframes(response.read())
        winsound.PlaySound(audio_path, winsound.SND_FILENAME)
    finally:
        if audio_path:
            os.unlink(audio_path)


def speak(text: str, voice_type: str = "local") -> None:
    """Speak an answer using the selected local or cloud voice."""
    if voice_type == "cloud":
        speak_cloud(text)
    else:
        speak_local(text)


def transcribe_recording(recording, sample_rate: int, api_key: str) -> str:
    """Save a recording temporarily and transcribe it with OpenAI."""
    audio_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio_file:
            audio_path = audio_file.name
        sf.write(audio_path, recording, sample_rate, subtype="PCM_16")
        client = OpenAI(api_key=api_key)
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model=os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"),
                file=audio_file,
            )
        return transcript.text
    finally:
        if audio_path:
            os.unlink(audio_path)


def listen(duration: float | None = None, on_question_complete=None) -> str:
    """Record until speech ends, then transcribe it with OpenAI."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        raise RuntimeError("Set OPENAI_API_KEY in your local .env file first.")

    sample_rate = 16_000
    duration = duration or float(os.getenv("RECORD_SECONDS", "6"))
    frame_size = int(sample_rate * 0.1)
    silence_threshold = float(os.getenv("QUESTION_SILENCE_THRESHOLD", "0.005"))
    silence_seconds = float(os.getenv("QUESTION_END_SILENCE_SECONDS", "0.8"))
    audio_queue = queue.Queue()

    def receive_audio(indata, frames, time_info, status) -> None:
        if status:
            print(f"Microphone status: {status}")
        audio_queue.put(indata[:, 0].copy())

    print(f"Listening for up to {duration:g} seconds...")
    recording = []
    speech_started = False
    silence_started = None
    start_time = time.monotonic()
    with sd.InputStream(
        samplerate=sample_rate,
        blocksize=frame_size,
        channels=1,
        dtype="int16",
        callback=receive_audio,
    ):
        while time.monotonic() - start_time < duration:
            try:
                frame = audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            normalized_frame = frame.astype(np.float32) / np.iinfo(np.int16).max
            volume = float(np.sqrt(np.mean(normalized_frame**2)))
            if volume >= silence_threshold:
                if not speech_started:
                    speech_started = True
                recording.append(frame)
                silence_started = None
            elif speech_started:
                recording.append(frame)
                if silence_started is None:
                    silence_started = time.monotonic()
                elif time.monotonic() - silence_started >= silence_seconds:
                    break

    if not speech_started:
        print("No question detected.")
        return ""
    if on_question_complete:
        on_question_complete()
    return transcribe_recording(np.concatenate(recording), sample_rate, api_key)


def run_wake_word_loop(
    update_status,
    stop_event: threading.Event,
    get_voice_type,
) -> None:
    """Wait locally for the wake word, then transcribe and answer a question."""
    while not stop_event.is_set():
        update_status('Listening locally for "yo pikachu"...')
        if wait_for_wake_word(stop_event):
            update_status("Wake word detected. Ask your question. Listening for a few seconds...")
            question = listen(
                on_question_complete=lambda: update_status("Heard you - thinking..."),
            )
            if question.strip():
                update_status("Thinking...")
                answer = ask(question)
                print(f"You asked: {question}\n{answer}")
                speak(answer, get_voice_type())
            else:
                update_status('Listening locally for "yo pikachu"...')


def start_window() -> None:
    """Show a window that toggles wake-word listening on and off."""
    root = tk.Tk()
    root.title("Sunrise Bakes Assistant")
    root.geometry("420x240")

    status = tk.StringVar(value="Off")
    stop_event = threading.Event()
    settings_state = {"voice_type": "local"}
    worker = None

    def update_status(message: str) -> None:
        root.after(0, status.set, message)

    def start_listening() -> None:
        nonlocal worker
        if worker and worker.is_alive():
            return
        stop_event.clear()
        worker = threading.Thread(
            target=run_wake_word_loop,
            args=(update_status, stop_event, lambda: settings_state["voice_type"]),
            daemon=True,
        )
        worker.start()
        status.set('Listening locally for "yo pikachu"...')

    def stop_listening() -> None:
        stop_event.set()
        status.set("Off")

    tk.Label(root, textvariable=status, wraplength=320).pack(pady=25)
    tk.Button(root, text="Start listening", command=start_listening).pack()
    tk.Button(root, text="Stop listening", command=stop_listening).pack(pady=8)

    def show_settings() -> None:
        settings = tk.Toplevel(root)
        settings.title("Settings")
        settings.geometry("360x320")

        tk.Label(settings, text="Voice type").pack(anchor="w", padx=20, pady=(18, 4))
        voice_type = tk.StringVar(value=settings_state["voice_type"])

        def update_voice_type() -> None:
            settings_state["voice_type"] = voice_type.get()

        tk.Radiobutton(
            settings,
            text="Local",
            variable=voice_type,
            value="local",
            command=update_voice_type,
        ).pack(anchor="w", padx=35)
        tk.Radiobutton(
            settings,
            text="Cloud (higher billing)",
            variable=voice_type,
            value="cloud",
            command=update_voice_type,
        ).pack(anchor="w", padx=35)

        tk.Label(settings, text="Mode").pack(anchor="w", padx=20, pady=(18, 4))
        mode = tk.StringVar(value="work")
        attachment_area = tk.Frame(settings)
        tk.Radiobutton(
            settings,
            text="Personal",
            variable=mode,
            value="personal",
        ).pack(anchor="w", padx=35)
        tk.Radiobutton(
            settings,
            text="Work",
            variable=mode,
            value="work",
        ).pack(anchor="w", padx=35)

        def update_attachment_option(*_args) -> None:
            if mode.get() == "work":
                attachment_area.pack(anchor="w", padx=55, pady=(4, 0))
            else:
                attachment_area.pack_forget()

        mode.trace_add("write", update_attachment_option)
        tk.Button(
            attachment_area,
            text="+  Attach documents",
        ).pack()
        update_attachment_option()

    tk.Button(root, text="Settings", command=show_settings).pack(pady=8)
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        question = " ".join(sys.argv[1:])
        print(f"You asked: {question}")
        answer = ask(question)
        print(answer)
        speak(answer)
    else:
        start_window()
