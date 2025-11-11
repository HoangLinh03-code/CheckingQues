# api/callApi.py
# -*- coding: utf-8 -*-
"""
Enhanced API Client với:
- Vertex AI (Gemini)
- Google Cloud Vision API (OCR) - FULL SUPPORT
- Hỗ trợ local dev + production build
"""

import os
import sys
import json
import base64
import io
from typing import Optional, Tuple, List, Dict
from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from dotenv import load_dotenv

# Vision API
try:
    from google.cloud import vision
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False
    print("[WARNING] google-cloud-vision chưa cài đặt. Chạy: pip install google-cloud-vision")

# Image processing
try:
    from PIL import Image, ImageEnhance, ImageFilter
    import numpy as np
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[WARNING] Pillow/numpy chưa cài đặt cho image processing nâng cao")

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("[WARNING] opencv-python chưa cài đặt cho adaptive threshold")

# --- Credentials nhúng cho build ---
EMBEDDED_CREDS = ""

if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(__file__)
 
dotenv_path = os.path.join(base_path, '.env')
load_dotenv(dotenv_path)


def _safe_get_env(key, required=True):
    """Lấy biến môi trường an toàn"""
    val = os.getenv(key)
    if required and (val is None or val == ""):
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return val


def _normalize_private_key(pk_raw):
    """Chuyển đổi escape sequence \\n thành newline thật"""
    if pk_raw is None:
        return None
    if "\\n" in pk_raw:
        return pk_raw.replace("\\n", "\n")
    return pk_raw


def _validate_service_account_dict(d):
    """Validate service account dictionary"""
    required_keys = ["type", "project_id", "private_key", "client_email"]
    missing = [k for k in required_keys if not d.get(k)]
    if missing:
        raise EnvironmentError(f"Service account JSON thiếu trường: {missing}")


