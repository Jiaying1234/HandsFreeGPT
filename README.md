# Hi GPT: Voice Assistant That Answers From Your Documents

> Ask a question, get an answer based on a business's own documents. Hands-free is next.

## The Problem
Bakery staff have messy hands and busy shifts. Looking up allergens, prices or
policies on a phone is slow and unhygienic.

## The Solution
An assistant that answers questions using only the business's own documents,
and says "I don't have that information" instead of guessing.

## Demo
🚧 Coming soon

## Sample Data Notice
All business data in /data is fictional sample data for a made-up bakery
("Sunrise Bakes"). Allergen information is NOT real safety advice.

## Why Not Alexa, Google Home or Siri?
- Customisable: I control the model, prompt and personality
- Pay-per-use: no monthly subscription
- Specialised: built for hands-busy work like baking
- Extensible: swap in any business's documents
- Transparent: open source, so you can see what happens to your data

## Roadmap
- [done] M1: Typed Q&A from documents
- [done] M2: Test set and accuracy score
- [done] M3: AI voices answers (generate the text ans and convert it to MP3)
- [ ] M4: Voice input and wake word
- [ ] M5: Proper retrieval for larger document sets
- [ ] M6: Raspberry Pi / hardware version

## Setup
1. Clone the repo
2. Create a virtual environment and `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and add your API key
4. `python src/ask.py "What is the price of a sourdough loaf?"`

The answer is printed in the terminal and read aloud using a voice installed
on Windows. The text answer requires an internet connection for the OpenAI
API; the speech step runs locally.

To use voice input, run `python src/ask.py` without a question argument. A
window lets you turn wake-word listening on or off. When listening is on, the
program checks short microphone recordings for "hi GPT", then records and
answers the next question. Set `RECORD_SECONDS` in `.env` to change the
question recording length.

## What I Learned
1. Use onnx file instead of tflite bcs:
We are already developing in Python on Windows
ONNX Runtime is straightforward to install
It matches the notebook’s original trained output
TFLite is more useful later for smaller embedded devices
The .tflite file is still valuable as a backup or for a future Raspberry Pi/embedded version.
