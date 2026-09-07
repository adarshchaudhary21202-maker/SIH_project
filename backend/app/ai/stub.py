import random
from typing import Dict, Any
from app.ai.interface import AIServiceInterface

class AIServiceStub(AIServiceInterface):
    """
    Mock implementation of AIService for local development and unit tests.
    Avoids loading real machine learning weights while satisfying system architecture.
    """

    def validate_image(self, image_bytes: bytes) -> bool:
        # Simple simulation: ensure the file has content
        return len(image_bytes) > 0

    def calculate_image_quality(self, image_bytes: bytes) -> float:
        # Simulates image clarity score based on file length or mock logic
        if len(image_bytes) == 0:
            return 0.0
        # Return a realistic score between 0.85 and 0.98
        return round(0.85 + (len(image_bytes) % 15) * 0.008, 3)

    def calibrate_image(self, image_bytes: bytes) -> float:
        # Simulates calibration checking (e.g. alignment of color card targets)
        if len(image_bytes) == 0:
            return 0.0
        return round(0.90 + (len(image_bytes) % 11) * 0.008, 3)

    def analyze_test(self, image_bytes: bytes, kit_type: str) -> Dict[str, Any]:
        if len(image_bytes) == 0:
            return {
                "result": "INVALID_IMAGE",
                "confidence": 0.0,
                "image_quality": 0.0,
                "calibration_score": 0.0,
                "detected_test_area": {},
                "validation_status": "FAILED_READ"
            }

        # Deterministic simulation based on kit_type
        kit_lower = kit_type.lower()
        if "heroin" in kit_lower:
            result = "HEROIN_POSITIVE"
            confidence = 0.942
        elif "cocaine" in kit_lower:
            result = "COCAINE_POSITIVE"
            confidence = 0.965
        elif "meth" in kit_lower or "amphetamine" in kit_lower:
            result = "AMPHETAMINE_POSITIVE"
            confidence = 0.912
        else:
            result = "NEGATIVE"
            confidence = 0.895

        return {
            "result": result,
            "confidence": confidence,
            "image_quality": self.calculate_image_quality(image_bytes),
            "calibration_score": self.calibrate_image(image_bytes),
            "detected_test_area": {
                "x_min": 142,
                "y_min": 210,
                "x_max": 384,
                "y_max": 450
            },
            "validation_status": "VALIDATED"
        }

