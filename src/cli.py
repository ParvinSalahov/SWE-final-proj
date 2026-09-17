"""Command Line Interface (CLI) for Lost & Found Service.

CLI Commands:
1. register-lost --image <path> --text <description>
2. register-found --image <path> --text <description>
3. search-matches --id <item_id> -k <n>
4. list --status <lost|found>
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Annotated

import requests
import typer

from src.config import configure_logging, ensure_ai_provider_env, settings

# Initialize logging
configure_logging()
ensure_ai_provider_env()
logger = logging.getLogger(__name__)

# Create CLI app
app = typer.Typer(
    name="lost-found",
    help="Smart Lost & Found CLI - Register and match lost and found items using AI",
)

# API base URL (use localhost for local connections)
API_BASE_URL = f"http://localhost:{settings.HTTP_PORT}"


def format_item_response(item: dict) -> str:
    """Format item registration response for CLI output."""
    return f"""
Item registered successfully!
   ID: {item["id"]}
   Status: {item["status"]}
   Description: {item["user_text"]}
   Created: {item["created_at"]}
"""


def format_match_response(
    query_id: str,
    query_status: str,
    matches: list[dict],
    total_candidates: int,
) -> str:
    """Format match search response for CLI output."""
    output = f"""
Match Results for {query_status.upper()} Item: {query_id}
   Total candidates evaluated: {total_candidates}
   Found {len(matches)} match(es)
"""
    if matches:
        for i, match in enumerate(matches, 1):
            item = match["item"]
            output += f"""
   Match #{i}:
     ID: {item["id"]}
     Status: {item["status"]}
     Description: {item["user_text"]}
     Similarity Score: {match["score"]:.3f}
     Reason: {match["reason"]}
     Created: {item["created_at"]}
"""
    else:
        output += "\n   No matches found.\n"
    return output


def format_list_response(items: list[dict], status_filter: str | None = None) -> str:
    """Format list response for CLI output."""
    filter_text = f" (filtered by status: {status_filter})" if status_filter else ""
    output = f"""
List of Items{filter_text}
   Total: {len(items)}
"""
    if items:
        for i, item in enumerate(items, 1):
            output += f"""
   #{i}:
     ID: {item["id"]}
     Status: {item["status"]}
     Description: {item["user_text"]}
     Created: {item["created_at"]}
"""
    else:
        output += "\n   No items found.\n"
    return output


@app.command()
def register_lost(
    image: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=True,
            dir_okay=False,
            help="Path to the image file (JPEG or PNG, <= 5MB)",
        ),
    ],
    text: Annotated[
        str,
        typer.Option(
            "--text", "-t", help="User description and context of the lost item"
        ),
    ] = "",
) -> None:
    """Register a lost item with an image and optional description."""
    try:
        url = f"{API_BASE_URL}/items/lost"
        with open(image, "rb") as f:
            content_type = (
                mimetypes.guess_type(image.name)[0] or "application/octet-stream"
            )
            files = {"image": (image.name, f, content_type)}
            data = {"user_text": text}
            response = requests.post(url, files=files, data=data, timeout=30)

        if response.status_code == 201:
            item = response.json()
            typer.echo(format_item_response(item))
        else:
            typer.echo(f"Error: {response.status_code} - {response.text}", err=True)
            raise typer.Exit(code=1)
    except requests.exceptions.RequestException:
        logger.exception("Failed to connect to API server")
        typer.echo(
            f"Error: Could not connect to API server at {API_BASE_URL}", err=True
        )
        typer.echo("Make sure the API server is running: uvicorn src.api:app", err=True)
        raise typer.Exit(code=1)


@app.command()
def register_found(
    image: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=True,
            dir_okay=False,
            help="Path to the image file (JPEG or PNG, <= 5MB)",
        ),
    ],
    text: Annotated[
        str,
        typer.Option(
            "--text", "-t", help="User description and context of the found item"
        ),
    ] = "",
) -> None:
    """Register a found item with an image and optional description."""
    try:
        url = f"{API_BASE_URL}/items/found"
        with open(image, "rb") as f:
            files = {"image": (image.name, f, "image/jpeg")}
            data = {"user_text": text}
            response = requests.post(url, files=files, data=data, timeout=30)

        if response.status_code == 201:
            item = response.json()
            typer.echo(format_item_response(item))
        else:
            typer.echo(f"Error: {response.status_code} - {response.text}", err=True)
            raise typer.Exit(code=1)
    except requests.exceptions.RequestException:
        logger.exception("Failed to connect to API server")
        typer.echo(
            f"Error: Could not connect to API server at {API_BASE_URL}", err=True
        )
        typer.echo("Make sure the API server is running: uvicorn src.api:app", err=True)
        raise typer.Exit(code=1)


@app.command()
def search_matches(
    id: Annotated[
        str,
        typer.Option("--id", help="The ID of the item to match against"),
    ],
    k: Annotated[
        int,
        typer.Option(
            "-k",
            min=1,
            max=50,
            help="Maximum number of top matches to return (default: 3)",
        ),
    ] = 3,
) -> None:
    """Find top-k matches for an item from the opposite pool."""
    try:
        url = f"{API_BASE_URL}/items/{id}/matches"
        params = {"k": k}
        response = requests.get(url, params=params, timeout=30)

        if response.status_code == 200:
            result = response.json()
            typer.echo(
                format_match_response(
                    result["query_item"]["id"],
                    result["query_item"]["status"],
                    result["matches"],
                    result["total_candidates_evaluated"],
                )
            )
        elif response.status_code == 404:
            typer.echo(f"Error: Item with ID '{id}' not found", err=True)
            raise typer.Exit(code=1)
        else:
            typer.echo(f"Error: {response.status_code} - {response.text}", err=True)
            raise typer.Exit(code=1)
    except requests.exceptions.RequestException:
        logger.exception("Failed to connect to API server")
        typer.echo(
            f"Error: Could not connect to API server at {API_BASE_URL}", err=True
        )
        typer.echo("Make sure the API server is running: uvicorn src.api:app", err=True)
        raise typer.Exit(code=1)


@app.command()
def list_items(
    status: Annotated[
        str | None,
        typer.Option("--status", "-s", help="Filter by item status (lost or found)"),
    ] = None,
) -> None:
    """List all registered items, optionally filtered by status."""
    try:
        url = f"{API_BASE_URL}/items"
        params = {}
        if status:
            params["status"] = status

        response = requests.get(url, params=params, timeout=30)

        if response.status_code == 200:
            items = response.json()
            typer.echo(format_list_response(items, status))
        else:
            typer.echo(f"Error: {response.status_code} - {response.text}", err=True)
            raise typer.Exit(code=1)
    except requests.exceptions.RequestException:
        logger.exception("Failed to connect to API server")
        typer.echo(
            f"Error: Could not connect to API server at {API_BASE_URL}", err=True
        )
        typer.echo("Make sure the API server is running: uvicorn src.api:app", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
