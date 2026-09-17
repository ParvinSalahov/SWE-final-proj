"""Benchmark script for the Lost & Found application.

This script benchmarks:
- AI provider performance (VLM and embedding)
- Database operations
- Concurrency pipeline performance
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Ensure environment variables are set for AI providers
# These must be set BEFORE importing the ai module
if os.getenv("LLM_PROVIDER"):
    os.environ["LLM_PROVIDER"] = os.getenv("LLM_PROVIDER")
if os.getenv("LLM_MODEL"):
    os.environ["LLM_MODEL"] = os.getenv("LLM_MODEL")
if os.getenv("EMBEDDING_PROVIDER"):
    os.environ["EMBEDDING_PROVIDER"] = os.getenv("EMBEDDING_PROVIDER")
if os.getenv("EMBEDDING_MODEL"):
    os.environ["EMBEDDING_MODEL"] = os.getenv("EMBEDDING_MODEL")
if os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
if os.getenv("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")
if os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings, configure_logging

configure_logging()

# Import AI providers AFTER environment variables are set
from ai.providers.factory import get_vlm, get_embedder


def benchmark_ai_providers():
    """Benchmark AI provider performance."""
    print("=== AI Provider Benchmarks ===")

    # Benchmark VLM
    print("\nVLM Provider:")
    vlm = get_vlm()
    print(f"  Provider: {type(vlm).__name__}")
    print(f"  Model: {os.getenv('LLM_MODEL')}")

    # Benchmark Embedding
    print("\nEmbedding Provider:")
    embedder = get_embedder()
    print(f"  Provider: {type(embedder).__name__}")
    print(f"  Model: {os.getenv('EMBEDDING_MODEL')}")
    print(f"  Dimension: {embedder.dimension}")

    # Benchmark embedding generation
    test_text = "A navy blue backpack with worn front zipper"
    start = time.time()
    for _ in range(5):
        vec = embedder.embed(test_text)
    elapsed = time.time() - start
    print(f"  Avg embedding time: {elapsed/5:.3f}s")


async def benchmark_database():
    """Benchmark database operations."""
    print("\n=== Database Benchmarks ===")
    print(f"  Database URL: {settings.DATABASE_URL}")

    try:
        from src.storage.database import check_database_connection

        connected = await check_database_connection()
        print(f"  Connection status: {'Connected' if connected else 'Failed'}")
    except Exception as e:
        print(f"  Connection error: {e}")


async def benchmark_concurrency():
    """Benchmark concurrency pipeline."""
    print("\n=== Concurrency Pipeline Benchmarks ===")

    # Simulate concurrent processing
    async def mock_process(item_id: int) -> float:
        await asyncio.sleep(0.05)  # Simulate work
        return item_id

    # Sequential processing
    start = time.time()
    for i in range(10):
        await mock_process(i)
    sequential_time = time.time() - start

    # Concurrent processing
    start = time.time()
    tasks = [mock_process(i) for i in range(10)]
    await asyncio.gather(*tasks)
    concurrent_time = time.time() - start

    speedup = sequential_time / concurrent_time
    print(f"  Sequential time: {sequential_time:.3f}s")
    print(f"  Concurrent time: {concurrent_time:.3f}s")
    print(f"  Speedup: {speedup:.2f}x")


def main():
    """Run all benchmarks."""
    print(f"Benchmarking Lost & Found Application")
    print(
        f"Environment: {os.getenv('LLM_PROVIDER')} LLM, {os.getenv('EMBEDDING_PROVIDER')} embeddings"
    )
    print(f"Database: {settings.DATABASE_URL}")

    # AI Provider benchmarks
    try:
        benchmark_ai_providers()
    except Exception as e:
        print(f"AI benchmark failed: {e}")

    # Database benchmarks
    try:
        asyncio.run(benchmark_database())
    except Exception as e:
        print(f"Database benchmark failed: {e}")

    # Concurrency benchmarks
    try:
        asyncio.run(benchmark_concurrency())
    except Exception as e:
        print(f"Concurrency benchmark failed: {e}")

    print("\n=== Benchmarks Complete ===")


if __name__ == "__main__":
    main()
