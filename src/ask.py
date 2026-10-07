"""Ask questions about the fictional Sunrise Bakes documents."""

from pathlib import Path
import os
import sys
import tempfile

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


def listen() -> str:
    """Record a short microphone clip and transcribe it with OpenAI."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        raise RuntimeError("Set OPENAI_API_KEY in your local .env file first.")

    sample_rate = 16_000
    duration = float(os.getenv("RECORD_SECONDS", "6"))
    print(f"Listening for up to {duration:g} seconds...")
    recording = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
    )
    sd.wait()

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


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) if len(sys.argv) >= 2 else listen()
    print(f"You asked: {question}")
    answer = ask(question)
    print(answer)
    AIspeak(answer)
