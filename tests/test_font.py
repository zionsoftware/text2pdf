"""Discovery of ipag.ttf under the standard font directories."""

import os

import pytest

from text2pdf import ConversionError, find_ipa_gothic


def test_finds_ipag_in_a_subdirectory(tmp_path):
    nested = tmp_path / "ipa-gothic"
    nested.mkdir()
    font = nested / "ipag.ttf"
    font.write_bytes(b"font")
    (tmp_path / "ipagp.ttf").write_bytes(b"p-gothic")
    (tmp_path / "ipam.ttf").write_bytes(b"mincho")
    assert find_ipa_gothic([str(tmp_path)]) == str(font)


def test_filename_match_ignores_case(tmp_path):
    font = tmp_path / "IPAG.TTF"
    font.write_bytes(b"font")
    assert find_ipa_gothic([str(tmp_path)]) == str(font)


def test_earlier_search_directory_wins(tmp_path):
    first = tmp_path / "system"
    second = tmp_path / "user"
    first.mkdir()
    second.mkdir()
    system_font = first / "sub" / "ipag.ttf"
    system_font.parent.mkdir()
    system_font.write_bytes(b"system")
    (second / "ipag.ttf").write_bytes(b"user")
    assert find_ipa_gothic([str(first), str(second)]) == str(system_font)


def test_missing_font_directory_is_skipped(tmp_path):
    present = tmp_path / "fonts"
    present.mkdir()
    font = present / "ipag.ttf"
    font.write_bytes(b"font")
    assert find_ipa_gothic([str(tmp_path / "missing"), str(present)]) == str(font)


def test_missing_ipa_gothic_raises(tmp_path):
    (tmp_path / "ipagp.ttf").write_bytes(b"other")
    with pytest.raises(ConversionError) as caught:
        find_ipa_gothic([str(tmp_path)])
    message = str(caught.value)
    assert caught.value.exit_code == 1
    assert "Cannot run" in message
    assert "ipag.ttf" in message
    assert "/usr/share/fonts/ipa-gothic/" in message
    assert "--font-path" in message


def test_installed_ipa_gothic_is_under_the_system_font_dir():
    path = find_ipa_gothic()
    assert os.path.basename(path).lower() == "ipag.ttf"
    assert os.path.isfile(path)
    assert path.startswith("/usr/share/fonts/")
