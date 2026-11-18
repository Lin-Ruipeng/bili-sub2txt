"""Tests for QR image file output (login --qr-out)."""

import pytest

from bili_sub2txt.bilibili.qr_output import QrOutputError, write_qr_image

pytest.importorskip("qrcode")

URL = "https://passport.bilibili.com/h5-app/passport/login/scan?navhide=1&qrcode_key=abc"


class TestWriteQrImage:
    def test_svg_output(self, tmp_path):
        p = write_qr_image(URL, tmp_path / "login.svg")
        assert p.exists()
        text = p.read_text(encoding="utf-8")
        assert "<svg" in text  # header is an <?xml?> declaration

    def test_png_output(self, tmp_path):
        PIL = pytest.importorskip("PIL")
        p = write_qr_image(URL, tmp_path / "login.png")
        assert p.exists()
        with PIL.Image.open(p) as im:
            assert im.size[0] == im.size[1]  # QR codes are square
            assert im.size[0] > 0

    def test_unsupported_extension_raises(self, tmp_path):
        with pytest.raises(QrOutputError, match="不支持的二维码输出格式"):
            write_qr_image(URL, tmp_path / "login.bmp")

    def test_missing_extension_raises(self, tmp_path):
        with pytest.raises(QrOutputError, match="不支持的二维码输出格式"):
            write_qr_image(URL, tmp_path / "login")
