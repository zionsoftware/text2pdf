"""PDF contents: embedded font, text, tab positions, and page counts.

Text extractors collapse repeated spaces, so column alignment is checked from
drawString positions. A missing-glyph box would show up as U+25A0 or as a tab
character in the extracted text; those are asserted absent separately from
whether the surrounding characters can be extracted at all.
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics

from text2pdf import FONT_NAME, ConversionError

ROOT = Path(__file__).resolve().parents[1]


def _run(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "text2pdf"), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


def _positions(path):
    """Return (text, x, y, size) for every text draw on every page."""
    found = []
    reader = PdfReader(str(path))
    for page_index, page in enumerate(reader.pages):
        def visitor(text, cm, tm, font_dict, font_size, page_index=page_index):
            # pypdf appends a newline to each extracted chunk. That newline is
            # not a drawn glyph, so it must not affect width or token checks.
            text = (text or "").replace("\n", "")
            if not text:
                return
            # cm is the page transform, tm is the text matrix.
            x = cm[0] * tm[4] + cm[2] * tm[5] + cm[4]
            y = cm[1] * tm[4] + cm[3] * tm[5] + cm[5]
            found.append(
                {
                    "page": page_index,
                    "text": text,
                    "x": x,
                    "y": y,
                    "size": font_size,
                }
            )

        page.extract_text(visitor_text=visitor)
    return found, reader


def _embedded_font_names(reader):
    names = []
    embedded = False
    for page in reader.pages:
        resources = page.get("/Resources")
        if resources is None:
            continue
        resources = resources.get_object()
        fonts = resources.get("/Font")
        if fonts is None:
            continue
        fonts = fonts.get_object()
        for font_ref in fonts.values():
            font = font_ref.get_object()
            base = str(font.get("/BaseFont", ""))
            names.append(base)
            descriptor = font.get("/FontDescriptor")
            if descriptor is None:
                continue
            descriptor = descriptor.get_object()
            if any(key in descriptor for key in ("/FontFile2", "/FontFile3", "/FontFile")):
                embedded = True
    return names, embedded


def _write(converter, tmp_path, text, encoding="utf-8", name="input.txt"):
    source = tmp_path / name
    source.write_bytes(text.encode(encoding))
    output = tmp_path / (Path(name).stem + ".pdf")
    converter.convert(str(source), str(output), encoding=encoding)
    return source, output


def test_embeds_ipa_gothic(converter_factory, tmp_path):
    converter = converter_factory()
    _source, output = _write(converter, tmp_path, "ABCあいう①\n", encoding="utf-8")
    _items, reader = _positions(output)
    names, embedded = _embedded_font_names(reader)
    assert any("IPAGothic" in name for name in names)
    assert embedded
    joined_names = " ".join(names)
    assert "HeiseiMin" not in joined_names
    assert "Courier" not in joined_names
    assert "Helvetica" not in joined_names


@pytest.mark.parametrize(
    "text,encoding",
    [
        ("ABC xyz 012\n", "utf-8"),
        ("あいうえお\n", "utf-8"),
        ("ＡＢＣ１２３\n", "utf-8"),
        ("①②③\n", "utf-8"),
        ("あA１B\n", "utf-8"),
        ("日本語ABC\n", "euc_jp"),
        ("丸数字①②③\n", "euc_jis_2004"),
        ("UTF-8 ①あA\n", "utf-8"),
    ],
)
def test_text_round_trip(converter_factory, tmp_path, text, encoding):
    converter = converter_factory()
    _source, output = _write(converter, tmp_path, text, encoding=encoding)
    items, _reader = _positions(output)
    extracted = "".join(item["text"] for item in items)
    body = text.strip("\n")
    assert body in extracted
    # Extraction succeeded, so a replacement box would be visible here too.
    assert "\t" not in extracted
    assert "\u25a0" not in extracted
    assert "\ufffd" not in extracted


def test_tabs_are_not_drawn_as_missing_glyphs(converter_factory, tmp_path):
    converter = converter_factory(font_size=10, tab_size=8, layout="1up")
    text = "AB\tZQ1\nあ\tZQ2\n\tLEAD\nA\t\tFAR\n"
    _source, output = _write(converter, tmp_path, text, encoding="utf-8")
    items, _reader = _positions(output)
    extracted = "".join(item["text"] for item in items)
    for token in ("AB", "ZQ1", "あ", "ZQ2", "LEAD", "FAR"):
        assert token in extracted
    assert "\t" not in extracted
    assert "\u25a0" not in extracted

    def at(token):
        matches = [item for item in items if item["text"] == token]
        assert matches, token
        return matches[0]

    pitch = converter._space_width * 8
    left = converter.margin + converter.padding_left
    # "AB" and "あ" are both 10pt wide, so the following field shares a stop.
    assert at("ZQ1")["x"] == pytest.approx(left + pitch)
    assert at("ZQ2")["x"] == pytest.approx(left + pitch)
    assert at("LEAD")["x"] == pytest.approx(left + pitch)
    assert at("FAR")["x"] == pytest.approx(left + 2 * pitch)
    assert at("ZQ1")["y"] != pytest.approx(at("ZQ2")["y"])


def test_tab_size_changes_pdf_position(converter_factory, tmp_path):
    converter = converter_factory(font_size=10, tab_size=4, layout="1up")
    _source, output = _write(converter, tmp_path, "A\tMARK\n", encoding="utf-8")
    items, _reader = _positions(output)
    mark = next(item for item in items if item["text"] == "MARK")
    left = converter.margin + converter.padding_left
    pitch = converter._space_width * 4
    assert mark["x"] == pytest.approx(left + pitch)


def test_wrapped_tab_line_stays_inside_the_frame(converter_factory, tmp_path):
    converter = converter_factory(layout="2up", font_size=10, tab_size=8)
    text = ("A" * 80) + "\tTAIL\n"
    _source, output = _write(converter, tmp_path, text, encoding="utf-8")
    items, _reader = _positions(output)
    body_top = converter.page_height - converter.margin - converter.header_height
    body_bottom = converter.margin + converter.footer_height
    body_items = [
        item
        for item in items
        if body_bottom < item["y"] < body_top and item["size"] == pytest.approx(10)
    ]
    assert any("TAIL" in item["text"] for item in body_items)
    assert any(item["text"].startswith("A") for item in body_items)
    right_limit = converter.margin + converter.layout_col_width - converter.padding_right
    for item in body_items:
        width = pdfmetrics.stringWidth(item["text"], FONT_NAME, converter.font_size)
        assert item["x"] >= converter.margin + converter.padding_left - 0.5
        assert item["x"] + width <= right_limit + 0.5
        assert "\t" not in item["text"]


def test_1up_and_2up_page_boxes(converter_factory, tmp_path):
    portrait = converter_factory(layout="1up")
    landscape = converter_factory(layout="2up")
    _source, portrait_pdf = _write(portrait, tmp_path, "one\n", name="portrait.txt")
    _source, landscape_pdf = _write(landscape, tmp_path, "one\n", name="landscape.txt")
    portrait_box = PdfReader(str(portrait_pdf)).pages[0].mediabox
    landscape_box = PdfReader(str(landscape_pdf)).pages[0].mediabox
    assert float(portrait_box.width) < float(portrait_box.height)
    assert float(landscape_box.width) > float(landscape_box.height)


def test_empty_file_is_one_page(converter_factory, tmp_path):
    converter = converter_factory(layout="1up")
    source = tmp_path / "input.txt"
    source.write_bytes(b"")
    updated = datetime(2026, 10, 13, 12, 0, 0)
    stamp = updated.timestamp()
    os.utime(source, (stamp, stamp))
    output = tmp_path / "input.pdf"
    converter.convert(str(source), str(output), encoding="utf-8")
    items, reader = _positions(output)
    assert len(reader.pages) == 1
    extracted = "".join(item["text"] for item in items)
    assert "1 / 1" in extracted
    assert "Printed by tester" in extracted
    assert "Updated 2026-10-13 12:00:00" in extracted


def test_header_shows_input_mtime_on_every_page(converter_factory, tmp_path):
    converter = converter_factory(layout="1up", font_size=10)
    total = converter.lines_per_page + 1
    lines = ["L{:04d}".format(i) for i in range(total)]
    source = tmp_path / "pages.txt"
    source.write_text("\n".join(lines) + "\n", encoding="utf-8")
    updated = datetime(2001, 2, 3, 4, 5, 6)
    stamp = updated.timestamp()
    os.utime(source, (stamp, stamp))
    output = tmp_path / "pages.pdf"
    converter.convert(str(source), str(output), encoding="utf-8")
    items, reader = _positions(output)
    assert len(reader.pages) > 1
    expected = "Updated {}".format(updated.strftime("%Y-%m-%d %H:%M:%S"))
    for page_index in range(len(reader.pages)):
        page_text = "".join(
            item["text"] for item in items if item["page"] == page_index
        )
        assert expected in page_text


def test_page_numbers_follow_wrapped_line_count(converter_factory, tmp_path):
    converter = converter_factory(layout="1up", font_size=10)
    total = converter.lines_per_page + 1
    lines = ["L{:04d}".format(i) for i in range(total)]
    _source, output = _write(converter, tmp_path, "\n".join(lines) + "\n")
    items, reader = _positions(output)
    assert len(reader.pages) == 2
    page0 = "".join(item["text"] for item in items if item["page"] == 0)
    page1 = "".join(item["text"] for item in items if item["page"] == 1)
    assert "1 / 2" in page0
    assert "2 / 2" in page1
    assert "L0000" in page0
    assert "L{:04d}".format(total - 1) in page1
    assert "L{:04d}".format(total - 1) not in page0


def test_2up_second_column_and_second_page(converter_factory, tmp_path):
    converter = converter_factory(layout="2up", font_size=10)
    marker_index = converter.lines_per_col
    page2_index = converter.lines_per_page
    total = page2_index + 1
    lines = ["R{:04d}".format(i) for i in range(total)]
    _source, output = _write(converter, tmp_path, "\n".join(lines) + "\n")
    items, reader = _positions(output)
    assert len(reader.pages) == 2

    right_x = (
        converter.margin
        + converter.layout_col_width
        + converter.column_gap
        + converter.padding_left
    )
    right_marker = "R{:04d}".format(marker_index)
    right_item = next(item for item in items if item["text"] == right_marker)
    assert right_item["page"] == 0
    assert right_item["x"] == pytest.approx(right_x)

    page1 = "".join(item["text"] for item in items if item["page"] == 1)
    assert "2 / 2" in page1
    assert "R{:04d}".format(page2_index) in page1


def test_header_and_footer_do_not_overlap(converter_factory, tmp_path):
    converter = converter_factory(layout="1up")
    nested = tmp_path
    for _ in range(6):
        nested = nested / ("dir_" + "n" * 40)
    nested.mkdir(parents=True)
    source = nested / ("file_" + "m" * 80 + ".txt")
    source.write_text("body\n", encoding="utf-8")
    output = tmp_path / "long.pdf"
    converter.convert(str(source), str(output), encoding="utf-8")
    items, _reader = _positions(output)

    info = next(item for item in items if "Printed by tester" in item["text"])
    page = next(item for item in items if item["text"] == "1 / 1")
    header_left = [
        item
        for item in items
        if item["size"] == pytest.approx(13) and item["y"] == pytest.approx(info["y"], abs=5)
    ]
    assert header_left
    name = header_left[0]
    name_width = pdfmetrics.stringWidth(name["text"], FONT_NAME, 13)
    info_width = pdfmetrics.stringWidth(info["text"], FONT_NAME, 10)
    assert name["x"] + name_width <= info["x"] - 5
    assert "..." in name["text"]

    footer_paths = [
        item
        for item in items
        if item["y"] == pytest.approx(page["y"]) and item["text"] != page["text"]
    ]
    assert footer_paths
    path_item = footer_paths[0]
    path_width = pdfmetrics.stringWidth(path_item["text"], FONT_NAME, 10)
    assert path_item["x"] + path_width <= page["x"] - 5
    assert "..." in path_item["text"]
    assert info["x"] + info_width <= converter.page_width - converter.margin


def test_body_text_stays_inside_the_frame(converter_factory, tmp_path):
    converter = converter_factory(layout="1up", font_size=10)
    text = "あいうえおABC" * 30 + "\n①②③\n"
    _source, output = _write(converter, tmp_path, text, encoding="utf-8")
    items, _reader = _positions(output)
    body_top = converter.page_height - converter.margin - converter.header_height
    body_bottom = converter.margin + converter.footer_height
    face = pdfmetrics.getFont(FONT_NAME).face
    ascent = face.ascent / 1000.0 * converter.font_size
    descent = face.descent / 1000.0 * converter.font_size
    saw_body = False
    for item in items:
        if not (body_bottom < item["y"] < body_top):
            continue
        if item["size"] != pytest.approx(converter.font_size):
            continue
        saw_body = True
        width = pdfmetrics.stringWidth(item["text"], FONT_NAME, converter.font_size)
        right_limit = (
            converter.margin + converter.body_width - converter.padding_right
        )
        assert item["x"] >= converter.margin + converter.padding_left - 0.5
        assert item["x"] + width <= right_limit + 0.5
        assert item["y"] + ascent <= body_top + 0.5
        assert item["y"] + descent >= body_bottom - 0.5
    assert saw_body


def test_failed_save_does_not_leave_a_pdf(converter_factory, tmp_path, monkeypatch):
    from reportlab.pdfgen import canvas as canvas_module

    converter = converter_factory()
    source = tmp_path / "in.txt"
    source.write_bytes(b"hello\n")
    output = tmp_path / "out.pdf"
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
    assert not output.exists()
    assert list(tmp_path.glob(".text2pdf-*")) == []


def test_missing_font_raises_before_writing(tmp_path):
    from text2pdf import TextToPdfConverter

    source = tmp_path / "in.txt"
    source.write_bytes(b"hello\n")
    output = tmp_path / "out.pdf"
    with pytest.raises(ConversionError) as caught:
        TextToPdfConverter(
            font_path=str(tmp_path / "no-such-font.ttf"),
            user="tester",
        )
    assert caught.value.exit_code == 1
    assert "Font file not found" in str(caught.value)
    assert not output.exists()


def test_default_samples_convert(converter_factory, tmp_path):
    english = ROOT / "samples" / "english_sample.txt"
    program = ROOT / "samples" / "program_sample.py"
    mixed = ROOT / "samples" / "mixed_euc_jis_2004.txt"
    assert english.is_file()
    assert program.is_file()
    assert mixed.is_file()

    converter = converter_factory(layout="2up")
    for source, encoding in (
        (english, "euc_jis_2004"),
        (program, "utf-8"),
        (mixed, "euc_jis_2004"),
    ):
        output = tmp_path / (source.stem + ".pdf")
        converter.convert(str(source), str(output), encoding=encoding)
        items, reader = _positions(output)
        names, embedded = _embedded_font_names(reader)
        assert reader.pages
        assert embedded
        assert any("IPAGothic" in name for name in names)
        extracted = "".join(item["text"] for item in items)
        assert "\t" not in extracted
        assert "\u25a0" not in extracted
        assert source.name in extracted or "..." in extracted


@pytest.mark.parametrize("layout", ["1up", "2up"])
@pytest.mark.parametrize(
    "argument,size",
    [
        ("6", 6),
        ("8", 8),
        ("10", 10),
        ("12", 12),
        ("16", 16),
        ("large", 11),
        ("medium", 10),
        ("small", 8),
    ],
)
def test_cli_font_size_sets_body_and_keeps_chrome(tmp_path, layout, argument, size):
    source = tmp_path / "body.txt"
    source.write_bytes(b"ABC\n")
    output = tmp_path / "body.pdf"
    result = _run(
        str(source),
        str(output),
        "--layout",
        layout,
        "--font-size",
        argument,
    )
    assert result.returncode == 0, result.stderr
    items, reader = _positions(output)
    box = reader.pages[0].mediabox
    if layout == "1up":
        assert float(box.width) < float(box.height)
    else:
        assert float(box.width) > float(box.height)
    assert any(
        item["text"] == "ABC" and item["size"] == pytest.approx(size) for item in items
    )
    assert any(item["size"] == pytest.approx(13) for item in items)
    page = next(item for item in items if item["text"] == "1 / 1")
    info = next(item for item in items if "Printed by" in item["text"])
    assert page["size"] == pytest.approx(10)
    assert info["size"] == pytest.approx(10)


def test_cli_default_font_size_is_medium(tmp_path):
    source = tmp_path / "body.txt"
    source.write_bytes(b"ABC\n")
    output = tmp_path / "body.pdf"
    result = _run(str(source), str(output), "--layout", "1up")
    assert result.returncode == 0, result.stderr
    items, _reader = _positions(output)
    assert any(
        item["text"] == "ABC" and item["size"] == pytest.approx(10) for item in items
    )


def test_larger_font_wraps_sooner_and_stays_inside_the_frame(converter_factory, tmp_path):
    text = "A" * 120
    small = converter_factory(font_size=6, layout="1up")
    large = converter_factory(font_size=16, layout="1up")
    assert len(small.layout_text_line(text)) < len(large.layout_text_line(text))
    assert large.lines_per_col < small.lines_per_col

    face = pdfmetrics.getFont(FONT_NAME).face
    for converter in (small, large):
        _source, output = _write(
            converter,
            tmp_path,
            text + "\n",
            name="wrap-{}.txt".format(converter.font_size),
        )
        items, _reader = _positions(output)
        body_top = converter.page_height - converter.margin - converter.header_height
        body_bottom = converter.margin + converter.footer_height
        ascent = face.ascent / 1000.0 * converter.font_size
        descent = face.descent / 1000.0 * converter.font_size
        saw_body = False
        for item in items:
            if not (body_bottom < item["y"] < body_top):
                continue
            if item["size"] != pytest.approx(converter.font_size):
                continue
            saw_body = True
            width = pdfmetrics.stringWidth(item["text"], FONT_NAME, converter.font_size)
            right_limit = converter.margin + converter.body_width - converter.padding_right
            assert item["x"] >= converter.margin + converter.padding_left - 0.5
            assert item["x"] + width <= right_limit + 0.5
            assert item["y"] + ascent <= body_top + 0.5
            assert item["y"] + descent >= body_bottom - 0.5
        assert saw_body


def test_2up_numeric_font_wraps_inside_the_column(converter_factory, tmp_path):
    converter = converter_factory(layout="2up", font_size=16)
    _source, output = _write(converter, tmp_path, ("B" * 80) + "\n", name="wide.txt")
    items, reader = _positions(output)
    box = reader.pages[0].mediabox
    assert float(box.width) > float(box.height)
    body_top = converter.page_height - converter.margin - converter.header_height
    body_bottom = converter.margin + converter.footer_height
    body_items = [
        item
        for item in items
        if body_bottom < item["y"] < body_top and item["size"] == pytest.approx(16)
    ]
    assert len(body_items) > 1
    right_limit = converter.margin + converter.layout_col_width - converter.padding_right
    for item in body_items:
        width = pdfmetrics.stringWidth(item["text"], FONT_NAME, 16)
        assert item["x"] + width <= right_limit + 0.5
    assert any(item["size"] == pytest.approx(13) for item in items)


def test_samples_convert_with_auto_detection(converter_factory, tmp_path, capsys):
    samples = [
        (ROOT / "samples" / "english_sample.txt", "utf-8"),
        (ROOT / "samples" / "program_sample.py", "utf-8"),
        (ROOT / "samples" / "mixed_euc_jis_2004.txt", "euc_jis_2004"),
    ]
    converter = converter_factory(layout="1up", font_size=12)
    for source, encoding in samples:
        output = tmp_path / (source.stem + "-auto.pdf")
        converter.convert(str(source), str(output))
        captured = capsys.readouterr()
        assert "Detected encoding: {}".format(encoding) in captured.out
        assert "Warning" not in captured.err
        items, reader = _positions(output)
        assert reader.pages
        body = [item for item in items if item["size"] == pytest.approx(12)]
        assert body
        extracted = "".join(item["text"] for item in items)
        assert "\t" not in extracted
        assert "\u25a0" not in extracted
