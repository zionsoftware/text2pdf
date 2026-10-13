"""Input encodings and decode errors."""

import subprocess
import sys
from pathlib import Path

import pytest

from converter import (
    ConversionError,
    detect_encoding,
    format_ambiguous_warning,
    load_text,
    normalize_encoding,
    read_text_file,
    select_decoded,
)

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
        ("auto", "auto"),
        ("AUTO", "auto"),
        ("cp932", "cp932"),
        ("cp_932", "cp932"),
        ("cp-932", "cp932"),
        ("CP932", "cp932"),
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
    assert "cp932" in message
    assert "auto" in message


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
        ("cp932", "cp_932"),
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
    assert "auto" in result.stdout
    assert "cp932" in result.stdout
    assert "6 to 16" in result.stdout


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


def test_select_decoded_keeps_priority_when_text_matches():
    codec, text, ambiguous = select_decoded(
        [
            ("euc_jis_2004", "same"),
            ("utf-8", "same"),
            ("cp932", "same"),
        ]
    )
    assert codec == "euc_jis_2004"
    assert text == "same"
    assert ambiguous == []


def test_select_decoded_warns_only_for_different_text():
    codec, text, ambiguous = select_decoded(
        [
            ("euc_jis_2004", "euc"),
            ("utf-8", "euc"),
            ("cp932", "cp"),
        ]
    )
    assert codec == "euc_jis_2004"
    assert text == "euc"
    assert ambiguous == ["cp932"]


def test_ascii_and_empty_are_utf8_without_warning():
    text, codec, ambiguous = detect_encoding(b"ABC\n", "plain.txt")
    assert (text, codec, ambiguous) == ("ABC\n", "utf-8", [])
    text, codec, ambiguous = detect_encoding(b"", "empty.txt")
    assert (text, codec, ambiguous) == ("", "utf-8", [])


def test_utf8_bom_is_stripped_and_not_reread_as_another_encoding():
    payload = "日本語\n二つ目".encode("utf-8")
    text, codec, ambiguous = detect_encoding(b"\xef\xbb\xbf" + payload, "bom.txt")
    assert codec == "utf-8"
    assert ambiguous == []
    assert text == "日本語\n二つ目"
    assert not text.startswith("\ufeff")


def test_invalid_utf8_after_bom_does_not_fall_back(tmp_path):
    path = tmp_path / "bom-bad.txt"
    path.write_bytes(b"\xef\xbb\xbfok\n\xff")
    with pytest.raises(ConversionError) as caught:
        load_text(str(path), "auto")
    message = str(caught.value)
    assert caught.value.exit_code == 1
    assert "utf-8" in message
    assert "byte 6" in message
    assert "line 2" in message
    assert "euc_jis_2004, utf-8, or cp932" not in message


def test_auto_detects_euc_jp_japanese_and_explicit_euc_jp_still_works(tmp_path):
    text = "日本語"
    path = tmp_path / "euc.txt"
    path.write_bytes(text.encode("euc_jp"))
    lines, codec, ambiguous = load_text(str(path), "auto")
    assert lines == [text]
    assert codec == "euc_jis_2004"
    assert ambiguous == []
    assert read_text_file(str(path), "euc_jp") == [text]
    assert read_text_file(str(path), "euc-jp") == [text]


def test_auto_detects_euc_jis_2004_circled_numbers(tmp_path):
    text = "①②③"
    path = tmp_path / "circled.txt"
    path.write_bytes(text.encode("euc_jis_2004"))
    lines, codec, ambiguous = load_text(str(path), "auto")
    assert lines == [text]
    assert codec == "euc_jis_2004"
    assert ambiguous == ["cp932"]


def test_auto_detects_utf8_japanese(tmp_path):
    text = "日本語"
    path = tmp_path / "utf.txt"
    path.write_bytes(text.encode("utf-8"))
    lines, codec, ambiguous = load_text(str(path), "auto")
    assert lines == [text]
    assert codec == "utf-8"
    assert ambiguous == []


def test_auto_detects_cp932_japanese_and_extended_character(tmp_path):
    path = tmp_path / "cp932.txt"
    path.write_bytes("日本語".encode("cp932"))
    lines, codec, ambiguous = load_text(str(path), "auto")
    assert lines == ["日本語"]
    assert codec == "cp932"
    assert ambiguous == []

    extended = tmp_path / "saki.txt"
    extended.write_bytes("﨑".encode("cp932"))
    lines, codec, ambiguous = load_text(str(extended), "auto")
    assert lines == ["﨑"]
    assert codec == "cp932"
    assert ambiguous == []


