"""Wrapper script for demo_ai.py that properly loads environment variables.

This script ensures that the .env file is loaded and environment variables
are set before running the demo_ai.py script, which uses os.getenv() directly.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Ensure environment variables are set for AI providers
# These are read by os.getenv() in the ai/providers/ modules
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

# Import and run the demo_ai module
demo_ai_path = Path(__file__).parent.parent / "demo_ai.py"
sys.path.insert(0, str(demo_ai_path.parent))

# Execute demo_ai.py with the same arguments
if __name__ == "__main__":
    import subprocess

    # Pass the current environment to the subprocess
    result = subprocess.run(
        [sys.executable, str(demo_ai_path)] + sys.argv[1:], env=os.environ.copy()
    )
    sys.exit(result.returncode)
