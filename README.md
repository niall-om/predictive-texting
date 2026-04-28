# Predictive Text Service

A backend service that provides fast word predictions based on user input, inspired by T9-style predictive text systems.

This project is designed as a **learning exercise in software engineering, system design, and data structures**, with a focus on building a **stateful backend service** using clean architecture principles.

---

## 🚀 Features

- Predict words from text input (autocomplete-style)
- Predict words from encoded key sequences (T9-style)
- Pluggable encoding schemes (T9 and QWERTY)
- In-memory completion index for fast lookup
- SQLite-backed persistent word repository
- Clean layered architecture (domain, application, infrastructure, API)

---

## 🧠 Why this project is interesting

Most simple backend apps follow a pattern like:

    Request → Database → Response

This project goes further by introducing a **stateful application layer**:

    Startup:
        Load data → Build in-memory index → Initialise service

    Request:
        Query in-memory index → Return results

### Key ideas explored:

- **Stateful backend design**  
  The service maintains an in-memory index across requests instead of recomputing on every call.

- **Separation of concerns**  
  Clear boundaries between:
  - Domain logic
  - Application orchestration
  - Infrastructure (database, locking)
  - API layer

- **In-memory vs persistent storage**
  - SQLite stores the source-of-truth data
  - In-memory structures provide fast lookup performance

- **Bootstrapping and lifecycle management**
  - Service is constructed once at startup
  - FastAPI lifespan hook manages this cleanly

---

## ⚙️ How it works

### 1. Data flow

At startup:

1. Database is initialised (with file locking for safety)
2. Repository is created and optionally seeded
3. Words are loaded into memory
4. A completion index (Trie) is built
5. The service is hydrated and stored in app state

At request time:

1. Input is encoded into a sequence of keys
2. The completion index is queried
3. Candidates are ranked and returned

---

## 🌳 Completion Index (Trie)

The core data structure is a **Trie (prefix tree)** built over encoded key sequences.

Example:

    "home" → [8, 15, 13, 5]

    Prefixes:
    [8]
    [8,15]
    [8,15,13]
    [8,15,13,5]

Each prefix maps to candidate word IDs.

### Why a Trie?

- Avoids scanning the entire dataset per request
- Enables efficient prefix lookup
- Provides near O(1) retrieval for prefix queries (after preprocessing)
- Supports incremental updates and ranking

This is a key improvement over naïve approaches like:

    for word in all_words:
        if word.startswith(prefix):
            ...

---

## 🔤 Encoding Schemes

The system supports **pluggable encoding strategies**.

### T9 Encoding

    h → 4
    o → 6
    → "ho" → 46

Multiple characters share keys (compressed keyspace).

### QWERTY Encoding (default)

    a → 1
    b → 2
    ...
    h → 8
    o → 15
    → "ho" → [8, 15]

- One-to-one mapping
- Behaves like standard autocomplete

### Design Insight

Encoding is abstracted as:

    (Language, EncodingScheme) → EncodingSpec

This allows new encoding strategies to be added without changing core logic.

---

## 🧱 Architecture

    api/
        FastAPI endpoints

    application/
        WordPredictionService (orchestration layer)

    domain/
        Core business logic (encoding, lexicon, trie)

    infrastructure/
        SQLite repository, bootstrapping, locking

### Key Principles

- Domain is independent of infrastructure
- Application layer coordinates use-cases
- Infrastructure handles persistence and external concerns
- API layer is thin and delegates to the service

---

## 🔒 Concurrency Considerations

Database bootstrapping uses a file lock to prevent multiple processes from:

- Creating the schema simultaneously
- Corrupting the database

This is implemented using:

    fcntl.flock + retry loop + timeout

This is intentionally included as a learning exercise in process-level coordination.

---

## 📦 Running the project

### Install

    python -m pip install -e ".[dev]"

### Run

    uvicorn predictive_texting.api.main:app --reload

---

## 🧪 Example usage

### Health check

    curl "http://127.0.0.1:8000/health"

### Predict by text (QWERTY)

    curl "http://127.0.0.1:8000/predict/text?text=he"

Example response:

    {
      "query": "he",
      "candidates": [
        {"word_id": 2078, "word": "he"},
        {"word_id": 2105, "word": "her"},
        {"word_id": 2113, "word": "hey"},
        ...
      ]
    }

---

### Predict by encoded keys

    curl "http://127.0.0.1:8000/predict/keys?keys=12"

Under QWERTY:

    1 → a
    2 → b
    → "ab"

---

## 📚 Learning goals

This project was built to explore:

- Designing stateful backend services
- Using in-memory data structures alongside databases
- Applying clean architecture principles
- Implementing Trie-based indexing
- Understanding encoding abstractions
- Managing application lifecycle in FastAPI
- Handling concurrency during bootstrapping

---

## 🔮 Possible extensions

- Add new encoding schemes (multi-language support)
- Improve ranking (recency, personalization)
- Add UI for interactive demo
- Introduce async database layer
- Scale to multi-worker or distributed setup
- Add caching layers

---

## ⚠️ Notes

- This is a learning/portfolio project, not production-ready
- Some design choices are intentionally simple
- Focus is on clarity, correctness, and design thinking

---

## 💡 Summary

This project demonstrates:

- Moving beyond CRUD APIs into stateful system design
- Clean separation between domain, application, and infrastructure
- Use of data structures (Trie) for real performance gains
- Designing extensible, pluggable systems