"""Tab stops follow font width, not character count."""

import pytest

from text2pdf import layout_line


def ascii_width(ch):
    """Half-width for ASCII, full-width (two spaces) for everything else."""
    if ord(ch) < 128:
        return 5.0
    return 10.0


def _layout(text, col_width=400, tab_size=8, char_width=ascii_width, space_width=5.0):
    return layout_line(text, col_width, char_width, space_width, tab_size)


def _texts(lines):
    return [[text for _x, text in line] for line in lines]


def test_leading_tab_advances_one_stop():
    lines = _layout("\tAB")
    assert lines == [[(40.0, "AB")]]
    assert "\t" not in lines[0][0][1]


def test_tab_in_the_middle_of_a_line():
    lines = _layout("AB\tC")
    assert lines == [[(0.0, "AB"), (40.0, "C")]]


def test_consecutive_tabs():
    lines = _layout("\t\tZ")
    assert lines == [[(80.0, "Z")]]


def test_japanese_and_ascii_share_tab_stops():
    # "あ" is two ASCII columns, the same width as "AB".
    japanese = _layout("あ\tX")
    ascii_line = _layout("AB\tX")
    assert japanese == [[(0.0, "あ"), (40.0, "X")]]
    assert ascii_line == [[(0.0, "AB"), (40.0, "X")]]
    assert japanese[0][1][0] == ascii_line[0][1][0]


def test_fullwidth_ascii_counts_as_two_columns():
    lines = _layout("Ａ\tZ")
    assert lines == [[(0.0, "Ａ"), (40.0, "Z")]]


def test_custom_tab_size():
    lines = _layout("A\tB", tab_size=4)
    assert lines == [[(0.0, "A"), (20.0, "B")]]


def test_tab_size_must_be_positive():
    with pytest.raises(ValueError):
        _layout("A", tab_size=0)


def test_wrapping_uses_expanded_tab_width():
    # 8 ASCII characters land on a tab stop. The next tab does not fit
    # in a 50pt column (pitch is 40pt), so the remainder starts a new line.
    lines = _layout("ABCDEFGH\tZ", col_width=50)
    assert lines[0] == [(0.0, "ABCDEFGH")]
    assert lines[1] == [(40.0, "Z")]
    for line in lines:
        for x, text in line:
            assert "\t" not in text
            assert x >= 0


def test_long_line_wraps_on_glyph_width():
    lines = _layout("ABCD", col_width=12)
    assert lines == [[(0.0, "AB")], [(0.0, "CD")]]
    for line in lines:
        for x, text in line:
            assert x + len(text) * 5 <= 12


def test_character_wider_than_the_column_does_not_loop():
    lines = _layout("あ", col_width=8)
    assert lines == [[(0.0, "あ")]]


def test_tab_wider_than_the_column_is_skipped():
    lines = _layout("\t" * 20 + "Z", col_width=30, tab_size=8)
    assert len(lines) < 10
    assert lines == [[(0.0, "Z")]]


def test_empty_line_is_preserved():
    assert _layout("") == [[]]


def test_real_font_matches_column_model(converter_factory):
    converter = converter_factory(font_size=10, tab_size=8)
    japanese = converter.layout_text_line("あ\tX")
    ascii_line = converter.layout_text_line("AB\tX")
    fullwidth = converter.layout_text_line("ＡＢ\tX")
    assert japanese[0][1][0] == pytest.approx(ascii_line[0][1][0])
    assert fullwidth[0][1][0] == pytest.approx(ascii_line[0][1][0])
    assert "\t" not in japanese[0][0][1]

    wrapped = converter.layout_text_line("A" * 400 + "\tEND")
    assert len(wrapped) > 1
    flat = [text for line in wrapped for _x, text in line]
    assert any("END" in text for text in flat)
    for line in wrapped:
        for x, text in line:
            assert "\t" not in text
            assert "\u25a0" not in text
            width = converter.char_width(text)
            assert x + width <= converter.col_width + 0.05
