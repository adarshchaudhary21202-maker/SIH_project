"""Print a judge-friendly demo analysis without mixing it with real-data training."""
from __future__ import annotations
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ai.baseline import load_service
from app.core.config import settings
def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze one image using the configured SIH prototype mode.")
    parser.add_argument("image", type=Path); args = parser.parse_args()
    if not args.image.is_file(): print(f"Image not found: {args.image}", file=sys.stderr); return 2
    result = load_service(settings.AI_DEMO_MODE, settings.AI_DEMO_PROFILE).analyze_image(args.image.read_bytes())
    print("Validation\n----------")
    for key in ("valid", "validation_reason", "kit_detected", "test_area_detected", "quality_score", "calibration_score"): print(f"{key}: {getattr(result, key)}")
    print("\nClassification\n--------------")
    for key in ("result", "confidence", "explanation", "model_version"): print(f"{key}: {getattr(result, key).value if key == 'result' else getattr(result, key)}")
    return 0
if __name__ == "__main__": raise SystemExit(main())
