# Predictive Text Service

A backend service that provides fast word predictions based on user input, inspired by T9-style predictive text systems.

This project is designed as a **learning exercise in software engineering, system design, and data structures**, with a focus on building a **stateful backend service** using clean architecture principles.

---

## 📚 Quick Links

- [Features](#-features)
- [Why this project is interesting](#-why-this-project-is-interesting)
- [Architecture Overview](#-architecture-overview)
- [How it works](#-how-it-works)
- [Request Flow](#-request-flow)
- [Completion Index (Trie)](#-completion-index-trie)
- [Encoding Schemes](#-encoding-schemes)
- [Personalization](#-personalization)
- [API Endpoints](#-api-endpoints)
- [Concurrency Considerations](#-concurrency-considerations)
- [Running the project](#-running-the-project)
- [Demo Flow](#-demo-flow)
- [Learning goals](#-learning-goals)
- [Deployment Notes](#-deployment-notes)
- [Possible extensions](#-possible-extensions)
- [Summary](#-summary)

---

## 🚀 Features

- Predict words from text input (autocomplete-style)
- Predict words from encoded key sequences (T9-style or QWERTY)
- Pluggable encoding schemes
- In-memory completion index (Trie) for fast lookup
- SQLite-backed persistent word repository
- Personalization via user selection tracking
- Clean layered architecture (domain, application, infrastructure, API)

---

## 🧠 Why this project is interesting

Most simple backend apps follow a pattern like:

```
Request → Database → Response
```

This project goes further by introducing a **stateful application layer**:

```
Startup:
    Load data → Build in-memory index → Initialise service

Request:
    Query in-memory index → Return results
```

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

## 🧭 Architecture Overview

```
Client
  ↓
FastAPI (API Layer)
  ↓
WordPredictionService (Application Layer)
  ↓
-----------------------------
| In-Memory Runtime State   |
| - WordStore              |
| - CompletionIndex (Trie) |
-----------------------------
  ↓
SQLite Repository (Persistence)
```

### Key idea

The system separates:

- **Persistent state** → SQLite (source of truth)
- **Runtime state** → in-memory structures for fast access

This allows:
- fast predictions
- consistent updates
- clear separation of responsibilities

---

## ⚙️ How it works

### 1. Data flow

At startup:

1. Database is initialised (with file locking for safety)
2. Repository is created and optionally seeded
3. Words are loaded into memory
4. A completion index (Trie) is built
5. The service is hydrated and stored in app state

---

## 🔁 Request Flow

```
User Input ("he")
    ↓
KeyEncoder (QWERTY)
    ↓
Encoded keys [8, 5]
    ↓
CompletionIndex (Trie lookup)
    ↓
Candidate Word IDs
    ↓
WordStore lookup
    ↓
Response returned
```

---

## 🌳 Completion Index (Trie)

The core data structure is a **Trie (prefix tree)** built over encoded key sequences.

Example:

```
"home" → [8, 15, 13, 5]

Prefixes:
[8]
[8,15]
[8,15,13]
[8,15,13,5]
```

Each prefix maps to candidate word IDs.

### Why a Trie?

- Avoids scanning the entire dataset per request
- Enables efficient prefix lookup
- Provides near O(1) retrieval for prefix queries (after preprocessing)
- Supports incremental updates and ranking

This is a key improvement over naïve approaches like:

```
for word in all_words:
    if word.startswith(prefix):
        ...
```

---

## 🔤 Encoding Schemes

The system supports **pluggable encoding strategies**.

### T9 Encoding

```
h → 4
o → 6
→ "ho" → 46
```

Multiple characters share keys (compressed keyspace).

---

### QWERTY Encoding (default)

```
a → 1
b → 2
...
h → 8
o → 15
→ "ho" → [8, 15]
```

- One-to-one mapping
- Behaves like standard autocomplete

---

### Design Insight

Encoding is abstracted as:

```
(Language, EncodingScheme) → EncodingSpec
```

This allows new encoding strategies to be added without changing core logic.

---

## 🎯 Personalization

The system supports dynamic learning based on user behavior.

### Flow:

```
User selects a word
    ↓
POST /words/{word_id}/select
    ↓
Frequency is incremented
    ↓
Completion index is refreshed
    ↓
Future predictions are re-ranked
```

This enables:

- adaptive suggestions
- frequency-based ranking
- evolving predictions over time

---

## 🌐 API Endpoints

### Prediction

- `GET /predict/text?text=...`
- `GET /predict/keys?keys=...`

---

### Word Management

- `POST /words`
    - Add a new word

- `GET /words/{word_id}`
    - Retrieve word details (includes frequency and source)

- `POST /words/{word_id}/select`
    - Record a user selection (updates ranking)

---

## 🔒 Concurrency Considerations

Database bootstrapping uses a file lock to prevent multiple processes from:

- Creating the schema simultaneously
- Corrupting the database

Implemented using:

```
fcntl.flock + retry loop + timeout
```

This is included as a learning exercise in process-level coordination.


### In-Memory State and Thread Safety

The application maintains shared in-memory state via:

- `WordStore`
- `CompletionIndex`

These structures are mutated during operations such as:

- `POST /words` (adding new words)
- `POST /words/{word_id}/select` (updating frequency and rankings)

Since FastAPI executes requests in a thread pool, multiple requests may access and modify this shared state concurrently.

### Current Behaviour

At present, no explicit synchronization (e.g. locks) is used around these mutations.

This means that in scenarios with concurrent writes, the system may be susceptible to:

- race conditions
- inconsistent intermediate states
- lost updates

For the purposes of this project, this trade-off is acceptable because:

- the system is designed as a learning exercise
- typical usage is low-concurrency (demo environment)
- the architecture prioritizes clarity over completeness

### Possible Improvements

In a production setting, several approaches could be used:

- Introduce a service-level lock (e.g. `threading.Lock`) around mutation operations
- Use a single-threaded worker model for state mutation
- Move to a process-safe or distributed state store
- Adopt an event-driven or queue-based update model

These approaches would ensure consistency while maintaining the performance benefits of the in-memory index.


---

## 📦 Running the project

### Install

```
python -m pip install -e ".[dev]"
```

### Run

```
uvicorn predictive_texting.api.main:app --reload
```

### Swagger UI

```
http://127.0.0.1:8000/docs
```

---

## 🧪 Demo Flow

Try the following sequence:

1. Add a new word:

    POST /words
    {
        "word": "foobar"
    }

2. Predict:

    GET /predict/text?text=foo

3. Record selection using the returned `word_id`:

    POST /words/{word_id}/select

4. Retrieve the word:

    GET /words/{word_id}

    The response should show the updated frequency.

5. Predict again:

    GET /predict/text?text=foo

→ `foobar` should be present in the results, and repeated selections should increase its frequency and improve its ranking over time.

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

## 🚧 Deployment Notes

This project uses SQLite for simplicity.

On platforms like Render or similar container-based environments:

- The database file may not persist across restarts
- Data may be lost on redeploy

For production use, a persistent database (e.g. PostgreSQL) would be required.

---

## 🔮 Possible extensions

- Add new encoding schemes (multi-language support)
- Improve ranking (recency, personalization, ML-based scoring)
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
- Implementing adaptive, personalized backend behaviour