def test_cp932_takai_is_misread_as_euc_jis_2004(tmp_path):
    """EE E0 is CP932 髙 and also a different EUC-JIS-2004 character."""
    path = tmp_path / "takai.txt"
    path.write_bytes("髙".encode("cp932"))
    lines, codec, ambiguous = load_text(str(path), "auto")
    assert codec == "euc_jis_2004"
    assert lines == ["釵"]
    assert lines != ["髙"]
    assert ambiguous == ["cp932"]
    assert read_text_file(str(path), "cp932") == ["髙"]


def test_ambiguous_bytes_keep_priority_and_list_the_others():
    data = bytes.fromhex("c2a140")
    text, codec, ambiguous = detect_encoding(data, "ambiguous.txt")
    assert codec == "euc_jis_2004"
    assert text == data.decode("euc_jis_2004")
    assert text != data.decode("utf-8")
    assert text != data.decode("cp932")
    assert ambiguous == ["utf-8", "cp932"]
    warning = format_ambiguous_warning(codec, ambiguous)
    assert warning == (
        "Warning: Ambiguous encoding detected.\n"
        "Selected: euc_jis_2004\n"
        "Other possible encodings: utf-8, cp932\n"
        "Use --encoding to specify the correct encoding."
    )


def test_auto_fails_when_no_candidate_decodes(tmp_path):
    path = tmp_path / "bad.txt"
    path.write_bytes(b"\x81")
    output = tmp_path / "bad.pdf"
    with pytest.raises(ConversionError) as caught:
        load_text(str(path), "auto")
    assert caught.value.exit_code == 1
    message = str(caught.value)
    assert str(path) in message
    assert "euc_jis_2004" in message
    assert "utf-8" in message
    assert "cp932" in message
    assert not output.exists()


def test_explicit_encoding_skips_detection(tmp_path):
    path = tmp_path / "forced.txt"
    data = bytes.fromhex("c2a140")
    path.write_bytes(data)
    lines, codec, ambiguous = load_text(str(path), "utf-8")
    assert lines == [data.decode("utf-8")]
    assert codec == "utf-8"
    assert ambiguous == []


def test_cli_auto_reports_encoding_and_ambiguous_warning(tmp_path, font_path):
    path = tmp_path / "ambiguous.txt"
    path.write_bytes("あいう\n".encode("euc_jis_2004"))
    output = tmp_path / "ambiguous.pdf"
    result = _run(str(path), str(output))
    assert result.returncode == 0
    assert "Detected encoding: euc_jis_2004" in result.stdout
    assert "Successfully created {}".format(output) in result.stdout
    assert result.stderr == (
        "Warning: Ambiguous encoding detected.\n"
        "Selected: euc_jis_2004\n"
        "Other possible encodings: cp932\n"
        "Use --encoding to specify the correct encoding.\n"
    )
    assert output.is_file()


def test_cli_explicit_encoding_is_quiet(tmp_path, font_path):
    path = tmp_path / "forced.txt"
    path.write_bytes(bytes.fromhex("c2a140"))
    output = tmp_path / "forced.pdf"
    result = _run(str(path), str(output), "--encoding", "utf-8")
    assert result.returncode == 0
    assert "Detected encoding" not in result.stdout
    assert result.stderr == ""
    assert "Successfully created {}".format(output) in result.stdout


def test_cli_encoding_auto_flag_and_bom(tmp_path, font_path):
    path = tmp_path / "bom.txt"
    path.write_bytes(b"\xef\xbb\xbf" + "日本語\n".encode("utf-8"))
    output = tmp_path / "bom.pdf"
    result = _run(str(path), str(output), "--encoding", "auto")
    assert result.returncode == 0
    assert "Detected encoding: utf-8" in result.stdout
    assert "Warning" not in result.stderr
    from pypdf import PdfReader

    extracted = "\n".join(page.extract_text() or "" for page in PdfReader(str(output)).pages)
    assert "日本語" in extracted
    assert "\ufeff" not in extracted


def test_cli_all_candidates_fail(tmp_path):
    path = tmp_path / "bad.txt"
    path.write_bytes(b"\x81")
    output = tmp_path / "bad.pdf"
    output.write_bytes(b"KEEP-ME")
    result = _run(str(path), str(output))
    assert result.returncode == 1
    assert "Could not decode" in result.stderr
    assert "Detected encoding" not in result.stdout
    assert output.read_bytes() == b"KEEP-ME"
    assert list(tmp_path.glob(".text2pdf-*")) == []


def test_cli_bom_failure_does_not_fall_back(tmp_path):
    path = tmp_path / "bom-bad.txt"
    path.write_bytes(b"\xef\xbb\xbf\xff")
    output = tmp_path / "bom-bad.pdf"
    result = _run(str(path), str(output), "--encoding", "auto")
    assert result.returncode == 1
    assert "utf-8" in result.stderr
    assert "byte 3" in result.stderr
    assert "euc_jis_2004, utf-8, or cp932" not in result.stderr
    assert not output.exists()


