from abc import ABC, abstractmethod
from typing import Dict, Any, Union

class AIServiceInterface(ABC):
    """
    Abstract Interface for AI Service. This defines the standard contract
    for image quality evaluation, colorimetry calibration, and presumptive test analysis.
    """

    @abstractmethod
    def validate_image(self, image_bytes: bytes) -> bool:
        """Verify whether the image contains a valid reagent kit."""
        pass

    @abstractmethod
    def calculate_image_quality(self, image_bytes: bytes) -> float:
        """Calculate image clarity, noise, and lighting sufficiency score (0.0 to 1.0)."""
        pass

    @abstractmethod
    def calibrate_image(self, image_bytes: bytes) -> float:
        """Analyze reference control regions to calibrate illumination/exposure score (0.0 to 1.0)."""
        pass

    @abstractmethod
    def analyze_test(self, image_bytes: bytes, kit_type: str) -> Dict[str, Any]:
        """
        Analyze a colorimetric field test.
        
        Returns a dictionary containing:
        - result (str): Presumptive result (e.g. "HEROIN_POSITIVE", "NEGATIVE", "COCAINE_POSITIVE")
        - confidence (float): AI model confidence score (0.0 to 1.0)
        - image_quality (float): Measured quality (0.0 to 1.0)
        - calibration_score (float): Lighting/color calibration (0.0 to 1.0)
        - detected_test_area (Dict[str, Any]): Bounding box/coordinates
        - validation_status (str): E.g. "VALIDATED", "UNSTABLE_LIGHTING", "REAGENT_BLEED"
        """
        pass

