"""Vision client backed by the Claude Messages API.

One request per photo: the image goes in as a base64 image block and the reply
is constrained to a JSON schema with structured outputs, so there is no free
text to parse. The anthropic package is imported lazily so the rest of the
project runs without it.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from .models import SEVERITIES, TRADES, Finding
from .vision import VisionError, media_type_for

DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_EFFORT = "medium"
MAX_TOKENS = 16000

SYSTEM_PROMPT = (
    "You review job site photos for a small renovation contractor and list the "
    "punch items: unfinished, damaged or defective work that a tradesperson must "
    "fix before the job can be closed out. Report only what is visible in the "
    "photo. One finding per distinct defect. Describe each so a tradesperson can "
    "act on it without seeing the photo, in one sentence. Name the room as it "
    "would appear on a floor plan. If the photo does not show which room it is, "
    "use 'Unknown'. If the photo shows no defects, return an empty list. "
    "Confidence is your certainty from 0 to 1 that the defect is real."
)

FINDINGS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "room": {"type": "string"},
                    "trade": {"type": "string", "enum": list(TRADES)},
                    "description": {"type": "string"},
                    "severity": {"type": "string", "enum": list(SEVERITIES)},
                    "confidence": {"type": "number"},
                },
                "required": ["room", "trade", "description", "severity", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}


class ClaudeVisionClient:
    name = "claude"

    def __init__(self, model: str | None = None, effort: str | None = None, client: Any = None):
        self.model = model or os.environ.get("PUNCHLIST_MODEL") or DEFAULT_MODEL
        self.effort = effort or os.environ.get("PUNCHLIST_EFFORT") or DEFAULT_EFFORT
        self._client = client  # injectable so tests never touch the network

    def _sdk_client(self) -> Any:
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise VisionError(
                    "the Claude client needs the anthropic package: pip install -e '.[claude]'"
                ) from exc
            self._client = anthropic.Anthropic()
        return self._client

    def build_request(self, image_path: Path) -> dict[str, Any]:
        """The exact keyword arguments sent to messages.create for one photo."""
        data = base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")
        return {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "system": SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type_for(image_path),
                                "data": data,
                            },
                        },
                        {
                            "type": "text",
                            "text": f"Photo file name: {image_path.name}. List the punch items.",
                        },
                    ],
                }
            ],
            "output_config": {
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": FINDINGS_SCHEMA},
            },
        }

    def analyze(self, image_path: Path) -> list[Finding]:
        request = self.build_request(image_path)
        client = self._sdk_client()
        try:
            response = client.messages.create(**request)
        except Exception as exc:  # SDK errors are typed; all of them mean "this photo failed"
            raise VisionError(f"{type(exc).__name__}: {exc}") from exc
        return parse_response(response)


def parse_response(response: Any) -> list[Finding]:
    """Turn a Messages API response into findings, checking stop_reason first."""
    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason == "refusal":
        raise VisionError("the model declined to analyze this photo")
    if stop_reason == "max_tokens":
        raise VisionError("the reply was cut off at max_tokens")
    text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), None)
    if text is None:
        raise VisionError("the reply contained no text block")
    try:
        payload = json.loads(text)
        return [Finding.from_dict(f) for f in payload["findings"]]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise VisionError(f"the reply did not match the findings schema: {exc}") from exc
