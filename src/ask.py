"""Ask questions about the fictional Sunrise Bakes documents."""

from pathlib import Path
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI


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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python src/ask.py "Your question"')
        raise SystemExit(1)

    print(ask(" ".join(sys.argv[1:])))
