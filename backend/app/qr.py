"""QR rendering for the opaque evidence reference (no sensitive metadata is encoded)."""
from io import BytesIO
import qrcode

def render_qr(reference: str) -> bytes:
    image = qrcode.make(reference)
    output = BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()