def get_credentials() -> Tuple[service_account.Credentials, str]:
    """
    Load Google Cloud credentials
    
    Returns:
        Tuple[Credentials, project_id]
    
    Raises:
        Exception: Nếu không thể load credentials
    """
    try:
        # 1) Ưu tiên EMBEDDED_CREDS (cho production build)
        if EMBEDDED_CREDS and EMBEDDED_CREDS.strip():
            try:
                service_account_data = json.loads(EMBEDDED_CREDS)
            except Exception as e:
                raise EnvironmentError(f"EMBEDDED_CREDS không hợp lệ: {e}")

            if "private_key" in service_account_data:
                service_account_data["private_key"] = _normalize_private_key(
                    service_account_data["private_key"]
                )

            _validate_service_account_dict(service_account_data)
            project_id = service_account_data.get("project_id")
        
        else:
            # 2) Fallback: Đọc từ .env (local dev)
            private_key_raw = os.getenv("PRIVATE_KEY")
            private_key = _normalize_private_key(private_key_raw)

            service_account_data = {
                "type": _safe_get_env("TYPE"),
                "project_id": _safe_get_env("PROJECT_ID"),
                "private_key_id": os.getenv("PRIVATE_KEY_ID", ""),
                "private_key": private_key,
                "client_email": _safe_get_env("CLIENT_EMAIL"),
                "client_id": os.getenv("CLIENT_ID", ""),
                "auth_uri": os.getenv("AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
                "token_uri": os.getenv("TOKEN_URI", "https://oauth2.googleapis.com/token"),
                "auth_provider_x509_cert_url": os.getenv("AUTH_PROVIDER_X509_CERT_URL", ""),
                "client_x509_cert_url": os.getenv("CLIENT_X509_CERT_URL", ""),
                "universe_domain": os.getenv("UNIVERSE_DOMAIN", "googleapis.com")
            }

            _validate_service_account_dict(service_account_data)
            project_id = service_account_data.get("project_id")

        # Tạo credentials với đầy đủ scopes
        credentials = service_account.Credentials.from_service_account_info(
            service_account_data,
            scopes=[
                "https://www.googleapis.com/auth/cloud-platform",
                "https://www.googleapis.com/auth/cloud-vision"
            ]
        )

        return credentials, project_id

    except Exception as e:
        raise Exception(f"Không thể load credentials: {e}")


# ==================== VISION API CLIENT ====================
class VisionAPIClient:
    """
    Google Cloud Vision API client - FULL FEATURES
    Hỗ trợ: text_detection, document_text_detection, image preprocessing
    """
    
    def __init__(self, credentials: service_account.Credentials):
        """
        Khởi tạo Vision API client
        
        Args:
            credentials: Service Account credentials
        """
        if not VISION_AVAILABLE:
            self.client = None
            print("[VisionAPI] ⚠️ Vision API không khả dụng (chưa cài đặt)")
            return
        
        try:
            self.client = vision.ImageAnnotatorClient(credentials=credentials)
            print("[VisionAPI] ✓ Đã khởi tạo Vision API client")
        except Exception as e:
            self.client = None
            print(f"[VisionAPI] ✗ Lỗi khởi tạo: {e}")
    
    def is_available(self) -> bool:
        """Kiểm tra Vision API có khả dụng không"""
        return self.client is not None
    
    def text_detection(self, image_bytes: bytes) -> str:
        """
        OCR text detection (cơ bản) - tốt cho text thông thường
        
        Args:
            image_bytes: Raw image bytes
        
        Returns:
            str: Extracted text
        """
        if not self.client:
            print("[VisionAPI] Client không khả dụng")
            return ""
        
        try:
            vision_image = vision.Image(content=image_bytes)
            response = self.client.text_detection(image=vision_image)
            
            if response.error.message:
                print(f"[VisionAPI] Lỗi API: {response.error.message}")
                return ""
            
            texts = response.text_annotations
            if texts:
                text = texts[0].description.strip()
                print(f"[VisionAPI] ✓ Text Detection: '{text[:100]}'...")
                return text
            else:
                print("[VisionAPI] Không phát hiện text")
                return ""
        
        except Exception as e:
            print(f"[VisionAPI] Lỗi text_detection: {str(e)}")
            return ""
    
    def document_text_detection(self, image_bytes: bytes) -> str:
        """
        OCR document text detection - TỐT HƠN cho công thức toán, văn bản có cấu trúc
        
        Args:
            image_bytes: Raw image bytes
        
        Returns:
            str: Extracted text with better structure
        """
        if not self.client:
            print("[VisionAPI] Client không khả dụng")
            return ""
        
        try:
            vision_image = vision.Image(content=image_bytes)
            
            # SỬ DỤNG DOCUMENT_TEXT_DETECTION
            response = self.client.document_text_detection(image=vision_image)
            
            if response.error.message:
                print(f"[VisionAPI] Lỗi API: {response.error.message}")
                return ""
            
            # Lấy full text annotation
            if response.full_text_annotation:
                text = response.full_text_annotation.text.strip()
                print(f"[VisionAPI] ✓ Document Detection: '{text[:100]}'...")
                return text
            else:
                print("[VisionAPI] Không phát hiện text")
                return ""
        
        except Exception as e:
            print(f"[VisionAPI] Lỗi document_text_detection: {str(e)}")
            return ""
    
    def extract_text(self, image_bytes: bytes, use_document_mode: bool = True) -> str:
        """
        OCR text từ image bytes (wrapper method)
        
        Args:
            image_bytes: Raw image bytes
            use_document_mode: True = document_text_detection (tốt cho công thức)
                              False = text_detection (tốt cho text thông thường)
        
        Returns:
            str: Extracted text
        """
        if use_document_mode:
            return self.document_text_detection(image_bytes)
        else:
            return self.text_detection(image_bytes)
    
    def extract_text_from_base64(self, base64_str: str, 
                                 use_document_mode: bool = True,
                                 preprocess: bool = False,
                                 scale_factor: int = 4) -> str:
        """
        OCR text từ base64 string
        
        Args:
            base64_str: Base64 encoded image
            use_document_mode: Document mode (tốt hơn cho công thức)
            preprocess: Có tiền xử lý ảnh không
            scale_factor: Hệ số scale nếu preprocess=True
        
        Returns:
            str: Extracted text
        """
        try:
            if preprocess:
                image_bytes = self.preprocess_image_for_ocr(base64_str, scale_factor)
            else:
                image_bytes = base64.b64decode(base64_str)
            
            return self.extract_text(image_bytes, use_document_mode)
            
        except Exception as e:
            print(f"[VisionAPI] Lỗi extract_text_from_base64: {e}")
            return ""
    
    def preprocess_image_for_ocr(self, base64_str: str, scale_factor: int = 4) -> bytes:
        """
        Tiền xử lý ảnh để tăng độ chính xác OCR
        ĐỒNG BỘ với logic trong AICheck.py
        
        Args:
            base64_str: Base64 encoded image
            scale_factor: Hệ số scale (2-4 recommended)
        
        Returns:
            bytes: Processed image bytes
        """
        if not PIL_AVAILABLE:
            print("[VisionAPI] PIL không khả dụng, trả về ảnh gốc")
            return base64.b64decode(base64_str)
        
        try:
            img_bytes = base64.b64decode(base64_str)
            img = Image.open(io.BytesIO(img_bytes))
            original_size = img.size
            
            # Xử lý alpha channel
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                alpha = img.split()[3]
                background.paste(img, mask=alpha)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Grayscale
            img = img.convert('L')
            
            # Scale lên
            new_size = (original_size[0] * scale_factor, original_size[1] * scale_factor)
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Tăng contrast và sharpness
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.5)
            
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(2.5)
            
            # Unsharp mask
            img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
            
            # Padding
            padding = 30
            padded_img = Image.new('L', 
                                   (img.width + 2*padding, img.height + 2*padding), 
                                   255)
            padded_img.paste(img, (padding, padding))
            img = padded_img
            
            # Convert to bytes
            output_buffer = io.BytesIO()
            img.save(output_buffer, format='PNG', quality=100, optimize=False)
            output_buffer.seek(0)
            
            print(f"[VisionAPI] ✓ Preprocessed: {original_size} -> {new_size} ({scale_factor}x)")
            return output_buffer.read()
            
        except Exception as e:
            print(f"[VisionAPI] Lỗi preprocess: {e}")
            return base64.b64decode(base64_str)
    
    def preprocess_wmf_emf_ultra_quality(self, base64_str: str) -> bytes:
        """
        Tiền xử lý CHUYÊN BIỆT cho WMF/EMF - giữ dấu phẩy/trừ/mũ
        ĐỒNG BỘ 100% với AICheck.py
        
        Args:
            base64_str: Base64 encoded WMF/EMF image
        
        Returns:
            bytes: Processed PNG bytes
        """
        if not PIL_AVAILABLE:
            print("[VisionAPI] PIL không khả dụng")
            return base64.b64decode(base64_str)
        
        try:
            img_bytes = base64.b64decode(base64_str)
            img = Image.open(io.BytesIO(img_bytes))
            original_size = img.size
            
            # Scale CỰC LỚN (24x)
            scale_factor = 24
            new_size = (original_size[0] * scale_factor, original_size[1] * scale_factor)
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Xử lý Alpha
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                alpha = img.split()[3]
                background.paste(img, mask=alpha)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Grayscale
            img = img.convert('L')
            
            # Gaussian Blur nhẹ
            img = img.filter(ImageFilter.GaussianBlur(radius=0.3))
            
            # ADAPTIVE THRESHOLD (quan trọng nhất)
            if CV2_AVAILABLE:
                img_array = np.array(img)
                
                # Adaptive Threshold
                img_array = cv2.adaptiveThreshold(
                    img_array, 255, 
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                    cv2.THRESH_BINARY, 
                    blockSize=7,
                    C=2
                )
                
                # Morphology: đóng khoảng trống
                kernel_close = np.ones((2, 2), np.uint8)
                img_array = cv2.morphologyEx(img_array, cv2.MORPH_CLOSE, kernel_close)
                
                # Dilate nhẹ
                kernel_dilate = np.ones((1, 1), np.uint8)
                img_array = cv2.dilate(img_array, kernel_dilate, iterations=1)
                
                img = Image.fromarray(img_array)
                print(f"[VisionAPI] ✓ Adaptive Threshold (CV2)")
                
            else:
                # Fallback: Binary threshold
                img_array = np.array(img)
                threshold = 110
                img_array = np.where(img_array < threshold, 0, 255).astype(np.uint8)
                img = Image.fromarray(img_array)
                print(f"[VisionAPI] Binary Threshold (fallback)")
            
            # Tăng Contrast + Sharpness
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(3.0)
            
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(3.0)
            
            # Unsharp Mask
            img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=200, threshold=2))
            
            # Padding lớn
            padding = 50
            new_width = img.width + 2 * padding
            new_height = img.height + 2 * padding
            padded_img = Image.new('L', (new_width, new_height), 255)
            padded_img.paste(img, (padding, padding))
            img = padded_img
            
            # Lưu PNG chất lượng MAX
            output_buffer = io.BytesIO()
            img.save(output_buffer, format='PNG', quality=100, optimize=False, compress_level=0)
            output_buffer.seek(0)
            
            print(f"[VisionAPI] ✓ WMF/EMF -> PNG: {original_size} -> {new_size} (24x ultra)")
            return output_buffer.read()
            
        except Exception as e:
            print(f"[VisionAPI] Lỗi preprocess WMF/EMF: {e}")
            import traceback
            traceback.print_exc()
            return base64.b64decode(base64_str)


