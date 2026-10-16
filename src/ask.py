"""Ask questions about the fictional Sunrise Bakes documents."""

from pathlib import Path
import os
import re
import sys
import tempfile
import threading
import tkinter as tk

from dotenv import load_dotenv
from openai import OpenAI
import pyttsx3
import sounddevice as sd
import soundfile as sf


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


def AIspeak(text: str) -> None:
    """Read the answer aloud using a voice installed on Windows."""
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()


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


def listen(duration: float | None = None) -> str:
    """Record a microphone clip and transcribe it with OpenAI."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        raise RuntimeError("Set OPENAI_API_KEY in your local .env file first.")

    sample_rate = 16_000
    duration = duration or float(os.getenv("RECORD_SECONDS", "6"))
    print(f"Listening for up to {duration:g} seconds...")
    recording = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
    )
    sd.wait()
    return transcribe_recording(recording, sample_rate, api_key)


def contains_wake_word(text: str) -> bool:
    """Return whether a transcript contains the phrase 'hi GPT'."""
    return bool(re.search(r"\bhi\s+gpt\b", text, re.IGNORECASE))


def run_wake_word_loop(update_status, stop_event: threading.Event) -> None:
    """Listen in short clips until stopped or 'hi GPT' is detected."""
    while not stop_event.is_set():
        update_status('Listening for "hi GPT"...')
        transcript = listen(duration=2)
        if contains_wake_word(transcript):
            update_status("Wake word detected. Ask your question...")
            question = listen()
            if question.strip():
                update_status("Thinking...")
                answer = ask(question)
                print(f"You asked: {question}\n{answer}")
                AIspeak(answer)


def start_window() -> None:
    """Show a window that toggles wake-word listening on and off."""
    root = tk.Tk()
    root.title("Sunrise Bakes Assistant")
    root.geometry("360x180")

    status = tk.StringVar(value="Off")
    stop_event = threading.Event()
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
            args=(update_status, stop_event),
            daemon=True,
        )
        worker.start()
        status.set('Listening for "hi GPT"...')

    def stop_listening() -> None:
        stop_event.set()
        status.set("Off")

    tk.Label(root, textvariable=status, wraplength=320).pack(pady=25)
    tk.Button(root, text="Start listening", command=start_listening).pack()
    tk.Button(root, text="Stop listening", command=stop_listening).pack(pady=8)
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        question = " ".join(sys.argv[1:])
        print(f"You asked: {question}")
        answer = ask(question)
        print(answer)
        AIspeak(answer)
    else:
        start_window()
