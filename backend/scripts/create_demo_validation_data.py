"""Create synthetic validation fixtures outside the real controlled-data directory."""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "demo" / "fixtures" / "validation"
MARKERS = {"valid_test": (20, 170, 80), "shirt": (220, 60, 70), "wall": (160, 160, 160), "tree": (35, 130, 55), "random_object": (220, 150, 30), "screenshot": (90, 80, 190), "empty": (245, 245, 245), "wrong_kit": (200, 80, 180), "blurred": (80, 170, 200), "bad_framing": (30, 30, 30)}
def make_fixture(label: str, marker: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", (640, 480), marker); draw = ImageDraw.Draw(image)
    if label == "valid_test":
        draw.rounded_rectangle((145, 70, 495, 420), radius=20, fill=(235, 235, 225), outline=(40, 40, 40), width=10); draw.rectangle((245, 155, 395, 330), fill=(205, 205, 195), outline=(40, 40, 40), width=5)
    elif label == "shirt": draw.polygon([(230, 80), (410, 80), (540, 220), (450, 440), (190, 440), (100, 220)], fill=(55, 100, 185))
    elif label == "tree": draw.rectangle((285, 260, 350, 460), fill=(110, 70, 35)); draw.ellipse((130, 45, 500, 325), fill=(35, 105, 45))
    elif label == "random_object": draw.ellipse((185, 90, 455, 390), fill=(70, 120, 210), outline=(20, 20, 20), width=10)
    elif label == "screenshot":
        draw.rectangle((65, 45, 575, 435), fill=(245, 245, 245)); draw.rectangle((65, 45, 575, 100), fill=(45, 60, 100)); draw.line((100, 150, 520, 150), fill=(90, 90, 90), width=14)
    elif label == "wrong_kit": draw.rectangle((120, 60, 520, 430), fill=(245, 210, 235), outline=(80, 30, 70), width=12); draw.text((225, 220), "OTHER KIT", fill=(80, 30, 70))
    elif label == "bad_framing": draw.rectangle((0, 0, 150, 480), fill=(230, 230, 225)); draw.rectangle((100, 100, 620, 500), outline=(220, 220, 225), width=12)
    elif label == "empty": pass
    elif label == "wall":
        for y in range(0, 480, 40): draw.line((0, y, 640, y), fill=(140, 140, 140), width=2)
    elif label == "blurred":
        draw.rounded_rectangle((145, 70, 495, 420), radius=20, fill=(235, 235, 225), outline=(40, 40, 40), width=10); image = image.filter(ImageFilter.GaussianBlur(12))
    # Stored after effects so deterministic marker recognition remains reliable.
    ImageDraw.Draw(image).rectangle((0, 0, 4, 4), fill=marker)
    return image
def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for label, marker in MARKERS.items(): make_fixture(label, marker).save(OUT / f"{label}.png")
    print(f"Created {len(MARKERS)} synthetic validation fixtures in {OUT}")
    print("These are software-testing fixtures only. They are not chemical-test data and were not added to data/.")
    return 0
if __name__ == "__main__": raise SystemExit(main())