# ==================== VERTEX AI CLIENT ====================
class VertexClient:
    """
    Vertex AI client cho Gemini models
    """
    
    def __init__(self, project_id: str, creds: service_account.Credentials, 
                 model: str, region: str = "us-central1"):
        """
        Khởi tạo Vertex AI client
        
        Args:
            project_id: Google Cloud Project ID
            creds: Service Account Credentials
            model: Tên model (vd: "gemini-2.5-pro")
            region: Vùng deploy (mặc định: us-central1)
        """
        vertexai.init(
            project=project_id,
            location=region,
            credentials=creds
        )
        self.model = GenerativeModel(model)
        print(f"[VertexAI] ✓ Đã khởi tạo model: {model}")

    def send_data_to_AI(self, prompt: str, file_paths: Optional[List[str]] = None, 
                       temperature: float = 0.5, top_p: float = 0.8) -> str:
        """
        Gửi prompt + PDF files lên AI
        
        Args:
            prompt: Text prompt
            file_paths: List đường dẫn file PDF
            temperature: Độ sáng tạo (0.0 - 1.0)
            top_p: Nucleus sampling (0.0 - 1.0)
        
        Returns:
            str: Response text từ AI
        """
        parts = []
        
        if file_paths:
            for file_path in file_paths:
                with open(file_path, "rb") as f:
                    pdf_bytes = f.read()
                parts.append(Part.from_data(data=pdf_bytes, mime_type="application/pdf"))

        parts.append(Part.from_text(prompt))

        generation_config = GenerationConfig(
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=8192,
            candidate_count=1
        )

        response = self.model.generate_content(parts, generation_config=generation_config)
        return response.text

    def send_data_to_check(self, prompt: str, temperature: float = 0.5, 
                          top_p: float = 0.8) -> str:
        """
        Gửi chỉ text lên AI (không có ảnh)
        
        Args:
            prompt: Text prompt
            temperature: Độ sáng tạo
            top_p: Nucleus sampling
        
        Returns:
            str: Response text từ AI
        """
        parts = [Part.from_text(prompt)]
        generation_config = GenerationConfig(
            temperature=temperature, 
            top_p=top_p,
            max_output_tokens=8192
        )
        response = self.model.generate_content(parts, generation_config=generation_config)
        return response.text
    
    def send_multimodal_to_check(self, prompt: str, 
                                images_base64: Optional[List[Dict]] = None, 
                                temperature: float = 0.3, 
                                top_p: float = 0.8) -> str:
        """
        Gửi cả text + hình ảnh (multimodal) lên AI
        
        Args:
            prompt: Text prompt
            images_base64: List of dict - [{'base64': '...', 'mime_type': 'image/png'}, ...]
            temperature: Độ sáng tạo (0.0 - 1.0, thấp = chính xác hơn)
            top_p: Nucleus sampling (0.0 - 1.0)
        
        Returns:
            str: Response text từ AI
        """
        print(f"[VertexAI] Temperature: {temperature} (thấp = chính xác)")
        parts = []
        
        # === THÊM HÌNH ẢNH TRƯỚC (nếu có) ===
        if images_base64:
            print(f"[VertexAI] Đang thêm {len(images_base64)} ảnh vào request...")
            
            for idx, img_data in enumerate(images_base64, 1):
                try:
                    base64_str = img_data.get('base64', '')
                    if not base64_str:
                        print(f"[VertexAI] ⚠️ Ảnh {idx}: Base64 rỗng, bỏ qua")
                        continue
                    
                    # Decode base64 → bytes
                    img_bytes = base64.b64decode(base64_str)
                    
                    # MIME type
                    mime_type = img_data.get('mime_type', 'image/png')
                    
                    # Tạo Part từ image bytes
                    parts.append(Part.from_data(data=img_bytes, mime_type=mime_type))
                    
                    print(f"[VertexAI] ✓ Ảnh {idx}: {mime_type} ({len(img_bytes):,} bytes)")
                    
                except Exception as e:
                    print(f"[VertexAI] ✗ Lỗi thêm ảnh {idx}: {str(e)}")
                    continue
        
        # === THÊM TEXT PROMPT CUỐI CÙNG ===
        parts.append(Part.from_text(prompt))
        
        # === GỬI REQUEST ===
        generation_config = GenerationConfig(
            temperature=temperature, 
            top_p=top_p,
            max_output_tokens=8192,
            candidate_count=1
        )
        
        print(f"[VertexAI] Đang gửi request lên AI...")
        response = self.model.generate_content(parts, generation_config=generation_config)
        print(f"[VertexAI] ✓ Nhận được response từ AI")
        
        return response.text


