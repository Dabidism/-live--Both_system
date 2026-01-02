"""Services package"""
from .anpr_service import ANPRService
from .detection_service import DetectionService
from .ocr_service import OCRService
from .auth_service import AuthService

__all__ = ['ANPRService', 'DetectionService', 'OCRService', 'AuthService']