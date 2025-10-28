import base64
import traceback
from typing import Dict
import re

# Import thư viện Google Cloud Vertex AI
import vertexai
from vertexai.preview.generative_models import (
    GenerativeModel,
    Part,
    GenerationConfig
)
from vertexai.generative_models._generative_models import Image

# ==================== AI CHECKER V6 (Multimodal Vision) ====================
class AIQuestionChecker:
    """
    AI Checker với khả năng "nhìn" hình ảnh (Multimodal)
    Sử dụng Google Vertex AI SDK trực tiếp.
    """
    
    def __init__(self, project_id: str, creds, model_name: str = "gemini-1.5-pro"):
        try:
            # Khởi tạo Vertex AI client
            vertexai.init(project=project_id, credentials=creds)
            
            # Tải mô hình
            self.model = GenerativeModel(model_name)
            print(f"[AIChecker] Đã khởi tạo Vertex AI với model: {model_name}")
            
        except Exception as e:
            print(f"[AIChecker] Lỗi nghiêm trọng khi khởi tạo Vertex AI: {str(e)}")
            raise
    
    def _get_mime_type(self, extension: str) -> str:
        """Chuyển đổi phần mở rộng file sang MIME type"""
        ext = (extension or '').lower()
        if ext in ['.jpg', '.jpeg']:
            return 'image/jpeg'
        if ext == '.wmf':
            return 'image/wmf'
        if ext == '.emf':
            return 'image/emf'
        # Mặc định là PNG cho các trường hợp khác
        return 'image/png'

    def check_question(self, question_data: Dict, prompt_content: str) -> Dict:
        """
        Check câu hỏi (bao gồm cả text VÀ images)
        
        Returns:
            {
                'is_correct': bool,
                'evaluation': str,
                'suggestions': str,
                'knowledge': str
            }
        """
        
        # === 1. Xây dựng phần VĂN BẢN của prompt ===
        question_text_parts = "\n".join(question_data.get('question_text', []))
        
        # Thêm công thức (nếu parser đọc được MathML)
        q_eqs = question_data.get('question_equations', [])
        s_eqs = question_data.get('solution_equations', [])
        if q_eqs or s_eqs:
            question_text_parts += "\n\n📐 CÔNG THỨC (Text):\n"
            for eq in q_eqs:
                content = eq.get('content', str(eq))
                question_text_parts += f"- [Câu hỏi] {content}\n"
            for eq in s_eqs:
                content = eq.get('content', str(eq))
                question_text_parts += f"- [Lời giải] {content}\n"
        
        # Thêm lời giải (nếu có)
        if question_data.get('solution_text'):
            question_text_parts += "\n\n" + "="*50
            question_text_parts += "\n📗 LỜI GIẢI\n"
            question_text_parts += "="*50 + "\n"
            question_text_parts += "\n".join(question_data['solution_text'])
                
        # Tạo prompt text hoàn chỉnh
        full_prompt_text = self._build_optimized_prompt(prompt_content, question_text_parts)
        
        # === 2. Chuẩn bị nội dung gửi cho AI (Văn bản + Hình ảnh) ===
        content_parts = []
        
        # Thêm phần văn bản
        content_parts.append(Part.from_text(full_prompt_text))
        
        # Thêm tất cả hình ảnh (câu hỏi + lời giải, bao gồm OLE)
        all_images = question_data.get('question_images', []) + \
                     question_data.get('solution_images', [])
        
        print(f"[AIChecker] Chuẩn bị gửi {len(all_images)} hình ảnh cho AI...")
        
        for img in all_images:
            try:
                img_base64 = img.get('base64')
                if img_base64:
                    # Lấy đúng MIME type từ parser
                    mime_type = self._get_mime_type(img.get('extension'))
                    # Giải mã base64
                    image_bytes = base64.b64decode(img_base64)
                    # Tạo đối tượng Image
                    image_part = Part.from_data(data=image_bytes, mime_type=mime_type)
                    # Thêm vào danh sách
                    content_parts.append(image_part)
            except Exception as e:
                print(f"[AIChecker] ⚠️ Lỗi khi xử lý ảnh {img.get('filename')}: {e}")
                continue

        # === 3. Gọi API ===
        try:
            # Cấu hình
            generation_config = GenerationConfig(
                temperature=0.2,
                max_output_tokens=4096
            )
            
            # Gửi yêu cầu (văn bản + ảnh)
            response = self.model.generate_content(
                content_parts,
                generation_config=generation_config
            )
            
            # Lấy phần text trả về
            response_text = response.text
            
            # Parse kết quả
            result = self._parse_response(response_text)
            
            # Validate kết quả (giữ nguyên)
            if not result['evaluation']:
                result['evaluation'] = "Câu hỏi chính xác" if result['is_correct'] else "Cần kiểm tra lại"
            if not result['suggestions']:
                result['suggestions'] = "- Bước 1: Đọc kỹ đề bài và xác định yêu cầu\n- Bước 2: Áp dụng kiến thức đã học\n- Bước 3: Tính toán và chọn đáp án"
            if not result['knowledge']:
                result['knowledge'] = "Áp dụng kiến thức theo chương trình học"
            
            return result
            
        except Exception as e:
            print(f"[AIChecker] Lỗi khi gọi Gemini API: {str(e)}")
            traceback.print_exc()
            return {
                'is_correct': False,
                'evaluation': f"Lỗi AI: {str(e)}",
                'suggestions': "Không thể đánh giá",
                'knowledge': "Không có thông tin"
            }
    
    def _build_optimized_prompt(self, prompt_content: str, question_text: str) -> str:
        """
        Xây dựng prompt tối ưu.
        (Giữ nguyên logic từ file gốc, chỉ xóa ví dụ về ảnh
         vì AI giờ đã tự thấy ảnh)
        """
        return f"""{prompt_content}

---

## CÂU HỎI CẦN ĐÁNH GIÁ

(Lưu ý: Nếu có hình ảnh hoặc công thức, chúng sẽ được đính kèm. 
Hãy phân tích cả văn bản và hình ảnh.)

{question_text}

---

## YÊU CẦU OUTPUT CHÍNH XÁC

Trả về CHÍNH XÁC theo format sau (KHÔNG thêm bớt gì):
IS_CORRECT: YES/NO

EVALUATION: [Nếu YES: Chỉ viết 'Câu hỏi chính xác'] [Nếu NO: Viết ngắn gọn sai ở đâu (1-2 câu)]

SUGGESTIONS: [Gợi ý làm bài theo từng bước, MỖI BƯỚC 1 DÒNG]

Bước 1: ...

Bước 2: ...

Bước 3: ... [Tối thiểu 3 bước, tối đa 5 bước]

KNOWLEDGE: [Viết lại công thức/định lý cốt lõi - TỐI ĐA 3 DÒNG] [Chỉ ghi kiến thức CHÍNH XÁC, KHÔNG giải thích thêm]
## LƯU Ý QUAN TRỌNG

1. **ĐỌC CẢ ẢNH:** Bạn sẽ nhận được hình ảnh (nếu có). Hãy đọc kỹ văn bản/công thức trong các hình ảnh đó để tìm dữ kiện (như A, f, R1...).
2. **IS_CORRECT phải là YES hoặc NO**
3. **EVALUATION:**
   - Nếu IS_CORRECT: YES → Chỉ viết: "Câu hỏi chính xác"
   - Nếu IS_CORRECT: NO → Nêu rõ vấn đề chính

4. **KNOWLEDGE:**
   - Tối đa 3 dòng
   - Chỉ ghi công thức/định lý chính, súc tích

5. **Format:**
   - Phân cách bằng #### (4 dấu thăng)
   - Không dùng markdown code block ```

BẮT ĐẦU ĐÁNH GIÁ:"""
    
    def _parse_response(self, response: str) -> Dict:
        """
        Parse AI response - (Giữ nguyên từ file gốc)
        """
        result = {
            'is_correct': False,
            'evaluation': '',
            'suggestions': '',
            'knowledge': ''
        }
        
        # Loại bỏ markdown code block
        response = response.replace('```', '').strip()
        
        # Parse IS_CORRECT
        if 'IS_CORRECT: YES' in response or 'IS_CORRECT:YES' in response or 'IS_CORRECT : YES' in response:
            result['is_correct'] = True
        elif 'IS_CORRECT: NO' in response or 'IS_CORRECT:NO' in response or 'IS_CORRECT : NO' in response:
            result['is_correct'] = False
        
        # Parse các phần theo delimiter ####
        parts = response.split('####')
        
        for part in parts:
            part = part.strip()
            
            # EVALUATION
            if 'EVALUATION:' in part or 'EVALUATION :' in part:
                content = part.split('EVALUATION:', 1)[-1].strip()
                content = content.split('EVALUATION :', 1)[-1].strip() if 'EVALUATION :' in part else content
                content = content.split('####')[0].strip()
                content = re.sub(r'\[.*?\]', '', content).strip()
                result['evaluation'] = content
            
            # SUGGESTIONS
            elif 'SUGGESTIONS:' in part or 'SUGGESTIONS :' in part:
                content = part.split('SUGGESTIONS:', 1)[-1].strip()
                content = content.split('SUGGESTIONS :', 1)[-1].strip() if 'SUGGESTIONS :' in part else content
                content = content.split('####')[0].strip()
                content = re.sub(r'\[.*?\]', '', content).strip()
                result['suggestions'] = content
            
            # KNOWLEDGE
            elif 'KNOWLEDGE:' in part or 'KNOWLEDGE :' in part:
                content = part.split('KNOWLEDGE:', 1)[-1].strip()
                content = content.split('KNOWLEDGE :', 1)[-1].strip() if 'KNOWLEDGE :' in part else content
                content = content.split('####')[0].strip()
                content = re.sub(r'\[.*?\]', '', content).strip()
                result['knowledge'] = content
        
        # Fallback parsing (giữ nguyên)
        if not result['evaluation'] and not result['suggestions'] and not result['knowledge']:
            lines = response.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                
                if line.startswith('EVALUATION:') or line.startswith('EVALUATION :'):
                    current_section = 'evaluation'
                    content = line.split(':', 1)[-1].strip()
                    content = re.sub(r'\[.*?\]', '', content).strip()
                    if content:
                        result['evaluation'] = content
                
                elif line.startswith('SUGGESTIONS:') or line.startswith('SUGGESTIONS :'):
                    current_section = 'suggestions'
                    content = line.split(':', 1)[-1].strip()
                    content = re.sub(r'\[.*?\]', '', content).strip()
                    if content:
                        result['suggestions'] = content
                
                elif line.startswith('KNOWLEDGE:') or line.startswith('KNOWLEDGE :'):
                    current_section = 'knowledge'
                    content = line.split(':', 1)[-1].strip()
                    content = re.sub(r'\[.*?\]', '', content).strip()
                    if content:
                        result['knowledge'] = content
                
                elif current_section and line and not line.startswith('IS_CORRECT'):
                    if line.startswith('[') and line.endswith(']'):
                        continue
                    
                    if result[current_section]:
                        result[current_section] += '\n' + line
                    else:
                        result[current_section] = line
        
        return result