# ==================== UNIFIED CLIENT ====================
class GoogleCloudClient:
    """
    Unified client cho cả Vertex AI và Vision API
    Quản lý tập trung, dễ sử dụng
    """
    
    def __init__(self, model_name: str = "gemini-2.5-pro", region: str = "us-central1"):
        """
        Khởi tạo cả Vertex AI và Vision API client
        
        Args:
            model_name: Gemini model name
            region: Vertex AI region
        """
        # Load credentials
        self.credentials, self.project_id = get_credentials()
        
        # Khởi tạo Vertex AI
        self.vertex_client = VertexClient(
            project_id=self.project_id,
            creds=self.credentials,
            model=model_name,
            region=region
        )
        
        # Khởi tạo Vision API
        self.vision_client = VisionAPIClient(self.credentials)
        
        print(f"[GoogleCloud] ✓ Đã khởi tạo: Vertex AI + Vision API")
    
    def get_vertex_client(self) -> VertexClient:
        """Lấy Vertex AI client"""
        return self.vertex_client
    
    def get_vision_client(self) -> VisionAPIClient:
        """Lấy Vision API client"""
        return self.vision_client
    
    def is_vision_available(self) -> bool:
        """Kiểm tra Vision API có khả dụng không"""
        return self.vision_client.is_available()
