"""Input encodings and decode errors."""

import subprocess
import sys
from pathlib import Path

import pytest

from converter import ConversionError, normalize_encoding, read_text_file

ROOT = Path(__file__).resolve().parents[1]


def _run(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "text2pdf"), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    "name,codec",
    [
        ("euc_jis_2004", "euc_jis_2004"),
        ("euc-jis-2004", "euc_jis_2004"),
        ("EUC_JIS_2004", "euc_jis_2004"),
        ("euc_jp", "euc_jp"),
        ("euc-jp", "euc_jp"),
        ("utf-8", "utf-8"),
        ("utf8", "utf-8"),
        ("UTF-8", "utf-8"),
    ],
)
def test_encoding_aliases(name, codec):
    assert normalize_encoding(name) == codec


@pytest.mark.parametrize("name", ["latin-1", "shift_jis", "ascii", "", "euc"])
def test_unknown_encoding_name(name):
    with pytest.raises(ConversionError) as caught:
        normalize_encoding(name)
    assert caught.value.exit_code == 2
    message = str(caught.value)
    assert "Unsupported encoding" in message
    assert "euc_jis_2004" in message


def test_ascii_japanese_fullwidth_and_circled_numbers(tmp_path):
    text = "ABC\nあいう\nＡＢＣ\n①②③\nあA１\n"
    path = tmp_path / "mixed.txt"
    path.write_bytes(text.encode("euc_jis_2004"))
    lines = read_text_file(str(path), "euc_jis_2004")
    assert lines == ["ABC", "あいう", "ＡＢＣ", "①②③", "あA１"]


@pytest.mark.parametrize(
    "codec,alias",
    [
        ("euc_jp", "euc-jp"),
        ("euc_jis_2004", "euc_jis_2004"),
        ("utf-8", "utf-8"),
    ],
)
def test_each_supported_codec_round_trips(tmp_path, codec, alias):
    # ① is in JIS X 0213 and is not representable in Python's euc_jp codec.
    text = "ABCあいう" if codec == "euc_jp" else "ABCあいう①②③"
    path = tmp_path / "sample.txt"
    path.write_bytes(text.encode(codec))
    assert read_text_file(str(path), alias) == [text]


def test_decode_error_reports_location_and_writes_nothing(tmp_path, converter_factory):
    path = tmp_path / "broken.txt"
    payload = "ok\n".encode("ascii") + b"\xff\xfe"
    path.write_bytes(payload)
    output = tmp_path / "broken.pdf"
    converter = converter_factory()
    with pytest.raises(ConversionError) as caught:
        converter.convert(str(path), str(output), encoding="euc_jis_2004")
    message = str(caught.value)
    assert caught.value.exit_code == 1
    assert str(path) in message
    assert "byte 3" in message
    assert "line 2" in message
    assert "illegal multibyte sequence" in message
    assert not output.exists()
    assert list(tmp_path.glob(".text2pdf-*")) == []


def test_cli_decode_error_is_nonzero_and_leaves_no_pdf(tmp_path):
    path = tmp_path / "broken.txt"
    path.write_bytes(b"\xff")
    output = tmp_path / "out.pdf"
    result = _run(str(path), str(output), "--encoding", "utf-8")
    assert result.returncode != 0
    assert str(path) in result.stderr
    assert "byte 0" in result.stderr
    assert "line 1" in result.stderr
    assert not output.exists()


def test_cli_unknown_encoding(tmp_path):
    path = tmp_path / "plain.txt"
    path.write_bytes(b"abc\n")
    output = tmp_path / "out.pdf"
    result = _run(str(path), str(output), "--encoding", "latin-1")
    assert result.returncode == 2
    assert "Unsupported encoding" in result.stderr
    assert not output.exists()


def test_cli_missing_input():
    result = _run("no-such-input.txt", "out.pdf")
    assert result.returncode == 1
    assert "File not found" in result.stderr
    assert not (ROOT / "out.pdf").exists()


def test_cli_missing_font(tmp_path):
    path = tmp_path / "plain.txt"
    path.write_bytes(b"abc\n")
    output = tmp_path / "out.pdf"
    missing = tmp_path / "missing.ttf"
    result = _run(str(path), str(output), "--font-path", str(missing))
    assert result.returncode == 1
    assert "Font file not found" in result.stderr
    assert str(missing) in result.stderr
    assert not output.exists()


def test_cli_bad_option():
    result = _run("--not-a-real-option")
    assert result.returncode == 2


def test_cli_bad_tab_size(tmp_path):
    path = tmp_path / "plain.txt"
    path.write_bytes(b"abc\n")
    result = _run(str(path), "--tab-size", "0")
    assert result.returncode == 2
    assert "tab-size" in result.stderr


def test_cli_help_lists_new_options():
    result = _run("--help")
    assert result.returncode == 0
    for option in ("--encoding", "--font-path", "--tab-size", "--layout", "--font-size"):
        assert option in result.stdout


def test_unwritable_output_directory(tmp_path):
    path = tmp_path / "plain.txt"
    path.write_bytes("あ".encode("euc_jis_2004"))
    locked = tmp_path / "locked"
    locked.mkdir()
    output = locked / "out.pdf"
    locked.chmod(0o555)
    try:
        result = _run(str(path), str(output))
        assert result.returncode != 0
        assert "Cannot write output file" in result.stderr
        assert not output.exists()
    finally:
        locked.chmod(0o755)
