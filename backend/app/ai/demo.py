"""Visible deterministic SIH workflow demo. It is not a chemical model."""
from __future__ import annotations
from io import BytesIO
import numpy as np
from PIL import Image, UnidentifiedImageError
from app.ai.baseline import quality_metrics
from app.ai.interface import AIResult, AIServiceInterface, PresumptiveResult

# Marker pixels are used only by files made by create_demo_validation_data.py.
FIXTURE_MARKERS = {
    (20, 170, 80): "valid_test", (220, 60, 70): "shirt", (160, 160, 160): "wall",
    (35, 130, 55): "tree", (220, 150, 30): "random_object", (90, 80, 190): "screenshot",
    (245, 245, 245): "empty", (200, 80, 180): "wrong_kit", (80, 170, 200): "blurred",
    (30, 30, 30): "bad_framing",
}
VALID_PROFILES = {item.value for item in PresumptiveResult}

class DemoAIService(AIServiceInterface):
    """Accepts only documented synthetic validation fixtures in explicit demo mode."""
    model_version = "prototype-demo-0.1.0"
    mode = "DEMO"

    def __init__(self, profile: str = "INCONCLUSIVE"):
        self.profile = profile if profile in VALID_PROFILES else "INCONCLUSIVE"

    @staticmethod
    def _fixture_label(image: Image.Image) -> str | None:
        pixel = np.asarray(image.convert("RGB"), dtype=np.int16)[0, 0]
        for marker, label in FIXTURE_MARKERS.items():
            if int(np.abs(pixel - marker).sum()) <= 30:
                return label
        return None

    def analyze_image(self, image_bytes: bytes) -> AIResult:
        try: image = Image.open(BytesIO(image_bytes)).convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError):
            return AIResult(valid=False, validation_reason="INVALID_TEST_IMAGE", kit_detected=False, test_area_detected=False, quality_score=0, calibration_score=0, result=PresumptiveResult.INCONCLUSIVE, confidence=0, explanation="Demo mode: unreadable image. Retake a clear target-kit image. Presumptive result only; not definitive drug identification.", model_version=self.model_version)
        label = self._fixture_label(image)
        quality, calibration = quality_metrics(image)
        if label != "valid_test":
            reason = "INVALID_TEST_IMAGE" if label else "UNRECOGNIZED_DEMO_IMAGE"
            detail = label or "an unrecognized image"
            return AIResult(valid=False, validation_reason=reason, kit_detected=False, test_area_detected=False, quality_score=quality, calibration_score=calibration, result=PresumptiveResult.INCONCLUSIVE, confidence=0, explanation=f"Demo mode: validation rejected {detail}; chemical classification was skipped. Presumptive result only; not definitive drug identification.", model_version=self.model_version)
        if quality < .30 or calibration < .35:
            return AIResult(valid=True, validation_reason="VALID_TEST_IMAGE_QUALITY_INSUFFICIENT", kit_detected=True, test_area_detected=True, quality_score=quality, calibration_score=calibration, result=PresumptiveResult.INCONCLUSIVE, confidence=0, explanation="Demo mode: valid prototype test fixture has insufficient quality; retake the image. Presumptive result only; not definitive drug identification.", model_version=self.model_version)
        result = PresumptiveResult(self.profile)
        return AIResult(valid=True, validation_reason="VALID_TEST_IMAGE", kit_detected=True, test_area_detected=True, quality_score=quality, calibration_score=calibration, result=result, confidence=0, explanation="Demo mode workflow state selected by AI_DEMO_PROFILE; no chemical model or forensic ground truth was used. Presumptive result only; not definitive drug identification.", model_version=self.model_version)
