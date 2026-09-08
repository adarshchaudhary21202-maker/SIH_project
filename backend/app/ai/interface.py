"""Stable, deliberately non-diagnostic interface for image analysis."""
from abc import ABC, abstractmethod
from enum import Enum
from pydantic import BaseModel, Field

class PresumptiveResult(str, Enum):
    PRESUMPTIVE_POSITIVE = "PRESUMPTIVE_POSITIVE"
    PRESUMPTIVE_NEGATIVE = "PRESUMPTIVE_NEGATIVE"
    INCONCLUSIVE = "INCONCLUSIVE"

class AIResult(BaseModel):
    """Image-analysis output. This is never a definitive drug identification."""
    valid: bool
    validation_reason: str
    kit_detected: bool
    test_area_detected: bool
    quality_score: float = Field(ge=0.0, le=1.0)
    calibration_score: float = Field(ge=0.0, le=1.0)
    result: PresumptiveResult
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    model_version: str

class AIServiceInterface(ABC):
    """
    Abstract Interface for AI Service. This defines the standard contract
    for image quality evaluation, colorimetry calibration, and presumptive test analysis.
    """

    @abstractmethod
    def analyze_image(self, image_bytes: bytes) -> AIResult:
        """Return a structured, presumptive analysis of one image."""
        raise NotImplementedError

