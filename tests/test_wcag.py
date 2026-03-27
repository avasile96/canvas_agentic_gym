"""Tests for WCAG contrast ratio utilities."""

import pytest

from marketcanvas.wcag import contrast_ratio, hex_to_rgb, meets_aa, relative_luminance


class TestHexToRgb:
    def test_black(self):
        assert hex_to_rgb("#000000") == (0, 0, 0)

    def test_white(self):
        assert hex_to_rgb("#FFFFFF") == (255, 255, 255)

    def test_red(self):
        assert hex_to_rgb("#FF0000") == (255, 0, 0)

    def test_no_hash(self):
        assert hex_to_rgb("00FF00") == (0, 255, 0)


class TestRelativeLuminance:
    def test_black(self):
        assert relative_luminance(0, 0, 0) == 0.0

    def test_white(self):
        assert relative_luminance(255, 255, 255) == pytest.approx(1.0, abs=0.001)

    def test_red(self):
        assert relative_luminance(255, 0, 0) == pytest.approx(0.2126, abs=0.001)


class TestContrastRatio:
    def test_black_on_white(self):
        assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0, abs=0.1)

    def test_same_color(self):
        assert contrast_ratio("#FFFFFF", "#FFFFFF") == pytest.approx(1.0, abs=0.01)

    def test_symmetric(self):
        r1 = contrast_ratio("#FF0000", "#0000FF")
        r2 = contrast_ratio("#0000FF", "#FF0000")
        assert r1 == pytest.approx(r2, abs=0.01)

    def test_gray_on_white_known(self):
        # #767676 on white is the classic AA boundary (~4.54:1)
        assert contrast_ratio("#767676", "#FFFFFF") >= 4.5


class TestMeetsAA:
    def test_black_on_white_passes(self):
        assert meets_aa("#000000", "#FFFFFF") is True

    def test_same_color_fails(self):
        assert meets_aa("#FFFFFF", "#FFFFFF") is False

    def test_large_text_lower_threshold(self):
        # #808080 on white ≈ 3.95:1 — fails normal AA, passes large text
        assert meets_aa("#808080", "#FFFFFF", large_text=False) is False
        assert meets_aa("#808080", "#FFFFFF", large_text=True) is True
