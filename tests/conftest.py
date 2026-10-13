import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FONT_PATH = os.path.expanduser("~/.local/share/fonts/ipag.ttf")


@pytest.fixture
def font_path():
    if not os.path.isfile(FONT_PATH):
        pytest.skip("IPA Gothic is not installed at {}".format(FONT_PATH))
    return FONT_PATH


@pytest.fixture
def converter_factory(font_path):
    from converter import TextToPdfConverter

    def make(**kwargs):
        kwargs.setdefault("font_path", font_path)
        kwargs.setdefault("timestamp", datetime(2026, 10, 13, 12, 0, 0))
        kwargs.setdefault("user", "tester")
        return TextToPdfConverter(**kwargs)

    return make
