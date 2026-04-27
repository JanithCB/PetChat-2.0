# PetChat 2.0

PetChat 2.0 is a desktop AI emotional-support chatbot built with Python and PyQt6. It is designed to feel more like a calm, caring companion than a generic chatbot, while supporting both local and cloud language models, local RAG, an integrated emotion classifier, and a future-ready Supabase memory layer.

---

## Features

- Desktop chat app built with PyQt6
- Two conversation modes:
  - Get Support
  - Help Someone
- Local models through Ollama
- Cloud models through OpenAI-compatible APIs
- Local RAG over `cleaned_txt/`
- Safety-aware response flow for higher-risk messages
- Emotion classification integrated into the chat pipeline
- Warm friend-style prompting and rewrite layer
- Minimal Supabase integration for future conversation memory
- Simple multi-screen UI:
  - Auth
  - Model Setup
  - Chat

---

## Project Goal

The goal of PetChat 2.0 is to create a more emotionally supportive chatbot that feels warm, steady, and practical during difficult conversations.

Instead of sounding robotic or overly clinical, the assistant is designed to:
- respond in a softer and more natural tone
- avoid diagnosis and therapist-like language
- handle emotional support more safely
- use retrieved wellbeing content when helpful
- adapt tone using detected emotional signals
- support both people seeking help and people helping someone else

---

## Modes

### Get Support
This mode is for users talking about their own feelings, stress, anxiety, loneliness, or emotional struggles.

The system focuses on:
- empathy first
- gentle follow-up
- calm emotional support
- minimal advice overload
- classifier-informed tone when helpful

### Help Someone
This mode is for users who want help supporting a friend, partner, family member, or someone else.

The system focuses on:
- how to respond supportively
- what practical steps to suggest
- when to encourage professional help
- using RAG more often for grounded support guidance
- keeping the assistant clearly in helper mode

---

## Tech Stack

- Python 3
- PyQt6
- Ollama
- OpenAI-compatible cloud APIs
- Hugging Face Transformers
- PyTorch
- FAISS
- NumPy
- Supabase Python client
- python-dotenv

---

## Current Project Structure

```text
PetChat-2.0/
├── .venv/
├── cleaned_txt/
├── data/
├── documents/
├── src/
│   ├── __init__.py
│   ├── app.py
│   ├── config.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── emotion_classifier.py
│   │   ├── emotion_model/
│   │   │   ├── config.json
│   │   │   ├── tokenizer_config.json
│   │   │   ├── tokenizer.json
│   │   │   ├── special_tokens_map.json
│   │   │   └── model.safetensors
│   │   ├── pipeline.py
│   │   ├── prompts.py
│   │   ├── providers.py
│   │   └── safety.py
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── eval_prompts.json
│   │   └── quick_eval.py
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── conversation_store.py
│   │   └── supabase_client.py
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── rag_engine.py
│   │   └── retriever.py
│   └── ui/
│       ├── __init__.py
│       ├── auth_page.py
│       ├── chat_page.py
│       ├── main_window.py
│       ├── model_setup_page.py
│       └── styles.py
├── .env
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Core Flow

### 1. User starts the app
The desktop app opens with a simple UI flow:
- Auth page
- Model setup page
- Chat page

### 2. Mode and model are selected
The user chooses:
- Get Support or Help Someone
- Local or cloud model

### 3. Safety check runs first
Each user message is checked for higher-risk language before normal generation continues.

### 4. Emotion classification runs on normal turns
If the message is not high-risk, the classifier predicts an emotional tone such as sadness, anxiety, stress, anger, confusion, calm, or positive mood.

This signal is used to:
- improve the internal support plan
- shape prompt tone more accurately
- keep replies warmer and more emotionally aware

If the classifier is unavailable or fails, the system falls back safely to the existing rule-based behavior.

### 5. RAG is used when appropriate
Local RAG searches the `cleaned_txt/` wellbeing documents when support context is useful, especially in Help Someone mode and longer guidance-heavy turns.

### 6. Draft response is generated
The selected model creates a first response using:
- system instructions
- example style turns
- recent history
- optional RAG context
- classifier-informed tone guidance

### 7. Reply is rewritten into final style
A rewrite step makes the response sound warmer, shorter, more natural, and more chat-friendly.

---

## Configuration

Main configuration lives in:

```text
src/config.py
```

Typical settings include:
- local model options
- cloud provider settings
- RAG feature flags
- Supabase feature flags
- emotion classifier feature flags
- UI constants
- root paths for `cleaned_txt/` and cache directories

Environment variables are stored in:

```text
.env
```

Example:

```env
OLLAMA_BASE_URL=http://localhost:11434
RAG_ENABLED=true
USE_SUPABASE_MEMORY=true
USE_EMOTION_CLASSIFIER=true
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key
```

---

## Installation

### 1. Open the project folder

```powershell
cd "D:\HND NIBM\PetChat-2.0"
```

### 2. Create and activate the virtual environment

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Start Ollama

```powershell
ollama serve
```

In another terminal, pull the required models if needed:

```powershell
ollama pull phi4-mini:latest
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

---

## Running the Project

### Launch the desktop app

```powershell
python -m src.app
```

### Run CLI mode

```powershell
python -m src.app --cli --model phi4-mini:latest
```

### Run without RAG

```powershell
python -m src.app --no-rag
```

The emotion classifier does not require a separate startup command. It is loaded inside the normal chat pipeline and is designed to remain optional.

---

## Supabase Setup

PetChat 2.0 includes a minimal Supabase memory layer for storing conversation history.

Current memory support includes:
- lazy client setup
- saving messages
- loading recent history

Supabase is optional. If it is disabled or not configured, memory functions fall back safely without crashing the app.

Tables are expected to be created manually in the Supabase SQL Editor.

---

## Safety Note

PetChat 2.0 is an emotional-support companion, not a therapist, doctor, or emergency service.

It should not:
- diagnose mental illness
- replace professional care
- provide medical advice
- act as the only source of help in a crisis

For higher-risk situations, the app should guide the user toward trusted people, crisis support, or emergency services.

Safety always stays ahead of emotion classification, RAG, and generation.

---

## Current Status

Current implementation work includes:
- UI screens through the chat page
- prompt system
- provider abstraction
- safety module
- chat pipeline
- local RAG engine
- integrated emotion classifier
- minimal Supabase client and conversation store

The architecture is set up so future work can expand:
- memory
- evaluation
- UI polish
- richer support planning
- richer analytics around emotion trends
- better long-term memory handling

---

## Future Improvements

- Better conversation memory integration
- More polished chat pacing and streaming
- Better retrieval tuning for emotional support
- Stronger guided-help prompting
- Richer evaluation workflows
- Better Supabase-backed long-term memory
- Optional journaling or mood tracking
- Internal analytics such as emotion-over-time views
- More refined support planning and prompt adaptation

---

## Author Note

PetChat 2.0 is being built as a focused emotional companion that feels warmer, steadier, and more human than a generic assistant.

The aim is not just to build another chatbot, but to build one that can support difficult conversations with more care, emotional presence, and practical structure.
