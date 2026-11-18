"""Write login QR codes to image files (PNG / SVG).

Used by the CLI ``login --qr-out`` option (issue #7, P1) so that
non-interactive environments can present the QR code as a file.

Formats:
  - ``.svg`` — pure ``qrcode`` package (``qrcode.image.svg`` factory),
    zero extra dependencies;
  - ``.png`` — requires Pillow (install extra ``qrcode[pil]``); a missing
    Pillow raises an actionable error instead of a bare ImportError.

Note for custom renderers: ``qrcode`` 8.x ``QRCode.get_matrix()`` already
includes the quiet-zone border — do not add it again.
"""

from pathlib import Path

from bili_sub2txt.errors import BiliError


class QrOutputError(BiliError):
    """Failed to write the QR code image file."""


def write_qr_image(url: str, path: str | Path) -> Path:
    """Render *url* as a QR image at *path* (format chosen by extension).

    Returns the written path.  Raises ``QrOutputError`` on unsupported
    extensions or missing optional dependencies.
    """
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix == ".svg":
        try:
            import qrcode
            import qrcode.image.svg
        except ImportError as exc:
            raise QrOutputError(
                "SVG 输出需要 qrcode 库: pip install 'bili-sub2txt[download]'"
            ) from exc
        try:
            qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage).save(str(p))
        except OSError as exc:
            raise QrOutputError(f"无法写入二维码文件 {p}: {exc}") from exc
        return p

    if suffix == ".png":
        try:
            import qrcode
        except ImportError as exc:
            raise QrOutputError(
                "PNG 输出需要 qrcode 库: pip install 'bili-sub2txt[download]'"
            ) from exc
        try:
            import PIL  # noqa: F401 — presence check only
        except ImportError as exc:
            raise QrOutputError(
                "PNG 输出需要 Pillow: pip install 'qrcode[pil]' (或改用 --qr-out xxx.svg)"
            ) from exc
        try:
            qrcode.make(url).save(str(p))
        except OSError as exc:
            raise QrOutputError(f"无法写入二维码文件 {p}: {exc}") from exc
        return p

    raise QrOutputError(f"不支持的二维码输出格式 {suffix or '(无扩展名)'}: 仅支持 .png / .svg")
