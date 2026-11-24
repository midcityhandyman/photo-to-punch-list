"""The Claude client is tested against a fake SDK object. No network, no key."""

import base64
import json
from types import SimpleNamespace

import pytest

from punchlist.claude_client import DEFAULT_MODEL, ClaudeVisionClient, parse_response
from punchlist.vision import VisionError


class FakeSDK:
    def __init__(self, response=None, error=None):
        self.calls = []
        self._response, self._error = response, error
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._response


def reply(payload, stop_reason="end_turn"):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])


FINDING = {"room": "Kitchen", "trade": "Paint", "description": "Drip.", "severity": "low", "confidence": 0.8}


def test_default_model_and_env_override(monkeypatch):
    monkeypatch.delenv("PUNCHLIST_MODEL", raising=False)
    assert DEFAULT_MODEL == "claude-sonnet-5-5"
    assert ClaudeVisionClient(client=object()).model == "claude-sonnet-5-5"
    monkeypatch.setenv("PUNCHLIST_MODEL", "some-other-model")
    assert ClaudeVisionClient(client=object()).model == "some-other-model"
    assert ClaudeVisionClient(model="explicit", client=object()).model == "explicit"


def test_request_carries_base64_image_and_json_schema(sample_dir):
    sdk = FakeSDK(reply({"findings": [FINDING]}))
    image = sample_dir / "kitchen_01.png"
    findings = ClaudeVisionClient(client=sdk).analyze(image)

    assert [f.description for f in findings] == ["Drip."]
    (call,) = sdk.calls
    assert call["model"] == "claude-sonnet-5-5"
    image_block, text_block = call["messages"][0]["content"]
    assert image_block["type"] == "image"
    assert image_block["source"]["type"] == "base64"
    assert image_block["source"]["media_type"] == "image/png"
    assert base64.standard_b64decode(image_block["source"]["data"]) == image.read_bytes()
    assert "kitchen_01.png" in text_block["text"]
    fmt = call["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["schema"]["additionalProperties"] is False
    assert "thinking" not in call and "temperature" not in call


def test_empty_findings_is_valid():
    assert parse_response(reply({"findings": []})) == []


@pytest.mark.parametrize(
    "response, message",
    [
        (reply({"findings": []}, stop_reason="refusal"), "declined"),
        (reply('{"findings": [', stop_reason="max_tokens"), "cut off"),
        (reply("not json"), "did not match"),
        (reply({"findings": [{"room": "Kitchen"}]}), "did not match"),
        (SimpleNamespace(stop_reason="end_turn", content=[]), "no text block"),
    ],
)
def test_bad_replies_raise_vision_error(response, message):
    with pytest.raises(VisionError, match=message):
        parse_response(response)


def test_sdk_exception_becomes_vision_error(sample_dir):
    sdk = FakeSDK(error=RuntimeError("rate limited"))
    with pytest.raises(VisionError, match="RuntimeError: rate limited"):
        ClaudeVisionClient(client=sdk).analyze(sample_dir / "kitchen_01.png")


def test_unsupported_extension_rejected_before_any_call(tmp_path):
    sdk = FakeSDK(reply({"findings": []}))
    odd = tmp_path / "photo.bmp"
    odd.write_bytes(b"x")
    with pytest.raises(VisionError, match="unsupported image type"):
        ClaudeVisionClient(client=sdk).analyze(odd)
    assert sdk.calls == []
