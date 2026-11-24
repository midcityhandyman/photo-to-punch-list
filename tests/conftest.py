from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def sample_dir() -> Path:
    return ROOT / "samples" / "images"


class FakeClient:
    """Vision client driven by a dict of file name to findings or exception."""

    name = "fake"

    def __init__(self, responses):
        self.responses = responses

    def analyze(self, image_path):
        result = self.responses[image_path.name]
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def fake_client():
    return FakeClient
