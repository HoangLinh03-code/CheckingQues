# api/callApi.py
import os
import sys
import json
import base64
from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from dotenv import load_dotenv

# --- Nếu build trên GitHub Action, dòng này sẽ bị injected bằng JSON credential ---
# Ví dụ khi inject: EMBEDDED_CREDS = """{"type":"service_account", "project_id":"my-proj", ...}"""
EMBEDDED_CREDS = ""

if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(__file__)
 
dotenv_path = os.path.join(base_path, '.env')
load_dotenv(dotenv_path)

def _safe_get_env(key, required=True):
    """Lấy biến môi trường an toàn. Nếu required True và không tồn tại -> raise error rõ ràng."""
    val = os.getenv(key)
    if required and (val is None or val == ""):
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return val


def _normalize_private_key(pk_raw):
    """Bảo vệ việc gọi replace trên None và chuyển các escape '\\n' thành newline thật."""
    if pk_raw is None:
        return None
    # Nếu key đã là multiline (ví dụ khi chạy local), trả về nguyên bản
    if "\\n" in pk_raw:
        return pk_raw.replace("\\n", "\n")
    return pk_raw


def _validate_service_account_dict(d):
    """Đảm bảo service account dict có các trường cần thiết."""
    required_keys = ["type", "project_id", "private_key", "client_email"]
    missing = [k for k in required_keys if not d.get(k)]
    if missing:
        raise EnvironmentError(f"Service account JSON thiếu trường: {missing}")


def get_credentials():
    """
    Load Google Cloud credentials.
    - Nếu EMBEDDED_CREDS khác rỗng -> dùng JSON nhúng (dùng cho .exe build).
    - Ngược lại -> đọc từ các biến môi trường / .env (dùng local).
    Trả về: (google.oauth2.service_account.Credentials, project_id)
    """
    try:
        # 1) Nếu có credential nhúng -> parse JSON
        if EMBEDDED_CREDS and EMBEDDED_CREDS.strip():
            try:
                service_account_data = json.loads(EMBEDDED_CREDS)
            except Exception as e:
                raise EnvironmentError(f"EMBEDDED_CREDS không hợp lệ: {e}")

            # Normalize private_key nếu cần
            if "private_key" in service_account_data:
                service_account_data["private_key"] = _normalize_private_key(service_account_data["private_key"])

            _validate_service_account_dict(service_account_data)
            project_id = service_account_data.get("project_id")
        else:
            # 2) Fallback: đọc từ environment / .env
            # Lấy private_key raw (cẩn trọng: có thể là multiline hoặc escaped)
            private_key_raw = os.getenv("PRIVATE_KEY")
            private_key = _normalize_private_key(private_key_raw)

            # Thu thập các giá trị (required = True đối với các trường quan trọng)
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

        # Tạo credentials object
        credentials = service_account.Credentials.from_service_account_info(
            service_account_data,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

        return credentials, project_id

    except Exception as e:
        # Bóc lỗi, trả về message rõ ràng cho caller
        raise Exception(f"Không thể load credentials: {e}")


# ==================== VERTEX CLIENT CLASS ====================
class VertexClient:
    def __init__(self, project_id, creds, model, region="us-central1"):
        """
        Khởi tạo Vertex AI client
        
        Args:
            project_id: Google Cloud Project ID
            creds: Service Account Credentials
            model: Tên model (vd: "gemini-2.5-pro", "gemini-1.5-pro")
            region: Vùng deploy (mặc định: us-central1)
        """
        vertexai.init(
            project=project_id,
            location=region,
            credentials=creds
        )
        self.model = GenerativeModel(model)
        print(f"[VertexClient] ✓ Đã khởi tạo model: {model}")

    def send_data_to_AI(self, prompt, file_paths=None, temperature=0.5, top_p=0.8):
        """
        Gửi prompt + PDF files lên AI (dùng cho xử lý PDF)
        
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

    def send_data_to_check(self, prompt, temperature=0.5, top_p=0.8):
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
    
    def send_multimodal_to_check(self, prompt, images_base64=None, temperature=0.3, top_p=0.8):
        """
        Gửi cả text + hình ảnh (multimodal) lên AI
        
        Args:
            prompt: Text prompt
            images_base64: List of dict - [{'base64': '...', 'mime_type': 'image/png'}, ...]
            temperature: Độ sáng tạo (0.0 - 1.0)
            top_p: Nucleus sampling (0.0 - 1.0)
        
        Returns:
            str: Response text từ AI
        """
        print(f"[VertexAI] Temperature: {temperature} (thấp = chính xác)")
        parts = []
        
        # === THÊM HÌNH ẢNH TRƯỚC (nếu có) ===
        if images_base64:
            print(f"[VertexClient] Đang thêm {len(images_base64)} ảnh vào request...")
            
            for idx, img_data in enumerate(images_base64):
                try:
                    # 1. Lấy base64 string
                    base64_str = img_data.get('base64', '')
                    if not base64_str:
                        print(f"[VertexClient] ⚠️ Ảnh {idx+1}: Base64 rỗng, bỏ qua")
                        continue
                    
                    # 2. Decode base64 string → bytes
                    img_bytes = base64.b64decode(base64_str)
                    
                    # 3. Xác định MIME type
                    mime_type = img_data.get('mime_type', 'image/png')
                    
                    # 4. Tạo Part từ image bytes
                    parts.append(Part.from_data(data=img_bytes, mime_type=mime_type))
                    
                    print(f"[VertexClient] ✓ Ảnh {idx+1}: {mime_type} ({len(img_bytes)} bytes)")
                    
                except Exception as e:
                    print(f"[VertexClient] ✗ Lỗi thêm ảnh {idx+1}: {str(e)}")
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
        
        print(f"[VertexClient] Đang gửi request lên AI...")
        response = self.model.generate_content(parts, generation_config=generation_config)
        print(f"[VertexClient] ✓ Nhận được response từ AI")
        
        return response.text