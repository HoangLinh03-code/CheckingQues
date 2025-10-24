import vertexai, os
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from dotenv import load_dotenv
import json
from google.oauth2 import service_account
import sys
from pathlib import Path
EMBEDDED_CREDS = ""  

if not EMBEDDED_CREDS:
    # Chạy local: ưu tiên file .env
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        print(f"✅ Loaded local .env from {env_path}")
    else:
        print("⚠️ Không tìm thấy .env, sẽ thử dùng biến môi trường hệ thống")

def get_credentials():
    """Load Google Cloud credentials"""
    try:
        if EMBEDDED_CREDS:
            service_account_data = json.loads(EMBEDDED_CREDS)
            project_id = service_account_data.get("project_id")
        service_account_data = {
            "type": os.getenv("TYPE"),
            "project_id": os.getenv("PROJECT_ID"),
            "private_key_id": os.getenv("PRIVATE_KEY_ID"),
            "private_key": os.getenv("PRIVATE_KEY").replace('\\n', '\n'),
            "client_email": os.getenv("CLIENT_EMAIL"),
            "client_id": os.getenv("CLIENT_ID", ""),
            "auth_uri": os.getenv("AUTH_URI"),
            "token_uri": os.getenv("TOKEN_URI"),
            "auth_provider_x509_cert_url": os.getenv("AUTH_PROVIDER_X509_CERT_URL"),
            "client_x509_cert_url": os.getenv("CLIENT_X509_CERT_URL"),
            "universe_domain": os.getenv("UNIVERSE_DOMAIN")
        }
        
        credentials = service_account.Credentials.from_service_account_info(
            service_account_data,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        project_id = os.getenv('PROJECT_ID')
        
        return credentials, project_id
    except Exception as e:
        raise Exception(f"Không thể load credentials: {str(e)}")

class VertexClient:
    def __init__(self, project_id, creds, model, region="us-central1"):
        vertexai.init(
            project=project_id,
            location=region,
            credentials=creds
        )
        self.model = GenerativeModel(model)

    def send_data_to_AI(self, prompt, file_paths=None, temperature=0.5, top_p=0.8):
        parts = []
        
        if file_paths:
            for file_path in file_paths:
                with open(file_path, "rb") as f:
                    pdf_bytes = f.read()
                parts.append(
                    Part.from_data(data=pdf_bytes, mime_type="application/pdf")
                )
            print("Load xong pdf\n")
        
        parts.append(Part.from_text(prompt))
        
        generation_config = GenerationConfig(
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=8192,  # THÃŠM DÃ’NG NÃ€Y
            candidate_count=1
        )
        
        response = self.model.generate_content(
            parts, generation_config=generation_config
        )
        return response.text
        
    def send_data_to_check(self, prompt, temperature=0.5, top_p=0.8):
        parts = []
        # ThÃƒÂªm prompt dÃ¡ÂºÂ¡ng text
        parts.append(Part.from_text(prompt))

        # Config sinh nÃ¡Â»â„¢i dung
        generation_config = GenerationConfig(
            temperature=temperature,
            top_p=top_p
        )

        response = self.model.generate_content(
            parts, generation_config=generation_config
        )
        return response.text



