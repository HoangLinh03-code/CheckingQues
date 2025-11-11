# -*- coding: utf-8 -*-
from typing import Dict, List
from api.callApi import VertexClient
import re
import base64
import io
from PIL import Image
import numpy as np
from PIL import ImageEnhance, ImageFilter
import pytesseract
import platform
import os

# # ============== CẤU HÌNH TESSERACT (THÊM ĐOẠN NÀY) ==============
# def configure_tesseract():
#     """Tự động cấu hình Tesseract path"""
#     system = platform.system()
    
#     if system == 'Windows':
#         # Các đường dẫn thường gặp trên Windows
#         possible_paths = [
#             r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe',
#             r'C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe',
#             r'C:\\Tesseract-OCR\\tesseract.exe',
#             os.path.expanduser(r'~\AppData\\Local\\Programs\\Tesseract-OCR\\tesseract.exe'),
#         ]
        
#         for path in possible_paths:
#             if os.path.exists(path):
#                 pytesseract.pytesseract.tesseract_cmd = path
#                 print(f"[Tesseract] ✓ Đã cấu hình: {path}")
#                 return True
        
#         print("[Tesseract] ✗ KHÔNG tìm thấy Tesseract!")
#         print("[Tesseract] Vui lòng cài đặt từ: https://github.com/UB-Mannheim/tesseract/wiki")
#         return False
    
#     elif system == 'Darwin':  # macOS
#         # Homebrew thường cài tại /usr/local/bin hoặc /opt/homebrew/bin
#         possible_paths = [
#             '/usr/local/bin/tesseract',
#             '/opt/homebrew/bin/tesseract',
#         ]
        
#         for path in possible_paths:
#             if os.path.exists(path):
#                 pytesseract.pytesseract.tesseract_cmd = path
#                 print(f"[Tesseract] ✓ Đã cấu hình: {path}")
#                 return True
    
#     elif system == 'Linux':
#         # Linux thường có sẵn trong PATH
#         # Không cần cấu hình gì thêm
#         print(f"[Tesseract] Linux - sử dụng PATH mặc định")
#         return True
    
#     return True

