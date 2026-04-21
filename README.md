# Emotional Companion

A desktop AI emotional-support chatbot built with Python, PyQt6, Groq, and local RAG.

This project is designed to feel more like a caring friend than a generic chatbot. It combines empathetic prompting, a friend-style response rewrite layer, safety checks for high-risk messages, and retrieval from a small mental-health support knowledge base.

---

## Features

- Desktop chat application built with PyQt6
- Emotional companion style responses
- Local RAG with FAISS + SentenceTransformers
- Friend-style response rewriting for more natural replies
- Safety detection for high-risk or self-harm related messages
- Cached document indexing for faster startup
- PowerShell-friendly testing workflow

---

## Project Goal

The goal of this project is to build a more emotionally supportive chatbot that feels warm, natural, and present during difficult conversations.

Instead of replying like a generic assistant, the chatbot is designed to:
- sound softer and more human
- avoid robotic therapy-style language
- stay grounded in helpful mental-health support documents
- respond more safely in crisis-like situations

---

## Tech Stack

- Python 3.13
- PyQt6
- Groq API
- SentenceTransformers
- FAISS
- JSON-based local data storage

---

## Project Structure

```text
emotional-companion/
├── app.py
├── prompts.py
├── rag_engine.py
├── safety.py
├── requirements.txt
├── README.md
├── data/
│   ├── users.json
│   └── rag_cache/
└── evals/
    ├── eval_prompts.json
    └── quick_eval.py
```

### File Overview

- `app.py`  
  Main desktop application UI and chat flow.

- `prompts.py`  
  Stores the main system prompt, friend-style examples, and rewrite prompt builder.

- `rag_engine.py`  
  Handles document loading, chunking, embeddings, FAISS indexing, caching, and retrieval.

- `safety.py`  
  Detects high-risk language and returns a safety-first response.

- `evals/quick_eval.py`  
  Runs quick retrieval checks using sample emotional prompts.

---

## How It Works

### 1. User sends a message
The desktop app receives the user input and passes it into the response pipeline.

### 2. Safety check runs first
If the message contains high-risk self-harm or suicide-related language, the chatbot returns a safety-first reply instead of continuing normal generation.

### 3. RAG retrieves support context
If the message is not high-risk, the local RAG engine searches the emotional-support documents and retrieves the most relevant chunks.

### 4. Main response is generated
The main model creates a helpful draft response using:
- the conversation history
- the system prompt
- the retrieved RAG context when useful

### 5. Reply is rewritten into friend style
A second prompt rewrites the draft into a warmer, shorter, more natural emotional-support reply.

---

## Documents Used for RAG

This project uses a small curated set of emotional-support and self-help documents in `.txt` format.

Example sources:
- WHO stress and grounding guide
- CBT workbook material
- anxiety and depression self-help content
- local crisis or mental health helpline information

The RAG system is intentionally kept small and curated to improve retrieval quality and reduce noisy results.

---

## Installation

### 1. Open the project folder

```powershell
cd "D:\HND NIBM\PetChat-2.0\emotional-companion"
```

### 2. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 3. Add your API key

Set your Groq API key in PowerShell before running the app:

```powershell
$env:GROQ_API_KEY="your_api_key_here"
```

If your code later uses Gemini directly, you can also set:

```powershell
$env:GEMINI_API_KEY="your_api_key_here"
```

---

## Running the Project

### Launch the desktop app

```powershell
python app.py
```

### Run RAG test directly

```powershell
python rag_engine.py
```

### Run quick eval checks

```powershell
python .\evals\quick_eval.py
```

---

## PowerShell Verification Checks

Use these commands to confirm the new implementations are working.

### Check imports

```powershell
python -c "import prompts, safety, rag_engine; print('imports ok')"
```

### Check prompt system

```powershell
python -c "from prompts import SYSTEM_PROMPT, build_rewrite_prompt; print('SYSTEM OK' if SYSTEM_PROMPT else 'SYSTEM MISSING'); print(build_rewrite_prompt('I feel alone', 'That sounds difficult.')[:300])"
```

### Check safety detection

```powershell
python -c "from safety import detect_risk_level; print(detect_risk_level('I want to die')); print(detect_risk_level('I hate myself')); print(detect_risk_level('I had a bad day'))"
```

Expected output:

```text
high
moderate
none
```

### Check RAG retrieval

```powershell
python -c "from rag_engine import build_rag_context; print(build_rag_context('I feel overwhelmed and need grounding')[:1200])"
```

---

## Current Improvements

Today’s work added:

- a stronger prompt architecture
- friend-style response examples
- a rewrite layer for making replies sound more human
- a dedicated safety module
- local retrieval testing
- project cleanup for PowerShell-based debugging

These changes make the chatbot feel less robotic and more emotionally supportive.

---

## Safety Note

This project is an emotional-support companion, not a therapist, doctor, or emergency service.

It should not:
- diagnose mental illness
- replace professional support
- give medical advice
- act as the only source of help in crisis situations

For high-risk or crisis-related messages, the app should encourage real-world support such as trusted people, emergency services, or crisis helplines.

Sri Lanka mental health support example:
- National Mental Health Helpline: 1926

---

## Known Issues

- The Hugging Face warning about unauthenticated requests is not a failure; it only affects rate limits for downloads.
- The `embeddings.position_ids | UNEXPECTED` message can appear when loading the embedding model and is usually harmless if the model still loads correctly.
- RAG retrieval for loneliness-related prompts may still need tuning for better emotional relevance.

---

## Future Improvements

- Better loneliness-specific retrieval
- More friend-style training examples
- Better crisis escalation flow
- Chat memory improvements
- Better UI polish and message streaming
- Optional mood journaling
- Optional voice features

---

## Author Notes

This project is being built as a focused emotional companion chatbot that feels more human, more supportive, and more specific than many generic chatbots.

The aim is not just to build another chatbot, but to build one that can respond with warmth, steadiness, and better emotional presence.

---