def test_default_pdf_is_beside_the_input(tmp_path, font_path):
    folder = tmp_path / "docs"
    folder.mkdir()
    source = folder / "report.txt"
    source.write_bytes("日本語\n".encode("utf-8"))
    result = _run(str(source))
    output = folder / "report.pdf"
    assert result.returncode == 0
    assert output.is_file()
    assert "Successfully created {}".format(output) in result.stdout
    assert "Detected encoding: utf-8" in result.stdout


def test_suffix_is_replaced_and_missing_suffix_is_added(tmp_path, font_path):
    folder = tmp_path / "samples"
    folder.mkdir()
    dat = folder / "example.dat"
    dat.write_bytes(b"data\n")
    bare = folder / "README"
    bare.write_bytes(b"readme\n")
    dat_result = _run(str(dat))
    bare_result = _run(str(bare))
    assert dat_result.returncode == 0
    assert bare_result.returncode == 0
    assert (folder / "example.pdf").is_file()
    assert (folder / "README.pdf").is_file()
    assert not (folder / "example.dat.pdf").exists()


def test_relative_output_stays_in_the_input_directory(tmp_path, font_path):
    source = tmp_path / "example.dat"
    source.write_bytes(b"abc\n")
    result = subprocess.run(
        [sys.executable, str(ROOT / "text2pdf"), "example.dat"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert (tmp_path / "example.pdf").is_file()
    assert "Successfully created example.pdf" in result.stdout


def test_explicit_output_directory_wins(tmp_path, font_path):
    source = tmp_path / "report.txt"
    source.write_bytes(b"abc\n")
    other = tmp_path / "elsewhere"
    other.mkdir()
    output = other / "report.pdf"
    result = _run(str(source), str(output))
    assert result.returncode == 0
    assert output.is_file()
    assert not (tmp_path / "report.pdf").exists()


def test_same_input_and_output_path_is_rejected(tmp_path, font_path, converter_factory):
    source = tmp_path / "notes.txt"
    source.write_bytes(b"keep\n")
    result = _run(str(source), str(tmp_path / "sub" / ".." / "notes.txt"))
    assert result.returncode == 1
    assert "same as the input file" in result.stderr
    assert source.read_bytes() == b"keep\n"

    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"original")
    omitted = _run(str(pdf))
    assert omitted.returncode == 1
    assert "same as the input file" in omitted.stderr
    assert pdf.read_bytes() == b"original"

    converter = converter_factory()
    with pytest.raises(ConversionError) as caught:
        converter.convert(str(source), str(source))
    assert caught.value.exit_code == 1
    assert source.read_bytes() == b"keep\n"


def test_existing_pdf_is_overwritten_on_success(tmp_path, font_path):
    source = tmp_path / "notes.txt"
    source.write_bytes(b"fresh\n")
    output = tmp_path / "notes.pdf"
    output.write_bytes(b"OLD-PDF-CONTENTS")
    result = _run(str(source), str(output))
    assert result.returncode == 0
    data = output.read_bytes()
    assert data.startswith(b"%PDF")
    assert b"OLD-PDF-CONTENTS" not in data


def test_existing_pdf_survives_render_failure(converter_factory, tmp_path, monkeypatch):
    from reportlab.pdfgen import canvas as canvas_module

    converter = converter_factory()
    source = tmp_path / "in.txt"
    source.write_bytes(b"hello\n")
    output = tmp_path / "out.pdf"
    output.write_bytes(b"OLD-PDF-CONTENTS")
    real_canvas = canvas_module.Canvas

    def broken_canvas(*args, **kwargs):
        document = real_canvas(*args, **kwargs)

        def fail():
            raise OSError("disk full")

        document.save = fail
        return document

    monkeypatch.setattr(canvas_module, "Canvas", broken_canvas)
    with pytest.raises(OSError):
        converter.convert(str(source), str(output), encoding="utf-8")
    assert output.read_bytes() == b"OLD-PDF-CONTENTS"
    assert list(tmp_path.glob(".text2pdf-*")) == []


@pytest.mark.parametrize("value", ["5", "17", "6.5", "10.0", "abc", "0"])
def test_cli_rejects_font_size_out_of_range_or_not_an_integer(tmp_path, value):
    path = tmp_path / "plain.txt"
    path.write_bytes(b"abc\n")
    output = tmp_path / "plain.pdf"
    result = _run(str(path), str(output), "--font-size", value)
    assert result.returncode == 2
    assert "font size" in result.stderr
    assert not output.exists()
    assert path.read_bytes() == b"abc\n"
