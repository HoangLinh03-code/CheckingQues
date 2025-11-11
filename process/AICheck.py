# -*- coding: utf-8 -*-
"""
AIQuestionChecker - REFACTORED
Sử dụng VisionAPIClient từ callApi.py thay vì tự khởi tạo
"""

from typing import Dict, List
from api.callApi import VertexClient, VisionAPIClient, GoogleCloudClient
import re
import base64
import io
from PIL import Image
import numpy as np
from PIL import ImageEnhance, ImageFilter
import os

class AIQuestionChecker:
    """
    AI Checker với Vision API + Convert WMF/EMF cực kỹ để giữ dấu
    """
    
    def __init__(self, project_id: str = None, creds = None, model_name: str = "gemini-2.5-pro"):
        """
        Khởi tạo AI Checker
        
        Args:
            project_id: Google Cloud Project ID (optional nếu dùng GoogleCloudClient)
            creds: Credentials (optional nếu dùng GoogleCloudClient)
            model_name: Gemini model name
        """
        if project_id and creds:
            # CÁCH 1: Khởi tạo riêng lẻ (tương thích ngược)
            self.client = VertexClient(project_id, creds, model_name)
            self.vision_client = VisionAPIClient(creds)
            print("[AIChecker] Khởi tạo (legacy mode)")
        else:
            # CÁCH 2: Dùng GoogleCloudClient (khuyến nghị)
            google_client = GoogleCloudClient(model_name=model_name)
            self.client = google_client.get_vertex_client()
            self.vision_client = google_client.get_vision_client()
            print("[AIChecker] Khởi tạo (unified mode)")
        
        if not self.vision_client.is_available():
            print("[AIChecker] ⚠️ Vision API không khả dụng")
    
    def _extract_text_from_image_vision(self, base64_str: str, extension: str) -> str:
        """
        OCR sử dụng Vision API từ callApi.py
        
        Args:
            base64_str: Base64 encoded image
            extension: File extension (.png, .jpg, .wmf, .emf)
        
        Returns:
            str: Extracted text
        """
        if not self.vision_client.is_available():
            print("[Vision] Vision API không khả dụng")
            return ""
        
        try:
            # Tiền xử lý ảnh NÂNG CAO (scale 4x)
            img_bytes = self.vision_client.preprocess_image_for_ocr(
                base64_str, 
                scale_factor=4
            )
            
            # Sử dụng document_text_detection (tốt cho công thức)
            full_text = self.vision_client.document_text_detection(img_bytes)
            
            if not full_text:
                print("[Vision] Không phát hiện text")
                return ""
            
            # POST-PROCESSING
            full_text = re.sub(r'\s+', ' ', full_text).strip()
            full_text = full_text.replace('|', '').replace('\\', '').replace('~', '').replace('`', '')
            
            return full_text
            
        except Exception as e:
            print(f"[Vision] Lỗi: {str(e)}")
            return ""
    
    def _convert_wmf_emf_ultra_quality(self, base64_str: str, extension: str) -> tuple:
        """
        Convert WMF/EMF sang PNG - SỬ DỤNG callApi.py
        
        Args:
            base64_str: Base64 encoded WMF/EMF
            extension: File extension (.wmf, .emf)
        
        Returns:
            tuple: (png_base64, 'image/png')
        """
        if not self.vision_client.is_available():
            print("[Convert] Vision client không khả dụng")
            return (base64_str, f'image/x-{extension[1:]}')
        
        try:
            # Sử dụng method từ VisionAPIClient
            png_bytes = self.vision_client.preprocess_wmf_emf_ultra_quality(base64_str)
            
            # Convert bytes -> base64
            png_base64 = base64.b64encode(png_bytes).decode('utf-8')
            
            print(f"[Convert] {extension} -> PNG (24x ultra quality)")
            return (png_base64, 'image/png')
            
        except Exception as e:
            print(f"[Convert] Lỗi convert {extension}: {str(e)}")
            import traceback
            traceback.print_exc()
            return (base64_str, f'image/x-{extension[1:]}')
    
    def check_question(self, question_data: Dict, prompt_content: str, 
        context_text: str = "") -> Dict:
        """
        Check câu hỏi - Convert WMF/EMF với chất lượng cực cao
        
        Args:
            question_data: Dict chứa question_text, question_images, solution_images, etc.
            prompt_content: System prompt
            context_text: Context bổ sung (optional)
        
        Returns:
            Dict: {is_correct, evaluation, fix_suggestion, suggestions, knowledge}
        """
        question_text = "\n".join(question_data.get('question_text', []))
        
        if context_text:
            question_text = context_text + "\n\n" + question_text 
        
        # Phân loại ảnh
        q_images = question_data.get('question_images', [])
        s_images = question_data.get('solution_images', [])
        
        wmf_emf_count = 0
        png_jpg_count = 0
        
        for img in q_images + s_images:
            ext = img.get('extension', '.png').lower()
            if ext in ['.wmf', '.emf']:
                wmf_emf_count += 1
            else:
                png_jpg_count += 1
        
        q_count = len(q_images)
        s_count = len(s_images)
        
        if q_count > 0 or s_count > 0:
            question_text += f"\n\n{'='*70}"
            question_text += f"\n[CẢNH BÁO HÌNH ẢNH] ({q_count} ảnh câu hỏi, {s_count} ảnh lời giải)"
            question_text += f"\n{'='*70}"
            question_text += f"\n[THỐNG KÊ]: WMF/EMF (công thức): {wmf_emf_count} | PNG/JPG: {png_jpg_count}"
            question_text += "\n"
            
            if wmf_emf_count > 0:
                question_text += "\n[XỬ LÝ WMF/EMF]:"
                question_text += f"\n- Đã convert {wmf_emf_count} công thức WMF/EMF sang PNG"
                question_text += "\n- Scale 24x + Adaptive Threshold (giữ dấu phẩy/trừ/mũ)"
                question_text += "\n- Chất lượng: Cực cao (100%, không nén)"
                question_text += "\n- OCR: Sử dụng Vision API (document mode)"
                question_text += "\n"
            
            question_text += "\n[VẤN ĐỀ CẦN LƯU Ý]:"
            question_text += "\n1. DẤU PHẨY THẬP PHÂN (,)"
            question_text += "\n   - '2,8' có thể đọc nhầm '28' nếu mất dấu phẩy"
            question_text += "\n   - Kiểm tra: 28 m² quá lớn -> nên là 2,8 m²"
            question_text += "\n"
            question_text += "\n2. DẤU TRỪ ÂM (-) TRƯỚC PHÂN SỐ"
            question_text += "\n   - '+ -1/3' có thể mất dấu trừ thành '+ 1/3'"
            question_text += "\n   - Rất khó phát hiện vì dấu trừ nhỏ"
            question_text += "\n"
            question_text += "\n3. DẤU MŨ / CHỈ SỐ"
            question_text += "\n   - 'x²' khác 'x2' (lũy thừa vs nhân 2)"
            question_text += "\n   - 'H₂O' khác 'H2O'"
            question_text += "\n"
            question_text += "\n[CÁCH KIỂM TRA]:"
            question_text += "\n1. XEM HÌNH ẢNH (đã xử lý chất lượng cao)"
            question_text += "\n2. ĐỌC OCR TEXT (tham khảo, có thể sai)"
            question_text += "\n3. KIỂM TRA LOGIC: Kết quả có hợp lý không?"
            question_text += f"\n{'='*70}\n"
            
            # OCR TEXT - Sử dụng Vision API
            ocr_texts = []
            
            if self.vision_client.is_available():
                for idx, img in enumerate(q_images, 1):
                    ext = img.get('extension', '.png')
                    base64_data = img.get('base64', '')
                    
                    # Nếu là WMF/EMF, convert trước khi OCR
                    if ext.lower() in ['.wmf', '.emf']:
                        print(f"[Vision] Convert {ext} trước khi OCR...")
                        base64_data, _ = self._convert_wmf_emf_ultra_quality(base64_data, ext)
                        ext = '.png'
                    
                    ocr_text = self._extract_text_from_image_vision(base64_data, ext)
                    if ocr_text:
                        ocr_texts.append(f"[Ảnh câu hỏi #{idx} - Vision OCR]: {ocr_text}")
                
                for idx, img in enumerate(s_images, 1):
                    ext = img.get('extension', '.png')
                    base64_data = img.get('base64', '')
                    
                    if ext.lower() in ['.wmf', '.emf']:
                        print(f"[Vision] Convert {ext} trước khi OCR...")
                        base64_data, _ = self._convert_wmf_emf_ultra_quality(base64_data, ext)
                        ext = '.png'
                    
                    ocr_text = self._extract_text_from_image_vision(base64_data, ext)
                    if ocr_text:
                        ocr_texts.append(f"[Ảnh lời giải #{idx} - Vision OCR]: {ocr_text}")
            
            if ocr_texts:
                question_text += "\n\n[TEXT TỪ VISION OCR - THAM KHẢO]:\n"
                question_text += "\n".join(ocr_texts)
                question_text += "\n\n[LƯU Ý]: OCR có thể vẫn sai về dấu nhỏ"
                question_text += "\n[ƯU TIÊN]: Xem hình ảnh đã xử lý (gửi kèm theo)"
        
        # Thêm công thức MathML
        q_eqs = question_data.get('question_equations', [])
        s_eqs = question_data.get('solution_equations', [])
        if q_eqs or s_eqs:
            question_text += "\n\nCÔNG THỨC (MathML):\n"
            for eq in q_eqs:
                content = eq.get('content', str(eq))
                question_text += f"- [Câu hỏi] {content}\n"
            for eq in s_eqs:
                content = eq.get('content', str(eq))
                question_text += f"- [Lời giải] {content}\n"
        
        # Thêm lời giải
        if question_data.get('solution_text'):
            question_text += "\n\n" + "="*50
            question_text += "\nLỜI GIẢI\n"
            question_text += "="*50 + "\n"
            question_text += "\n".join(question_data['solution_text'])
                
        # Tạo prompt
        full_prompt = self._build_optimized_prompt(prompt_content, question_text)
        
        try:
            # Chuẩn bị hình ảnh (CONVERT WMF/EMF)
            images_to_send = self._prepare_images_for_ai(question_data)
            
            # Gửi AI
            if images_to_send:
                print(f"[AIChecker] Gửi {len(images_to_send)} ảnh lên Gemini Vision...")
                response = self.client.send_multimodal_to_check(
                    prompt=full_prompt,
                    images_base64=images_to_send,
                    temperature=0.05
                )
            else:
                print(f"[AIChecker] Không có ảnh, chỉ gửi text...")
                response = self.client.send_data_to_check(
                    prompt=full_prompt,
                    temperature=0.05
                )
            
            result = self._parse_response(response)
            
            # Validate
            if not result['evaluation']:
                result['evaluation'] = "Câu hỏi chính xác" if result['is_correct'] else "Cần kiểm tra lại"
            if not result['suggestions']:
                result['suggestions'] = "- Bước 1: Đọc kỹ đề bài\n- Bước 2: Áp dụng kiến thức\n- Bước 3: Tính toán và chọn đáp án"
            if not result['knowledge']:
                result['knowledge'] = "Áp dụng kiến thức theo chương trình học."
            
            return result
            
        except Exception as e:
            print(f"[AIChecker] Lỗi: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'is_correct': False,
                'evaluation': f"Lỗi AI: {str(e)}",
                'fix_suggestion': "Không thể đánh giá",
                'suggestions': "Không thể đánh giá",
                'knowledge': "Không có thông tin"
            }
    
    def _build_optimized_prompt(self, prompt_content: str, question_text: str) -> str:
        """Xây dựng prompt"""
        return f"""{prompt_content}

---

## LƯU Ý KHI ĐỌC HÌNH ẢNH ĐÃ XỬ LÝ

**QUAN TRỌNG**: Các hình ảnh WMF/EMF (công thức) đã được convert sang PNG 
với chất lượng CỰC CAO (scale 24x, adaptive threshold) để giữ dấu phẩy/trừ/mũ.

**VẤN ĐỀ CÓ THỂ GẶP**:

1. **Dấu phẩy thập phân (,)** - Đã xử lý nhưng vẫn có thể sai
   - "2,8" có thể đọc nhầm "28"
   - Kiểm tra logic: 28 m² quá lớn -> nên là 2,8 m²

2. **Dấu trừ âm (-)** - Rất khó phát hiện
   - "1/2 + -1/3" có thể mất dấu trừ
   - Xem kỹ trước phân số

3. **Dấu mũ / chỉ số**
   - x² khác x2 (lũy thừa vs nhân)
   - H₂O khác H2O (chỉ số vs số thường)

---

## CÂU HỎI CẦN ĐÁNH GIÁ

{question_text}

---

## YÊU CẦU OUTPUT

Trả về CHÍNH XÁC theo format sau:
```
IS_CORRECT: YES/NO
####
EVALUATION:
[Nếu YES: 'Câu hỏi chính xác']
[Nếu NO: Viết ngắn gọn sai ở đâu]
####
FIX_SUGGESTION:
[CHỈ KHI NO - Cách sửa cụ thể]
####
SUGGESTIONS:
- Bước 1: ...
- Bước 2: ...
- Bước 3: ...
####
KNOWLEDGE:
[7-10 dòng kiến thức]
```

BẮT ĐẦU ĐÁNH GIÁ:"""
    
    def _prepare_images_for_ai(self, question_data: Dict) -> List[Dict]:
        """
        Chuẩn bị ảnh - CONVERT WMF/EMF sang PNG chất lượng cao
        """
        images_to_send = []
        
        mime_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
        }
        
        need_convert = ['.wmf', '.emf']
        
        # Lấy ảnh từ câu hỏi
        q_images = question_data.get('question_images', [])
        for img in q_images:
            try:
                base64_str = img.get('base64', '')
                extension = img.get('extension', '.png').lower()
                
                if not base64_str:
                    continue
                
                # CONVERT WMF/EMF
                if extension in need_convert:
                    print(f"[AIChecker] Convert {extension} -> PNG (ultra quality)...")
                    base64_str, mime_type = self._convert_wmf_emf_ultra_quality(base64_str, extension)
                    
                    if base64_str is None:
                        print(f"[AIChecker] Bỏ qua ảnh (convert thất bại)")
                        continue
                else:
                    mime_type = mime_map.get(extension, 'image/png')
                
                images_to_send.append({
                    'base64': base64_str,
                    'mime_type': mime_type
                })
                
            except Exception as e:
                print(f"[AIChecker] Lỗi chuẩn bị ảnh câu hỏi: {str(e)}")
                continue
        
        # Lấy ảnh từ lời giải
        s_images = question_data.get('solution_images', [])
        for img in s_images:
            try:
                base64_str = img.get('base64', '')
                extension = img.get('extension', '.png').lower()
                
                if not base64_str:
                    continue
                
                if extension in need_convert:
                    print(f"[AIChecker] Convert {extension} -> PNG (ultra quality)...")
                    base64_str, mime_type = self._convert_wmf_emf_ultra_quality(base64_str, extension)
                    
                    if base64_str is None:
                        print(f"[AIChecker] Bỏ qua ảnh (convert thất bại)")
                        continue
                else:
                    mime_type = mime_map.get(extension, 'image/png')
                
                images_to_send.append({
                    'base64': base64_str,
                    'mime_type': mime_type
                })
                
            except Exception as e:
                print(f"[AIChecker] Lỗi chuẩn bị ảnh lời giải: {str(e)}")
                continue
        
        return images_to_send
    
    def _parse_response(self, response: str) -> Dict:
        """Parse AI response"""
        result = {
            'is_correct': False,
            'evaluation': '',
            'fix_suggestion': '',
            'suggestions': '',
            'knowledge': ''
        }
        
        response = response.replace('```', '').strip()
        
        if 'IS_CORRECT: YES' in response or 'IS_CORRECT:YES' in response:
            result['is_correct'] = True
        elif 'IS_CORRECT: NO' in response or 'IS_CORRECT:NO' in response:
            result['is_correct'] = False
        
        parts = response.split('####')
        
        for part in parts:
            part = part.strip()
            
            if 'EVALUATION:' in part:
                content = part.split('EVALUATION:', 1)[-1].strip()
                content = content.split('####')[0].strip()
                content = re.sub(r'\[.*?\]', '', content).strip()
                result['evaluation'] = content
            
            elif 'FIX_SUGGESTION:' in part:
                content = part.split('FIX_SUGGESTION:', 1)[-1].strip()
                content = content.split('####')[0].strip()
                content = re.sub(r'\[.*?\]', '', content).strip()
                content = re.sub(r'(\s+)\*(\s+)', r'\1+\2', content)
                content = content.replace('**', '')
                result['fix_suggestion'] = content
            
            elif 'SUGGESTIONS:' in part:
                content = part.split('SUGGESTIONS:', 1)[-1].strip()
                content = content.split('####')[0].strip()
                content = re.sub(r'\[.*?\]', '', content).strip()
                content = content.replace('**', '')
                result['suggestions'] = content
            
            elif 'KNOWLEDGE:' in part:
                content = part.split('KNOWLEDGE:', 1)[-1].strip()
                content = content.split('####')[0].strip()
                lines = content.split('\n')
                filtered_lines = [line for line in lines 
                                 if not (line.strip().startswith('[') and line.strip().endswith(']'))]
                content = '\n'.join(filtered_lines).strip()
                content = content.replace('**', '')
                result['knowledge'] = content
        
        return result