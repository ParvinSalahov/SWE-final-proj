"""Tests for the Typer CLI (src/cli.py).

All tests run offline: the `requests` library is patched so no live HTTP
server is needed.  The Typer CliRunner invokes commands in-process.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Shared helpers / factories
# ---------------------------------------------------------------------------

_CREATED = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()


def _item_payload(
    item_id: str = "id-001",
    status: str = "lost",
    user_text: str = "red wallet",
) -> dict:
    return {
        "id": item_id,
        "status": status,
        "user_text": user_text,
        "image_path": "/tmp/img.jpg",
        "description": {
            "object_class": "wallet",
            "colors": ["red"],
            "brand": None,
            "distinguishing_marks": [],
            "location_hints": [],
            "confidence": 0.9,
        },
        "created_at": _CREATED,
    }


def _match_payload(
    query_id: str = "id-001",
    query_status: str = "lost",
    match_id: str = "id-002",
    score: float = 0.92,
) -> dict:
    return {
        "query_item": _item_payload(item_id=query_id, status=query_status),
        "matches": [
            {
                "item": _item_payload(item_id=match_id, status="found"),
                "score": score,
                "reason": "same color",
            }
        ],
        "total_candidates_evaluated": 5,
    }


def _mock_response(status_code: int, payload: dict | list) -> MagicMock:
    """Build a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.text = json.dumps(payload)
    return resp


def _dummy_image(tmp_path) -> str:
    """Create a minimal file that exists on disk (content doesn't matter here)."""
    p = tmp_path / "test.jpg"
    p.write_bytes(b"\xff\xd8\xff" + b"\x00" * 10 + b"\xff\xd9")
    return str(p)


# ---------------------------------------------------------------------------
# format_* helper unit tests (pure functions, no mocking needed)
# ---------------------------------------------------------------------------

def test_format_item_response_contains_id():
    from src.cli import format_item_response
    out = format_item_response(_item_payload())
    assert "id-001" in out
    assert "lost" in out


def test_format_match_response_contains_score():
    from src.cli import format_match_response
    payload = _match_payload()
    out = format_match_response(
        payload["query_item"]["id"],
        payload["query_item"]["status"],
        payload["matches"],
        payload["total_candidates_evaluated"],
    )
    assert "0.920" in out
    assert "id-002" in out


def test_format_match_response_no_matches():
    from src.cli import format_match_response
    out = format_match_response("id-001", "lost", [], 3)
    assert "No matches found" in out


def test_format_list_response_with_items():
    from src.cli import format_list_response
    items = [_item_payload("a"), _item_payload("b")]
    out = format_list_response(items)
    assert "Total: 2" in out
    assert "#1" in out
    assert "#2" in out


def test_format_list_response_empty():
    from src.cli import format_list_response
    out = format_list_response([])
    assert "No items found" in out


def test_format_list_response_status_filter():
    from src.cli import format_list_response
    out = format_list_response([], status_filter="lost")
    assert "lost" in out


# ---------------------------------------------------------------------------
# register-lost command
# ---------------------------------------------------------------------------

