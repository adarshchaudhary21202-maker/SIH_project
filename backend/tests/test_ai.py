"""AI boundary tests use mock classifiers; they do not create chemical ground truth."""
from io import BytesIO
from pathlib import Path
import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from app.ai.baseline import BaselineAIService
from app.ai.demo import DemoAIService, FIXTURE_MARKERS
from app.ai.interface import PresumptiveResult
from app.main import app
REQUIRED_FIELDS = {"valid", "validation_reason", "kit_detected", "test_area_detected", "quality_score", "calibration_score", "result", "confidence", "explanation", "model_version"}
INVALID_VALIDATION_LABELS = ["shirt", "wall", "tree", "random_object", "screenshot", "empty", "wrong_kit", "blurred", "bad_framing"]
class FixedModel:
    def __init__(self, label): self.label = label
    def predict(self, _): return np.array([self.label])
    def predict_proba(self, _): return np.array([[0.05, 0.95]])
class ForbiddenChemicalModel(FixedModel):
    def predict(self, _): raise AssertionError("chemical classifier must not be called after validation rejection")
def image_bytes():
    image = Image.new("RGB", (600, 600), (120, 120, 120)); draw = ImageDraw.Draw(image)
    draw.rectangle((80, 80, 520, 520), fill=(230, 230, 230), outline=(20, 20, 20), width=20); draw.rectangle((220, 220, 380, 380), fill=(170, 70, 40))
    output = BytesIO(); image.save(output, "PNG"); return output.getvalue()
def service(tmp_path: Path, validation_label="valid_test", chemical_label="PRESUMPTIVE_POSITIVE"):
    artifact = tmp_path / "baseline.joblib"; joblib.dump({"validation_model": FixedModel(validation_label), "chemical_model": FixedModel(chemical_label), "metadata": {"model_version": "test-v1"}}, artifact); return BaselineAIService(artifact)
def assert_safe(result):
    payload = result.model_dump(); assert REQUIRED_FIELDS <= payload.keys(); assert payload["result"] in {item.value for item in PresumptiveResult}; assert "not definitive drug identification" in payload["explanation"].lower(); assert payload["model_version"]
def test_invalid_bytes_are_inconclusive(tmp_path):
    result = service(tmp_path).analyze_image(b"not-an-image")
    assert result.validation_reason == "INVALID_TEST_IMAGE" and result.result == PresumptiveResult.INCONCLUSIVE; assert_safe(result)
@pytest.mark.parametrize("label", INVALID_VALIDATION_LABELS)
def test_invalid_validation_classes_never_reach_chemical_classifier(tmp_path, label):
    result = service(tmp_path, label).analyze_image(image_bytes())
    assert not result.valid and result.validation_reason == "INVALID_TEST_IMAGE" and result.result == PresumptiveResult.INCONCLUSIVE and not result.kit_detected and not result.test_area_detected; assert_safe(result)
def test_validation_rejection_does_not_call_chemical_classifier(tmp_path):
    artifact = tmp_path / "baseline.joblib"; joblib.dump({"validation_model": FixedModel("shirt"), "chemical_model": ForbiddenChemicalModel("PRESUMPTIVE_POSITIVE"), "metadata": {"model_version": "test-v1"}}, artifact)
    result = BaselineAIService(artifact).analyze_image(image_bytes())
    assert result.result == PresumptiveResult.INCONCLUSIVE
@pytest.mark.parametrize("label", ["PRESUMPTIVE_POSITIVE", "PRESUMPTIVE_NEGATIVE", "INCONCLUSIVE"])
def test_valid_test_restricts_chemical_output_to_contract(tmp_path, label):
    result = service(tmp_path, "valid_test", label).analyze_image(image_bytes())
    assert result.valid and result.result.value == label and result.kit_detected and result.test_area_detected; assert_safe(result)
def test_api_rejects_non_image_upload_with_415():
    assert TestClient(app).post("/ai/analyze", files={"image": ("notes.txt", b"hello", "text/plain")}).status_code == 415
    assert TestClient(app).post("/ai/analyze", files={"image": ("shape.svg", b"<svg/>", "image/svg+xml")}).status_code == 415
def test_api_invalid_image_returns_complete_safe_contract():
    response = TestClient(app).post("/ai/analyze", files={"image": ("bad.jpg", b"not-image", "image/jpeg")})
    assert response.status_code == 200; body = response.json(); assert REQUIRED_FIELDS <= body.keys(); assert body["result"] == "INCONCLUSIVE"; assert "not definitive drug identification" in body["explanation"].lower()
def demo_fixture(label="valid_test"):
    image = Image.new("RGB", (640, 480), (140, 140, 140)); draw = ImageDraw.Draw(image)
    draw.rectangle((130, 60, 510, 430), fill=(235, 235, 225), outline=(20, 20, 20), width=12); draw.rectangle((240, 150, 400, 340), fill=(180, 90, 50))
    draw.rectangle((0, 0, 4, 4), fill=next(marker for marker, name in FIXTURE_MARKERS.items() if name == label)); output = BytesIO(); image.save(output, "PNG"); return output.getvalue()
def test_demo_mode_is_visible_deterministic_and_has_no_model_confidence():
    result = DemoAIService("PRESUMPTIVE_NEGATIVE").analyze_image(demo_fixture())
    assert result.valid and result.result == PresumptiveResult.PRESUMPTIVE_NEGATIVE and result.confidence == 0 and result.model_version == "prototype-demo-0.1.0"; assert_safe(result)
def test_demo_validation_rejection_skips_demo_chemical_state():
    result = DemoAIService("PRESUMPTIVE_POSITIVE").analyze_image(demo_fixture("shirt"))
    assert not result.valid and result.result == PresumptiveResult.INCONCLUSIVE and "chemical classification was skipped" in result.explanation; assert_safe(result)
def test_health_explicitly_reports_demo_mode():
    body = TestClient(app).get("/health").json(); assert body["mode"] in {"DEMO", "CONTROLLED_DATA_OR_FALLBACK"} and body["ai_model_version"]
