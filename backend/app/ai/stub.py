from io import BytesIO
from PIL import Image, ImageStat, UnidentifiedImageError
from app.ai.interface import AIServiceInterface
from app.ai.interface import AIResult, PresumptiveResult

class AIServiceStub(AIServiceInterface):
    """
    Mock implementation of AIService for local development and unit tests.
    Avoids loading real machine learning weights while satisfying system architecture.
    """

    model_version = "baseline-fallback-0.1.0"
    def analyze_image(self, image_bytes: bytes) -> AIResult:
        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError):
            return AIResult(valid=False, validation_reason="INVALID_TEST_IMAGE", kit_detected=False, test_area_detected=False, quality_score=0, calibration_score=0, result=PresumptiveResult.INCONCLUSIVE, confidence=0, explanation="No presumptive result: image cannot be decoded; retake a clear target-kit photo. This is not definitive drug identification.", model_version=self.model_version)
        width, height = image.size
        luminance = ImageStat.Stat(image.convert("L")).mean[0] / 255
        quality = min(1.0, (min(width, height) / 720) * 0.65 + 0.35)
        calibration = 1.0 - min(0.55, abs(luminance - 0.55))
        return AIResult(valid=False, validation_reason="INVALID_TEST_IMAGE", kit_detected=False, test_area_detected=False, quality_score=round(quality,3), calibration_score=round(calibration,3), result=PresumptiveResult.INCONCLUSIVE, confidence=0, explanation="No presumptive result: retake with a controlled, validated target-kit image. This is not definitive drug identification.", model_version=self.model_version)