class TestRegisterLostCommand:
    def test_happy_path(self, tmp_path):
        img = _dummy_image(tmp_path)
        with patch("src.cli.requests.post") as mock_post:
            mock_post.return_value = _mock_response(201, _item_payload())
            result = runner.invoke(app, ["register-lost", "--image", img, "--text", "red wallet"])
        assert result.exit_code == 0
        assert "id-001" in result.output

    def test_error_response(self, tmp_path):
        img = _dummy_image(tmp_path)
        with patch("src.cli.requests.post") as mock_post:
            mock_post.return_value = _mock_response(400, {"detail": "bad image"})
            result = runner.invoke(app, ["register-lost", "--image", img])
        assert result.exit_code == 1

    def test_connection_error(self, tmp_path):
        import requests as req_lib
        img = _dummy_image(tmp_path)
        with patch("src.cli.requests.post", side_effect=req_lib.exceptions.ConnectionError("refused")):
            result = runner.invoke(app, ["register-lost", "--image", img])
        assert result.exit_code == 1
        assert "Could not connect" in result.output

    def test_missing_image_file(self):
        result = runner.invoke(app, ["register-lost", "--image", "/nonexistent/path.jpg"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# register-found command
# ---------------------------------------------------------------------------

class TestRegisterFoundCommand:
    def test_happy_path(self, tmp_path):
        img = _dummy_image(tmp_path)
        with patch("src.cli.requests.post") as mock_post:
            mock_post.return_value = _mock_response(201, _item_payload(status="found"))
            result = runner.invoke(app, ["register-found", "--image", img, "--text", "blue bag"])
        assert result.exit_code == 0
        assert "found" in result.output

    def test_error_response(self, tmp_path):
        img = _dummy_image(tmp_path)
        with patch("src.cli.requests.post") as mock_post:
            mock_post.return_value = _mock_response(413, {"detail": "too large"})
            result = runner.invoke(app, ["register-found", "--image", img])
        assert result.exit_code == 1

    def test_connection_error(self, tmp_path):
        import requests as req_lib
        img = _dummy_image(tmp_path)
        with patch("src.cli.requests.post", side_effect=req_lib.exceptions.ConnectionError("refused")):
            result = runner.invoke(app, ["register-found", "--image", img])
        assert result.exit_code == 1
        assert "Could not connect" in result.output


# ---------------------------------------------------------------------------
# search-matches command
# ---------------------------------------------------------------------------

class TestSearchMatchesCommand:
    def test_happy_path(self):
        with patch("src.cli.requests.get") as mock_get:
            mock_get.return_value = _mock_response(200, _match_payload())
            result = runner.invoke(app, ["search-matches", "--id", "id-001"])
        assert result.exit_code == 0
        assert "id-001" in result.output
        assert "0.920" in result.output

    def test_not_found(self):
        with patch("src.cli.requests.get") as mock_get:
            mock_get.return_value = _mock_response(404, {"detail": "not found"})
            result = runner.invoke(app, ["search-matches", "--id", "ghost"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_generic_error_response(self):
        with patch("src.cli.requests.get") as mock_get:
            mock_get.return_value = _mock_response(500, {"detail": "server error"})
            result = runner.invoke(app, ["search-matches", "--id", "id-001"])
        assert result.exit_code == 1

    def test_connection_error(self):
        import requests as req_lib
        with patch("src.cli.requests.get", side_effect=req_lib.exceptions.ConnectionError("refused")):
            result = runner.invoke(app, ["search-matches", "--id", "id-001"])
        assert result.exit_code == 1
        assert "Could not connect" in result.output

    def test_custom_k_value(self):
        with patch("src.cli.requests.get") as mock_get:
            mock_get.return_value = _mock_response(200, _match_payload())
            result = runner.invoke(app, ["search-matches", "--id", "id-001", "-k", "5"])
        assert result.exit_code == 0
        _, call_kwargs = mock_get.call_args
        assert call_kwargs.get("params", {}).get("k") == 5


# ---------------------------------------------------------------------------
# list command
# ---------------------------------------------------------------------------

class TestListItemsCommand:
    def test_list_all(self):
        items = [_item_payload("a", "lost"), _item_payload("b", "found")]
        with patch("src.cli.requests.get") as mock_get:
            mock_get.return_value = _mock_response(200, items)
            result = runner.invoke(app, ["list-items"])
        assert result.exit_code == 0
        assert "Total: 2" in result.output

    def test_list_filtered(self):
        with patch("src.cli.requests.get") as mock_get:
            mock_get.return_value = _mock_response(200, [_item_payload("a", "lost")])
            result = runner.invoke(app, ["list-items", "--status", "lost"])
        assert result.exit_code == 0
        _, call_kwargs = mock_get.call_args
        assert call_kwargs.get("params", {}).get("status") == "lost"

    def test_empty_list(self):
        with patch("src.cli.requests.get") as mock_get:
            mock_get.return_value = _mock_response(200, [])
            result = runner.invoke(app, ["list-items"])
        assert result.exit_code == 0
        assert "No items found" in result.output

    def test_error_response(self):
        with patch("src.cli.requests.get") as mock_get:
            mock_get.return_value = _mock_response(500, {"detail": "error"})
            result = runner.invoke(app, ["list-items"])
        assert result.exit_code == 1

    def test_connection_error(self):
        import requests as req_lib
        with patch("src.cli.requests.get", side_effect=req_lib.exceptions.ConnectionError("refused")):
            result = runner.invoke(app, ["list-items"])
        assert result.exit_code == 1
        assert "Could not connect" in result.output
