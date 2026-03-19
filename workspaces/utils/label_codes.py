# workspaces/utils/label_codes.py

import base64
from io import BytesIO

import barcode
from barcode.writer import ImageWriter
import qrcode
from qrcode.constants import ERROR_CORRECT_M


def make_barcode_png(data: str) -> str:
    """
    Return a data: URL for a high-res Code128 barcode PNG.
    Using Code128 avoids length restrictions of pure EAN.
    """
    # You can switch to 'ean13' later if you enforce 12-digit input.
    BClass = barcode.get_barcode_class("code128")

    options = {
        "module_height": 20.0,   # bar height in mm-ish units
        "module_width": 0.25,    # thin bar width; smaller -> higher resolution
        "font_size": 10,
        "text_distance": 5.0,
        "quiet_zone": 3.0,
    }

    buf = BytesIO()
    BClass(data, writer=ImageWriter()).write(buf, options)
    png_bytes = buf.getvalue()

    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")


def make_qr_png(data: str) -> str:
    """
    Return a data: URL for a high-res QR PNG.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,  # more robust for print
        box_size=8,                       # pixels per module
        border=4,                          # quiet zone
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")