"""Small scikit-learn baseline trained only from the controlled manifest."""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
import joblib
import numpy as np
from PIL import Image, UnidentifiedImageError
from app.ai.interface import AIResult, AIServiceInterface, PresumptiveResult

ARTIFACT = Path(__file__).resolve().parents[2] / "artifacts" / "baseline.joblib"

def image_features(image: Image.Image) -> np.ndarray:
    image = image.convert("RGB").resize((128, 128))
    hsv = np.asarray(image.convert("HSV"), dtype=np.float32) / 255
    rgb = np.asarray(image, dtype=np.float32) / 255
    return np.concatenate([hsv.mean((0,1)), hsv.std((0,1)), rgb.mean((0,1)), rgb.std((0,1))])

def quality_metrics(image: Image.Image) -> tuple[float, float]:
    """Prototype image-quality and lighting heuristics, not scientific measurements."""
    gray = np.asarray(image.convert("L").resize((256, 256)), dtype=np.float32)
    sharpness = min(1.0, float(np.var(np.diff(gray, axis=0)) + np.var(np.diff(gray, axis=1))) / 500.0)
    brightness = float(gray.mean() / 255.0)
    contrast = min(1.0, float(gray.std()) / 64.0)
    exposure = max(0.0, 1.0 - abs(brightness - 0.55) / 0.55)
    size = min(1.0, min(image.size) / 256.0)
    quality = round(0.40 * sharpness + 0.25 * contrast + 0.20 * exposure + 0.15 * size, 3)
    calibration = round(0.65 * exposure + 0.35 * contrast, 3)
    return quality, calibration

class BaselineAIService(AIServiceInterface):
    def __init__(self, artifact: Path = ARTIFACT):
        saved = joblib.load(artifact)
        self.validation_model, self.chemical_model = saved["validation_model"], saved["chemical_model"]
        self.model_version = saved["metadata"]["model_version"]

    def analyze_image(self, image_bytes: bytes) -> AIResult:
        try: image = Image.open(BytesIO(image_bytes)).convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError):
            return AIResult(valid=False,validation_reason="INVALID_TEST_IMAGE",kit_detected=False,test_area_detected=False,quality_score=0,calibration_score=0,result=PresumptiveResult.INCONCLUSIVE,confidence=0,explanation="No presumptive result: image cannot be decoded; retake a clear target-kit image. This is not definitive drug identification.",model_version=self.model_version)
        x = image_features(image).reshape(1,-1)
        validation = self.validation_model.predict(x)[0]
        quality, calibration = quality_metrics(image)
        if validation != "valid_test":
            return AIResult(valid=False,validation_reason="INVALID_TEST_IMAGE",kit_detected=False,test_area_detected=False,quality_score=quality,calibration_score=calibration,result=PresumptiveResult.INCONCLUSIVE,confidence=round(float(self.validation_model.predict_proba(x).max()),3),explanation=f"No presumptive result: validation classified this image as {validation}; retake the target-kit photo. This is not definitive drug identification.",model_version=self.model_version)
        if quality < .30 or calibration < .35:
            return AIResult(valid=True,validation_reason="VALID_TEST_IMAGE_QUALITY_INSUFFICIENT",kit_detected=True,test_area_detected=True,quality_score=quality,calibration_score=calibration,result=PresumptiveResult.INCONCLUSIVE,confidence=0,explanation="No presumptive result: the target-kit image passed prototype validation but is too poor for analysis; retake it with better focus, framing, and lighting. This is not definitive drug identification.",model_version=self.model_version)
        result = self.chemical_model.predict(x)[0]
        return AIResult(valid=True,validation_reason="VALID_TEST_IMAGE",kit_detected=True,test_area_detected=True,quality_score=quality,calibration_score=calibration,result=PresumptiveResult(result),confidence=round(float(self.chemical_model.predict_proba(x).max()),3),explanation="Presumptive result only; not definitive drug identification. Confidence is an uncalibrated model probability, not a scientific probability of drug identity.",model_version=self.model_version)

def load_service(demo_mode: bool = False, demo_profile: str = "INCONCLUSIVE") -> AIServiceInterface:
    if demo_mode:
        from app.ai.demo import DemoAIService
        return DemoAIService(demo_profile)
    if ARTIFACT.exists(): return BaselineAIService()
    from app.ai.stub import AIServiceStub
    return AIServiceStub()
