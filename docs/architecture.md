# System Architecture — Lost & Found AI Application

This document outlines the software architecture, design patterns, and component interactions of the **Lost & Found AI Application**.

---

## 1. High-Level Overview

The system provides intelligent image-based lost & found item registration, feature extraction (via Vision-Language Models), semantic vector embedding generation, and similarity matching across items.

```
                    ┌─────────────────────────┐
                    │   User Interfaces       │
                    │   (CLI / REST API)      │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   Service & Concurrency │
                    │   (Batch Processing)    │
                    └───────────┬─────────────┘
                                │
             ┌──────────────────┴──────────────────┐
             ▼                                     ▼
┌─────────────────────────┐           ┌─────────────────────────┐
│  AI Module (Provided)   │           │   Storage & Persistence │
│  (VLM & Embeddings)     │           │   (PostgreSQL & Images) │
└─────────────────────────┘           └─────────────────────────┘
```

---

## 2. Component Layers

### A. Presentation Layer (`src/cli.py` & `src/api.py`)
- **CLI Interface**: Terminal-based administration for single/batch processing, item matching, and benchmark execution.
- **REST API (FastAPI)**: HTTP endpoints for registration, item lookup, and semantic search queries.

### B. Core & Configuration (`src/config.py`, `src/models.py`)
- **Config Management**: Environment variable validation and application settings using `pydantic-settings`.
- **Data Schemas**: Strongly typed Pydantic dataclasses/models across boundaries (`ItemRegistration`, `ItemMatchResult`, `ItemCategory`).

### C. Concurrency Pipeline (`src/concurrency/pipeline.py`)
- **Bounded Concurrency**: Implements `asyncio.gather()` with `asyncio.Semaphore` to process item batches concurrently while respecting provider rate limits and database connections.

### D. AI Service Layer (`src/services/ai_service.py`)
- Treats the provided `ai/` package as an isolated boundary.
- Orchestrates Vision-Language Models (VLM) for item description/category extraction.
- Generates vector embeddings for visual and textual semantic matching.

### E. Storage Layer (`src/storage/`)
- **Database (`database.py`)**: Async SQLAlchemy / Asyncpg connection management and schema migration.
- **Repository (`repository.py`)**: Data access layer for CRUD operations on Lost/Found items and embedding vectors.
- **Image Storage (`image_storage.py`)**: Handles local/cloud file storage and validation for uploaded item images.

---

## 3. Data Flow & Processing Pipeline

1. **Upload / Registration**: User submits an item image with optional category & location metadata via CLI or REST API.
2. **AI Analysis**: `AIService` passes the image to the VLM provider to extract category, color, key visual attributes, and description.
3. **Embedding Generation**: Text and visual attributes are converted into high-dimensional vector embeddings.
4. **Storage**: Item record and embedding vector are saved to the repository.
5. **Matching Engine**: Cosine similarity is computed between query item embeddings and stored items to return top-ranked potential matches.

---

## 4. Architectural Principles

- **Clean Boundaries**: The `ai/` module interface is kept strictly isolated from core business logic.
- **Async Concurrency**: Asynchronous I/O across database operations and external API requests.
- **Provider Agnostic**: Factory pattern abstracts AI providers (OpenAI, Anthropic, Gemini).
- **Robust Error Handling**: Structured logging, exponential backoff retries, and graceful fallback mechanisms.
