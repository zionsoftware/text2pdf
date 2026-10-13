import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# text2pdf has no .py suffix, so register it before test modules import it.
_loader = SourceFileLoader("text2pdf", str(ROOT / "text2pdf"))
_spec = importlib.util.spec_from_loader("text2pdf", _loader)
_module = importlib.util.module_from_spec(_spec)
sys.modules["text2pdf"] = _module
_loader.exec_module(_module)

@pytest.fixture
def font_path():
    from text2pdf import ConversionError, find_ipa_gothic

    try:
        path = find_ipa_gothic()
    except ConversionError as exc:
        pytest.skip(str(exc))
    return path


@pytest.fixture
def converter_factory(font_path):
    from text2pdf import TextToPdfConverter

    def make(**kwargs):
        kwargs.setdefault("font_path", font_path)
        kwargs.setdefault("user", "tester")
        return TextToPdfConverter(**kwargs)

    return make