# # Chạy cấu hình khi import module
# configure_tesseract()
class AIQuestionChecker:
    """
    AI Checker với prompt tối ưu và KNOWLEDGE mở rộng (7-10 dòng)
    + Thêm FIX_SUGGESTION
    + GỬI HÌNH ẢNH LÊN AI (Multimodal)
    + Convert WMF/EMF → PNG (Gemini không hỗ trợ WMF/EMF)
    """
    
    def __init__(self, project_id: str, creds, model_name: str = "gemini-2.5-pro"):
        self.client = VertexClient(project_id, creds, model_name)
    
    def _extract_text_from_image(self, base64_str: str) -> str:
        """
        OCR CẢI TIẾN V2 - Phát hiện dấu phẩy (,) và dấu trừ âm (-)
        """
        try:
            img_bytes = base64.b64decode(base64_str)
            img = Image.open(io.BytesIO(img_bytes))
            
            # === BƯỚC 1: Grayscale ===
            if img.mode != 'L':
                img = img.convert('L')
            
            # === BƯỚC 2: Scale CỰC LỚN (20x) ===
            scale_factor = 20  # Tăng từ 16x lên 20x
            original_size = img.size
            new_size = (original_size[0] * scale_factor, original_size[1] * scale_factor)
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            print(f"[OCR] Scale {original_size} → {new_size} (20x)")
            
            # === BƯỚC 3: Tăng Contrast CỰC MẠNH (cho dấu phẩy/trừ) ===
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(3.5)  # Tăng từ 2.5 lên 3.5
            
            # === BƯỚC 4: Adaptive Threshold ===
            try:
                import cv2
                img_array = np.array(img)
                
                # Adaptive Threshold với blockSize nhỏ hơn (phát hiện chi tiết nhỏ)
                img_array = cv2.adaptiveThreshold(
                    img_array, 255, 
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                    cv2.THRESH_BINARY, 
                    blockSize=9,  # Giảm từ 11 xuống 9
                    C=2
                )
                
                # Morphology: Đóng khoảng trống nhỏ
                kernel_small = np.ones((1, 1), np.uint8)  # Kernel nhỏ hơn
                img_array = cv2.morphologyEx(img_array, cv2.MORPH_CLOSE, kernel_small)
                
                # Làm dày nét chữ nhẹ
                kernel_dilate = np.ones((1, 1), np.uint8)
                img_array = cv2.dilate(img_array, kernel_dilate, iterations=1)
                
                img = Image.fromarray(img_array)
                print(f"[OCR] Đã áp dụng Adaptive Threshold + Morphology")
                
            except ImportError:
                # Fallback: Binary threshold
                img_array = np.array(img)
                threshold = 120  # Giảm threshold để giữ chi tiết
                img_array = np.where(img_array < threshold, 0, 255).astype(np.uint8)
                img = Image.fromarray(img_array)
                print(f"[OCR] OpenCV không có, dùng Binary threshold")
            
            # === BƯỚC 5: Tăng Sharpness ===
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(3.0)  # Tăng từ 2.5 lên 3.0
            
            # === BƯỚC 6: Thêm Padding ===
            padding = 40  # Tăng từ 30 lên 40
            new_width = img.width + 2 * padding
            new_height = img.height + 2 * padding
            padded_img = Image.new('L', (new_width, new_height), 255)
            padded_img.paste(img, (padding, padding))
            img = padded_img
            
            # === BƯỚC 7: OCR với NHIỀU CONFIG (CẢI TIẾN) ===
            
            # Config 1: Tập trung số học + dấu (THÊM DẤU PHẨY VÀ TRỪ)
            config_1 = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.,-+×÷=()[]{}/ '
            
            # Config 2: Cho phép chữ cái
            config_2 = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.,-+×÷=()[]{}abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ/ '
            
            # Config 3: Tự do hoàn toàn
            config_3 = r'--oem 3 --psm 6'
            
            # Config 4: Single line (tốt cho công thức ngắn)
            config_4 = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789.,-+×÷=()[]{}/ '
            
            # Config 5: MỚI - Tập trung dấu phẩy/trừ với PSM 13 (raw line)
            config_5 = r'--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789.,-+×÷=()[]{}/ '
            
            results = []
            for idx, config in enumerate([config_1, config_2, config_3, config_4, config_5], 1):
                try:
                    text = pytesseract.image_to_string(img, lang='eng', config=config)
                    text = text.strip()
                    if text:
                        results.append(text)
                        print(f"[OCR] Config {idx}: '{text[:60]}'")
                except Exception as e:
                    print(f"[OCR] Config {idx} lỗi: {e}")
                    continue
            
            # Chọn kết quả dài nhất
            if results:
                text = max(results, key=len)
            else:
                text = ""
            
            # === BƯỚC 8: POST-PROCESSING CẢI TIẾN ===
            
            # Loại bỏ ký tự lạ
            text = text.replace('|', '').replace('\\', '').replace('~', '').replace('`', '')
            
            # Chuẩn hóa khoảng trắng
            text = re.sub(r'\s+', ' ', text).strip()
            
            # === SỬA LỖI OCR THƯỜNG GẶP ===
            
            # 1. "O" (chữ O) → "0" (số 0)
            text = re.sub(r'\b([0-9])O([0-9])\b', r'\1 0 \2', text)
            text = re.sub(r'\bO\b', '0', text)
            
            # 2. "l" (chữ l) → "1" (số 1)
            text = re.sub(r'\b([0-9])l([0-9])\b', r'\1 1 \2', text)
            
            # 3. Sửa "x" thành "×" nếu ở giữa 2 số
            text = re.sub(r'(\d)\s*x\s*(\d)', r'\1 × \2', text)
            
            # === MỚI: XỬ LÝ DẤU PHẨY VÀ DẤU TRỪ ===
            
            # 4. Phát hiện số bị thiếu dấu phẩy
            # VD: "28" có thể là "2,8" nếu context là diện tích/thể tích nhỏ
            # (Logic này sẽ được AI xử lý, nhưng ta cảnh báo)
            
            # 5. Bảo vệ dấu trừ âm trước phân số
            # VD: "+ -1/3" KHÔNG được sửa thành "+ 1/3"
            # Giữ nguyên pattern: [+×÷] -[số]/[số]
            # (Không sửa gì, chỉ log cảnh báo)
            
            # 6. Phát hiện pattern nghi ngờ thiếu dấu phẩy
            suspicious_patterns = []
            
            # Pattern: Số 2-3 chữ số không có dấu phẩy/chấm
            matches = re.findall(r'\b(\d{2,3})\b', text)
            for match in matches:
                if ',' not in match and '.' not in match:
                    suspicious_patterns.append(match)
            
            if suspicious_patterns:
                print(f"[OCR] ⚠️ Phát hiện số nghi ngờ thiếu dấu phẩy: {suspicious_patterns}")
            
            # 7. Phát hiện pattern nghi ngờ thiếu dấu trừ
            # VD: "1/2 + 1/3" có thể là "1/2 + -1/3"
            if re.search(r'[+×÷]\s*\d+/\d+', text):
                print(f"[OCR] ⚠️ Phát hiện phân số sau toán tử - kiểm tra dấu trừ âm")
            
            print(f"[OCR] Kết quả cuối: '{text}'")
            
            return text
            
        except Exception as e:
            print(f"[OCR] Lỗi: {str(e)}")
            return ""
    def check_question(self, question_data: Dict, prompt_content: str, 
        context_text: str = "") -> Dict:
        """
        Check câu hỏi - CHIẾN LƯỢC MỚI với cảnh báo về dấu phẩy và dấu trừ
        """
        # Tạo prompt với format cải tiến
        question_text = "\n".join(question_data.get('question_text', []))
        
        if context_text:
            question_text = context_text + "\n\n" + question_text 
        
        # === PHẦN 1: CẢNH BÁO VỀ DẤU PHẨY VÀ DẤU TRỪ (CẢI TIẾN) ===
        q_images = question_data.get('question_images', [])
        s_images = question_data.get('solution_images', [])
        q_count = len(q_images)
        s_count = len(s_images)
        
        if q_count > 0 or s_count > 0:
            question_text += f"\n\n{'='*70}"
            question_text += f"\n⚠️ CẢNH BÁO - HÌNH ẢNH ({q_count} ảnh câu hỏi, {s_count} ảnh lời giải)"
            question_text += f"\n{'='*70}"
            question_text += "\n🔴 ƯU TIÊN CAO NHẤT: XEM KỸ HÌNH ẢNH (đã zoom 20x)"
            question_text += "\n"
            question_text += "\n📌 VẤN ĐỀ 1: DẤU PHẨY THẬP PHÂN (,)"
            question_text += "\n- OCR thường BỎ QUA hoặc NHẦM dấu phẩy vì quá nhỏ"
            question_text += "\n- VD: '2,8' bị đọc thành '28' | '1,6' thành '16'"
            question_text += "\n- KIỂM TRA: Nếu thấy số 'lớn bất thường' → có thể thiếu dấu phẩy"
            question_text += "\n- NGHI NGỜ: Diện tích 28 m² (quá lớn) → có thể là 2,8 m²"
            question_text += "\n"
            question_text += "\n📌 VẤN ĐỀ 2: DẤU TRỪ ÂM (-) TRƯỚC PHÂN SỐ"
            question_text += "\n- OCR thường BỎ QUA dấu trừ âm khi đứng trước phân số"
            question_text += "\n- VD: '1/2 + -1/3' bị đọc thành '1/2 + 1/3'"
            question_text += "\n- VD: '2/3 × -5/7' bị đọc thành '2/3 × 5/7'"
            question_text += "\n- KIỂM TRA: Xem KỸ trong ảnh có dấu '-' nhỏ trước phân số không"
            question_text += "\n"
            question_text += "\n🔍 CÁCH KIỂM TRA:"
            question_text += "\n1. XEM ẢNH GỐC (ưu tiên số 1)"
            question_text += "\n2. Tìm dấu phẩy/chấm/trừ NHỎ giữa các số"
            question_text += "\n3. Kiểm tra logic: Kết quả có hợp lý không?"
            question_text += "\n4. So sánh: Tính toán trong ảnh vs kết luận cuối"
            question_text += f"\n{'='*70}\n"
            
            # === PHẦN 2: OCR TEXT (CHỈ LÀM THAM KHẢO) ===
            ocr_texts = []
            for idx, img in enumerate(q_images, 1):
                ocr_text = self._extract_text_from_image(img.get('base64', ''))
                if ocr_text:
                    ocr_texts.append(f"[Ảnh #{idx} - OCR]: {ocr_text}")
            
            for idx, img in enumerate(s_images, 1):
                ocr_text = self._extract_text_from_image(img.get('base64', ''))
                if ocr_text:
                    ocr_texts.append(f"[Lời giải #{idx} - OCR]: {ocr_text}")
            
            if ocr_texts:
                question_text += "\n\n📝 TEXT TỪ OCR (CHỈ THAM KHẢO - CÓ THỂ SAI):\n"
                question_text += "\n".join(ocr_texts)
                question_text += "\n⚠️ LƯU Ý: OCR có thể sai về:"
                question_text += "\n  - Dấu phẩy thập phân (,) → bị bỏ qua"
                question_text += "\n  - Dấu trừ âm (-) trước phân số → bị bỏ qua"
                question_text += "\n  - Dấu nhân (×) → nhầm 'x'"
                question_text += "\n❗ ƯU TIÊN XEM HÌNH ẢNH GỐC!"
        
        # Thêm công thức (giữ nguyên)
        q_eqs = question_data.get('question_equations', [])
        s_eqs = question_data.get('solution_equations', [])
        if q_eqs or s_eqs:
            question_text += "\n\nCÔNG THỨC:\n"
            for eq in q_eqs:
                content = eq.get('content', str(eq))
                question_text += f"- [Câu hỏi] {content}\n"
            for eq in s_eqs:
                content = eq.get('content', str(eq))
                question_text += f"- [Lời giải] {content}\n"
        
        # Thêm lời giải (giữ nguyên)
        if question_data.get('solution_text'):
            question_text += "\n\n" + "="*50
            question_text += "\nLỜI GIẢI\n"
            question_text += "="*50 + "\n"
            question_text += "\n".join(question_data['solution_text'])
                
        # Tạo prompt với format mới
        full_prompt = self._build_optimized_prompt(prompt_content, question_text)
        
        try:
            # === Chuẩn bị hình ảnh để gửi ===
            images_to_send = self._prepare_images_for_ai(question_data)
            
            # === GỬI MULTIMODAL (Text + Images) ===
            if images_to_send:
                print(f"[AIChecker] Gửi {len(images_to_send)} ảnh lên AI...")
                print(f"[AIChecker] ⚠️ ĐÃ CẢNH BÁO về dấu phẩy và dấu trừ")
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
            
            # Validate kết quả (giữ nguyên)
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
        """
        Xây dựng prompt tối ưu với hướng dẫn đọc số
        """
        return f"""{prompt_content}

    ---

    ## LƯU Ý QUAN TRỌNG KHI ĐỌC HÌNH ẢNH CÔNG THỨC

    1. **Dấu phẩy/chấm thập phân**:
    - Trong tiếng Việt: 2,2 (dùng dấu phẩy)
    - Nếu thấy "22" trong công thức S = ... hoặc V = ..., hãy cân nhắc có thể là "2,2"
    - Nếu thấy "1118", có thể là "11,18" hoặc "1.118" (nghìn)
    
    2. **Ngữ cảnh toán học**:
    - Diện tích/Thể tích thường là số thập phân (VD: 2,2 m²)
    - Số lượng đếm là số nguyên (VD: 22 học sinh)
    - Số đo lớn có dấu chấm ngăn cách (VD: 1.118 km)

    3. **Cách xác định**:
    - Xem đơn vị (m², m³, cm² → thường là số thập phân)
    - Xem context (1/2 × 4,4 → kết quả nên là 2,2 chứ không phải 22)
    - Kiểm tra logic phép tính

    ---

    ## CÂU HỎI CẦN ĐÁNH GIÁ

    {question_text}

    ---

    ## YÊU CẦU OUTPUT CHÍNH XÁC

    Trả về CHÍNH XÁC theo format sau (KHÔNG thêm bớt gì):
    ```
    IS_CORRECT: YES/NO
    ####
    EVALUATION:
    [Nếu YES: Chỉ viết 'Câu hỏi chính xác']
    [Nếu NO: Viết ngắn gọn sai ở đâu (1-2 câu)]
    ####
    FIX_SUGGESTION:
    [CHỈ KHI IS_CORRECT: NO]
    [Kiến thức cần sửa, cách sửa cụ thể, ví dụ minh họa]
    ####
    SUGGESTIONS:
    [Gợi ý làm bài theo từng bước, MỖI BƯỚC 1 DÒNG]
    - Bước 1: ...
    - Bước 2: ...
    - Bước 3: ...
    [Tối thiểu 3 bước, tối đa 5 bước]
    ####
    KNOWLEDGE:
    [KIẾN THỨC MỞ RỘNG - 7 ĐẾN 10 DÒNG]
    [Dòng 1-2: Công thức/định lý chính ĐÃ DÙNG trong đề]
    [Dòng 3-4: Giải thích ý nghĩa các ký hiệu, đơn vị]
    [Dòng 5-6: Công thức liên quan hoặc điều kiện áp dụng]
    [Dòng 7-8: Lưu ý quan trọng, trường hợp đặc biệt]
    [Dòng 9-10: (Tùy chọn) Mở rộng kiến thức, ứng dụng]
    ```

    BẮT ĐẦU ĐÁNH GIÁ:"""
    
    def _convert_wmf_emf_to_png(self, base64_str: str, extension: str) -> tuple:
        """
        Convert WMF/EMF sang PNG - CHẤT LƯỢNG CỰC CAO
        + Scale 16x (tăng từ 8x)
        + Adaptive Threshold thay vì Binary
        + Morphology để giữ dấu phẩy/chấm
        """
        try:
            img_bytes = base64.b64decode(base64_str)
            
            try:
                from PIL import ImageEnhance, ImageFilter, ImageOps
                
                img = Image.open(io.BytesIO(img_bytes))
                original_size = img.size
                
                # === BƯỚC 1: SCALE CỰC LỚN (16x) ===
                scale_factor = 16
                new_size = (original_size[0] * scale_factor, original_size[1] * scale_factor)
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                print(f"[Convert] Scaled {original_size} → {new_size} (16x)")
                
                # === BƯỚC 2: Xử lý Alpha Channel ===
                if img.mode == 'RGBA':
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    alpha = img.split()[3]
                    background.paste(img, mask=alpha)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # === BƯỚC 3: Chuyển Grayscale ===
                img = img.convert('L')
                
                # === BƯỚC 4: Gaussian Blur nhẹ (giảm noise) ===
                img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
                
                # === BƯỚC 5: ADAPTIVE THRESHOLD (Tốt hơn Binary) ===
                try:
                    import cv2
                    img_array = np.array(img)
                    
                    # Adaptive Gaussian Threshold
                    img_array = cv2.adaptiveThreshold(
                        img_array, 255,
                        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                        cv2.THRESH_BINARY,
                        blockSize=15,  # Kích thước vùng (lớn hơn cho ảnh lớn)
                        C=2
                    )
                    
                    # Morphology: CLOSE - Đóng khoảng trống nhỏ (dấu phẩy bị vỡ)
                    kernel_close = np.ones((2, 2), np.uint8)
                    img_array = cv2.morphologyEx(img_array, cv2.MORPH_CLOSE, kernel_close)
                    
                    # Morphology: DILATE nhẹ - Làm dày nét chữ
                    kernel_dilate = np.ones((2, 2), np.uint8)
                    img_array = cv2.dilate(img_array, kernel_dilate, iterations=1)
                    
                    img = Image.fromarray(img_array)
                    print(f"[Convert] Adaptive Threshold + Morphology")
                    
                except ImportError:
                    # Fallback: Binary threshold
                    img_array = np.array(img)
                    threshold = 128
                    img_array = np.where(img_array < threshold, 0, 255).astype(np.uint8)
                    img = Image.fromarray(img_array)
                    print(f"[Convert] Binary Threshold (fallback)")
                
                # === BƯỚC 6: Tăng Contrast + Sharpness ===
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(2.5)
                
                enhancer = ImageEnhance.Sharpness(img)
                img = enhancer.enhance(2.5)
                
                # === BƯỚC 7: Thêm Padding ===
                padding = 30
                new_width = img.width + 2 * padding
                new_height = img.height + 2 * padding
                
                padded_img = Image.new('L', (new_width, new_height), 255)
                padded_img.paste(img, (padding, padding))
                img = padded_img
                
                # === BƯỚC 8: Lưu PNG chất lượng cao ===
                output_buffer = io.BytesIO()
                img.save(output_buffer, format='PNG', optimize=False, compress_level=0)
                output_buffer.seek(0)
                
                png_base64 = base64.b64encode(output_buffer.read()).decode('utf-8')
                
                print(f"[Convert] ✓ {extension} → PNG (16x, Adaptive Threshold)")
                
                return (png_base64, 'image/png')
                
            except Exception as e:
                print(f"[Convert] ✗ Lỗi convert {extension}: {str(e)}")
                import traceback
                traceback.print_exc()
                return (base64_str, f'image/x-{extension[1:]}')
        
        except Exception as e:
            print(f"[Convert] ✗ Lỗi decode base64: {str(e)}")
            return (None, None)
    
    def _prepare_images_for_ai(self, question_data: Dict) -> List[Dict]:
        """
        Chuẩn bị danh sách ảnh để gửi lên AI
        - Convert WMF/EMF → PNG
        - Giữ nguyên PNG/JPEG/GIF
        
        Returns:
            List[Dict]: [{'base64': '...', 'mime_type': 'image/png'}, ...]
        """
        images_to_send = []
        
        # MIME type mapping
        mime_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
        }
        
        # Các định dạng cần convert
        need_convert = ['.wmf', '.emf']
        
        # Lấy ảnh từ câu hỏi
        q_images = question_data.get('question_images', [])
        for img in q_images:
            try:
                base64_str = img.get('base64', '')
                extension = img.get('extension', '.png').lower()
                
                if not base64_str:
                    continue
                
                # Nếu là WMF/EMF → Convert sang PNG
                if extension in need_convert:
                    print(f"[AIChecker] Phát hiện {extension}, đang convert...")
                    base64_str, mime_type = self._convert_wmf_emf_to_png(base64_str, extension)
                    
                    if base64_str is None:
                        print(f"[AIChecker] ✗ Bỏ qua ảnh (convert thất bại)")
                        continue
                else:
                    # Giữ nguyên định dạng gốc
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
                
                # Nếu là WMF/EMF → Convert sang PNG
                if extension in need_convert:
                    print(f"[AIChecker] Phát hiện {extension}, đang convert...")
                    base64_str, mime_type = self._convert_wmf_emf_to_png(base64_str, extension)
                    
                    if base64_str is None:
                        print(f"[AIChecker] ✗ Bỏ qua ảnh (convert thất bại)")
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
        """Parse AI response - xử lý cả format sai"""
        result = {
            'is_correct': False,
            'evaluation': '',
            'fix_suggestion': '',
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
            
            # FIX_SUGGESTION
            elif 'FIX_SUGGESTION:' in part or 'FIX_SUGGESTION :' in part:
                content = part.split('FIX_SUGGESTION:', 1)[-1].strip()
                content = content.split('FIX_SUGGESTION :', 1)[-1].strip() if 'FIX_SUGGESTION :' in part else content
                content = content.split('####')[0].strip()
                content = re.sub(r'\[.*?\]', '', content).strip()
                
                # === START FIX (P5) ===
                # Thay thế (khoảng trắng)* (khoảng trắng) bằng (khoảng trắng)+ (khoảng trắng)
                content = re.sub(r'(\s+)\*(\s+)', r'\1+\2', content)
                content = content.replace('**', '') # Xóa bold
                # === END FIX (P5) ===

                result['fix_suggestion'] = content
            
            # SUGGESTIONS
            elif 'SUGGESTIONS:' in part or 'SUGGESTIONS :' in part:
                content = part.split('SUGGESTIONS:', 1)[-1].strip()
                content = content.split('SUGGESTIONS :', 1)[-1].strip() if 'SUGGESTIONS :' in part else content
                content = content.split('####')[0].strip()
                content = re.sub(r'\[.*?\]', '', content).strip()
                
                # === START FIX (P5) ===
                content = content.replace('**', '') # Xóa bold
                # === END FIX (P5) ===
                
                result['suggestions'] = content
            
            # KNOWLEDGE
            elif 'KNOWLEDGE:' in part or 'KNOWLEDGE :' in part:
                content = part.split('KNOWLEDGE:', 1)[-1].strip()
                content = content.split('KNOWLEDGE :', 1)[-1].strip() if 'KNOWLEDGE :' in part else content
                content = content.split('####')[0].strip()
                lines = content.split('\n')
                filtered_lines = []
                for line in lines:
                    if not (line.strip().startswith('[') and line.strip().endswith(']')):
                        filtered_lines.append(line)
                content = '\n'.join(filtered_lines).strip()

                # === START FIX (P5) ===
                content = content.replace('**', '') # Xóa bold
                # === END FIX (P5) ===

                result['knowledge'] = content
        
        # Fallback parsing nếu không có ####
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
                
                elif line.startswith('FIX_SUGGESTION:') or line.startswith('FIX_SUGGESTION :'):
                    current_section = 'fix_suggestion'
                    content = line.split(':', 1)[-1].strip()
                    content = re.sub(r'\[.*?\]', '', content).strip()
                    
                    # === START FIX (P5) ===
                    content = re.sub(r'(\s+)\*(\s+)', r'\1+\2', content)
                    content = content.replace('**', '')
                    # === END FIX (P5) ===
                    
                    if content:
                        result['fix_suggestion'] = content
                
                elif line.startswith('SUGGESTIONS:') or line.startswith('SUGGESTIONS :'):
                    current_section = 'suggestions'
                    content = line.split(':', 1)[-1].strip()
                    content = re.sub(r'\[.*?\]', '', content).strip()
                    
                    # === START FIX (P5) ===
                    content = content.replace('**', '')
                    # === END FIX (P5) ===
                    
                    if content:
                        result['suggestions'] = content
                
                elif line.startswith('KNOWLEDGE:') or line.startswith('KNOWLEDGE :'):
                    current_section = 'knowledge'
                    content = line.split(':', 1)[-1].strip()
                    content = re.sub(r'\[.*?\]', '', content).strip()
                    
                    # === START FIX (P5) ===
                    content = content.replace('**', '')
                    # === END FIX (P5) ===
                    
                    if content:
                        result['knowledge'] = content
                
                elif current_section and line and not line.startswith('IS_CORRECT'):
                    if line.startswith('[') and line.endswith(']'):
                        continue
                    
                    # === START FIX (P5) ===
                    # Áp dụng logic clean-up nhất quán
                    if current_section == 'fix_suggestion':
                        line = re.sub(r'(\s+)\*(\s+)', r'\1+\2', line)
                        line = line.replace('**', '')
                    elif current_section == 'suggestions':
                        line = line.replace('**', '')
                    elif current_section == 'knowledge':
                        line = line.replace('**', '')
                    # === END FIX (P5) ===
                    
                    if result[current_section]:
                        result[current_section] += '\n' + line
                    else:
                        result[current_section] = line
        
        return result