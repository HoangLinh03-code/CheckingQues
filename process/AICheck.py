import traceback
from typing import Dict, List
from api.callApi import VertexClient
import re
import json
# ==================== AI CHECKER V5 (OPTIMIZED PROMPT) ====================
class AIQuestionChecker:
    """
    AI Checker với prompt tối ưu và output chuẩn format
    """
    
    def __init__(self, project_id: str, creds, model_name: str = "gemini-2.5-pro"):
        self.client = VertexClient(project_id, creds, model_name)

    
    
    def check_question(self, question_data: Dict, prompt_content: str) -> Dict:
        """
        Check câu hỏi với text, images, equations
        
        Returns:
            {
                'is_correct': bool,
                'evaluation': str,      # Ngắn gọn: "Câu hỏi chính xác" hoặc lý do sai
                'suggestions': str,     # Gạch đầu dòng các bước
                'knowledge': str        # Kiến thức cốt lõi
            }
        """
        # Tạo prompt với format cải tiến
        question_text = "\n".join(question_data.get('question_text', []))
        
        # Thêm thông tin hình ảnh
        q_images = len(question_data.get('question_images', []))
        s_images = len(question_data.get('solution_images', []))
        if q_images > 0 or s_images > 0:
            question_text += f"\n\n[📷 Câu hỏi có {q_images} ảnh, Lời giải có {s_images} ảnh]"
        
        # Thêm công thức
        q_eqs = question_data.get('question_equations', [])
        s_eqs = question_data.get('solution_equations', [])
        if q_eqs or s_eqs:
            question_text += "\n\n📐 CÔNG THỨC:\n"
            for eq in q_eqs:
                content = eq.get('content', str(eq))
                question_text += f"- [Câu hỏi] {content}\n"
            for eq in s_eqs:
                content = eq.get('content', str(eq))
                question_text += f"- [Lời giải] {content}\n"
        
        # Thêm lời giải (nếu có)
        if question_data.get('solution_text'):
            question_text += "\n\n" + "="*50
            question_text += "\n📗 LỜI GIẢI\n"
            question_text += "="*50 + "\n"
            question_text += "\n".join(question_data['solution_text'])
                
        # Tạo prompt với format mới
        full_prompt = self._build_optimized_prompt(prompt_content, question_text)
        
        try:
            response = self.client.send_data_to_check(
                prompt=full_prompt,
                temperature=0.2
            )
            
            result = self._parse_response(response)
            
            # Validate kết quả
            if not result['evaluation']:
                result['evaluation'] = "Câu hỏi chính xác" if result['is_correct'] else "Cần kiểm tra lại"
            if not result['suggestions']:
                result['suggestions'] = "- Bước 1: Đọc kỹ đề bài và xác định yêu cầu\n- Bước 2: Áp dụng kiến thức đã học\n- Bước 3: Tính toán và chọn đáp án"
            if not result['knowledge']:
                result['knowledge'] = "Áp dụng kiến thức theo chương trình học"
            
            return result
            
        except Exception as e:
            print(f"[AIChecker] Lỗi: {str(e)}")
            return {
                'is_correct': False,
                'evaluation': f"Lỗi AI: {str(e)}",
                'suggestions': "Không thể đánh giá",
                'knowledge': "Không có thông tin"
            }
    
    def _build_optimized_prompt(self, prompt_content: str, question_text: str) -> str:
        """
        Xây dựng prompt tối ưu với format rõ ràng
        """
        return f"""{prompt_content}

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
SUGGESTIONS:
[Gợi ý làm bài theo từng bước, MỖI BƯỚC 1 DÒNG]
- Bước 1: ...
- Bước 2: ...
- Bước 3: ...
[Tối thiểu 3 bước, tối đa 5 bước]
####
KNOWLEDGE:
[Viết lại công thức/định lý cốt lõi - TỐI ĐA 3 DÒNG]
[Chỉ ghi kiến thức CHÍNH XÁC, KHÔNG giải thích thêm]
```

## LƯU Ý QUAN TRỌNG

1. **IS_CORRECT phải là YES hoặc NO** - không có giá trị khác
2. **EVALUATION:**
   - Nếu IS_CORRECT: YES → Chỉ viết: "Câu hỏi chính xác"
   - Nếu IS_CORRECT: NO → Nêu rõ vấn đề chính (ví dụ: "Đáp án A và B trùng nhau", "Thiếu dữ kiện về thời gian", "Bước 2 tính sai công thức")

3. **SUGGESTIONS:**
   - Phải có ít nhất 3 bước, tối đa 5 bước
   - Mỗi bước bắt đầu bằng "- Bước X:"
   - Viết cụ thể, đầy đủ: Đọc đề → Phân tích → Áp dụng → Tính toán → Kết luận

4. **KNOWLEDGE:**
   - Tối đa 3 dòng
   - Chỉ ghi công thức/định lý chính, súc tích
   - Ví dụ: "- Định luật Ohm: U = I × R"

5. **Format:**
   - Phân cách bằng #### (4 dấu thăng)
   - Không viết thêm text ngoài 4 phần trên
   - Không dùng markdown code block ```

## VÍ DỤ CHUẨN

**Ví dụ 1: Câu đúng**
```
IS_CORRECT: YES
####
EVALUATION:
Câu hỏi chính xác
####
SUGGESTIONS:
- Bước 1: Đọc kỹ đề, xác định các đại lượng đã cho
- Bước 2: Nhận dạng công thức điện trở tương đương mạch nối tiếp
- Bước 3: Áp dụng công thức R = R1 + R2 + R3 và thay số
- Bước 4: Chọn đáp án có giá trị tính được
####
KNOWLEDGE:
- Điện trở mạch nối tiếp: R = R1 + R2 + ... + Rn
- Cường độ dòng điện qua các điện trở bằng nhau
```

**Ví dụ 2: Câu sai**
```
IS_CORRECT: NO
####
EVALUATION:
Đáp án A và đáp án C có cùng nội dung "6Ω", gây nhầm lẫn cho học sinh
####
SUGGESTIONS:
- Bước 1: Kiểm tra kỹ các đáp án, nhận biết đáp án nào khác biệt
- Bước 2: Áp dụng công thức điện trở song song: 1/R = 1/R1 + 1/R2
- Bước 3: Tính toán và đối chiếu với đáp án hợp lý
- Bước 4: Trong trường hợp đề có vấn đề, báo giáo viên để làm rõ
####
KNOWLEDGE:
- Điện trở mạch song song: 1/R = 1/R1 + 1/R2 + ... + 1/Rn
- Hiệu điện thế hai đầu các điện trở bằng nhau
```

BẮT ĐẦU ĐÁNH GIÁ:"""
    
    def _parse_response(self, response: str) -> Dict:
        """Parse AI response - xử lý cả format sai"""
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
                # Loại bỏ phần còn lại nếu có
                content = content.split('####')[0].strip()
                # Loại bỏ comment trong []
                content = re.sub(r'\[.*?\]', '', content).strip()
                result['evaluation'] = content
            
            # SUGGESTIONS
            elif 'SUGGESTIONS:' in part or 'SUGGESTIONS :' in part:
                content = part.split('SUGGESTIONS:', 1)[-1].strip()
                content = content.split('SUGGESTIONS :', 1)[-1].strip() if 'SUGGESTIONS :' in part else content
                content = content.split('####')[0].strip()
                # Loại bỏ comment trong []
                content = re.sub(r'\[.*?\]', '', content).strip()
                result['suggestions'] = content
            
            # KNOWLEDGE
            elif 'KNOWLEDGE:' in part or 'KNOWLEDGE :' in part:
                content = part.split('KNOWLEDGE:', 1)[-1].strip()
                content = content.split('KNOWLEDGE :', 1)[-1].strip() if 'KNOWLEDGE :' in part else content
                content = content.split('####')[0].strip()
                # Loại bỏ comment trong []
                content = re.sub(r'\[.*?\]', '', content).strip()
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
                    # Loại bỏ comment
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
                    # Bỏ qua comment
                    if line.startswith('[') and line.endswith(']'):
                        continue
                    
                    if result[current_section]:
                        result[current_section] += '\n' + line
                    else:
                        result[current_section] = line
        
        return result
    
# class AIQuestionExcelChecker:
#     """
#     AI Checker chuyên dụng cho ExcelCheckThread.
#     Nhận dữ liệu từng dòng Excel, gọi AI và trả về dictionary phù hợp với cột trong Excel.
#     """
    
#     def __init__(self, project_id: str, creds, model_name: str = "gemini-2.5-pro"):
#         self.client = VertexClient(project_id, creds, model_name)

#     def check_question(self, question_data: Dict, prompt_content: str) -> Dict:
#         """
#         Kiểm tra câu hỏi từ Excel.
        
#         Args:
#             question_data: {
#                 "question_text": List[str],
#                 "question_images": List,
#                 "solution_text": List[str],
#                 "question_equations": List,
#                 "solution_equations": List,
#                 "materials": str,
#                 "options": str,
#                 "extras": List[str]
#             }
#             prompt_content: text prompt gốc từ file prompt.txt
            
#         Returns:
#             Dict với 3 trường: evaluation, suggestions, knowledge
#         """
#         # --- 1. Chuẩn bị text cho AI ---
#         q_text = "\n".join(question_data.get("question_text", []))
#         materials = question_data.get("materials", "")
#         options = question_data.get("options", "")
#         extras = question_data.get("extras", [])

#         full_context = [prompt_content, f"Đề bài: {q_text}"]
#         if materials:
#             full_context.append(f"Học liệu / Nội dung tham khảo: {materials}")
#         if options:
#             full_context.append(f"Phương án / Đáp án: {options}")
#         if extras:
#             full_context.append("Thông tin khác:\n" + "\n".join(extras))
        
#         # full_context.append(
#         #     "\nYêu cầu: Trả về JSON với 3 trường: evaluation, suggestions, knowledge"
#         # )
#         full_context.append(
#     "\nYêu cầu: Trả về theo đúng định dạng text dưới đây, không thêm ký hiệu hay markdown:\n"
#     "EVALUATION:\n[một câu]\n\n"
#     "SUGGESTIONS:\n[2-4 dòng, mỗi dòng bắt đầu bằng '-']\n\n"
#     "KNOWLEDGE:\n[5-7 câu kiến thức, mỗi câu một dòng]\n"
# )
#         final_prompt = "\n\n".join(full_context)

#         # --- 2. Gọi AI ---
#         try:
#             response = self.client.send_data_to_check(prompt=final_prompt, temperature=0.2)
#             return self.parse_ai_response(response)
#         except Exception as e:
#             return {
#                 "evaluation": f"Lỗi AI: {str(e)}",
#                 "suggestions": "Không thể đánh giá",
#                 "knowledge": "Không có thông tin"
#             }
#     def clean_json_string(s: str) -> str:
#         """Loại bỏ code block ```json ...``` và các ký tự escape thừa"""
#         s = s.strip()
#         # Xóa markdown code block
#         s = re.sub(r"^```json\s*|\s*```$", "", s, flags=re.IGNORECASE)
#         # Thay \n, \t, \\uxxxx… thành ký tự thực
#         s = s.encode('utf-8').decode('unicode_escape')
#         return s    

#     def parse_ai_response(self, text: str) -> Dict[str, str]:
#         """Tách 3 phần EVALUATION / SUGGESTIONS / KNOWLEDGE từ text AI trả về"""
#         result = {"evaluation": "", "suggestions": "", "knowledge": ""}
#         if not text:
#             return result

#         s = text.replace("\r", "").strip()

#         # Regex nhận diện 3 phần
#         eval_re = r"(?:^|\n)\s*EVALUATION\s*:\s*"
#         sugg_re = r"(?:^|\n)\s*SUGGESTIONS\s*:\s*"
#         know_re = r"(?:^|\n)\s*KNOWLEDGE\s*:\s*"

#         m_eval = re.search(eval_re, s, flags=re.IGNORECASE)
#         m_sugg = re.search(sugg_re, s, flags=re.IGNORECASE)
#         m_know = re.search(know_re, s, flags=re.IGNORECASE)

#         if not m_eval:
#             return result

#         eval_end = m_sugg.start() if m_sugg else (m_know.start() if m_know else len(s))
#         sugg_end = m_know.start() if m_know else len(s)

#         result["evaluation"] = s[m_eval.end():eval_end].strip() if m_eval else ""
#         result["suggestions"] = s[m_sugg.end():sugg_end].strip() if m_sugg else ""
#         result["knowledge"] = s[m_know.end():].strip() if m_know else ""

#         return result

class AIQuestionExcelChecker:
    """AI Checker chuyên dụng cho ExcelCheckThread (batch request)."""

    def __init__(self, project_id: str, creds, model_name: str = "gemini-2.5-pro"):
        self.client = VertexClient(project_id, creds, model_name)

  

    def check_questions_batch(self, questions_data, prompt_text):
        if not questions_data:
            return []

        total = len(questions_data)
        chunk_size = 10 if total >= 20 else total if total < 10 else 10

        all_results = []

        # chia chunk
        for idx, i in enumerate(range(0, total, chunk_size), start=1):
            chunk = questions_data[i:i + chunk_size]

            # SỬ DỤNG _build_batch_prompt để format nhất quán
            final_prompt = self._build_batch_prompt(chunk, prompt_text)

            try:
                response = self.client.send_data_to_check(prompt=final_prompt, temperature=0.2)
                parsed_list = self.parse_ai_response_batch(response, len(chunk))
                all_results.extend(parsed_list)
            except Exception as e:
                # nếu lỗi, thêm placeholder rỗng để không làm lệch zip khi ghi
                for _ in chunk:
                    all_results.append({"evaluation": "", "suggestions": "", "knowledge": ""})
                continue

        # đảm bảo đúng độ dài
        while len(all_results) < total:
            all_results.append({"evaluation": "", "suggestions": "", "knowledge": ""})

        return all_results[:total]

    # ------------------------- GHÉP PROMPT -------------------------
    def _build_batch_prompt(self, question_list: List[Dict], prompt_content: str) -> str:
        """Tạo prompt chứa nhiều câu hỏi."""
        sections = [prompt_content, "Dưới đây là danh sách các câu hỏi cần phân tích:\n"]

        for idx, q in enumerate(question_list, start=1):
            q_text = "\n".join(q.get("question_text", []))
            materials = q.get("materials", "")
            options = q.get("options", "")
            extras = q.get("extras", [])

            block = [f"--- CÂU HỎI {idx} ---", f"Đề bài: {q_text}"]
            if materials:
                block.append(f"Học liệu: {materials}")
            if options:
                block.append(f"Phương án: {options}")
            if extras:
                block.append("Thông tin khác:\n" + "\n".join(extras))
            sections.append("\n".join(block))

        sections.append(
            "\nYêu cầu: Trả về kết quả cho từng câu hỏi, theo đúng mẫu sau (không markdown):\n"
            "CÂU HỎI [số]:\n"
            "EVALUATION: [một câu]\n"
            "SUGGESTIONS:\n- dòng 1\n- dòng 2\n"
            "KNOWLEDGE:\n[5-7 câu mỗi dòng một câu]\n\n"
            "Lặp lại theo thứ tự từng câu."
        )
        return "\n\n".join(sections)

    # ------------------------- PHÂN TÍCH KẾT QUẢ -------------------------


    def parse_ai_response_batch(self, text: str, expected_count: int) -> List[Dict[str, str]]:
        results = []
        if not text:
            return [{"evaluation": "", "suggestions": "", "knowledge": ""} for _ in range(expected_count)]

        # chia an toàn theo khoá "CÂU HỎI" hoặc các delimiters --- 
        blocks = re.split(r"\n---+\s*\n", text)
        # lọc các block rỗng và giữ chỉ những block có "EVALUATION" hoặc "SUGGESTIONS"...
        for blk in blocks:
            blk = blk.strip()
            if not blk:
                continue
            # nếu block chứa nhiều câu (AI may repeat full blocks), tách thêm theo "CÂU HỎI \d+"
            sub = re.split(r"CÂU HỎI\s*\d+\s*[:\-]?", blk, flags=re.IGNORECASE)
            for s in sub:
                s = s.strip()
                if not s:
                    continue
                results.append(self.parse_ai_response(s))
                if len(results) >= expected_count:
                    break
            if len(results) >= expected_count:
                break

        # fill nếu thiếu
        while len(results) < expected_count:
            results.append({"evaluation": "", "suggestions": "", "knowledge": ""})

        return results[:expected_count]

    # ----- Sửa parse_ai_response để robust hơn (giữ nguyên logic nhưng an toàn) -----
    def parse_ai_response(self, text: str) -> Dict[str, str]:
        result = {"evaluation": "", "suggestions": "", "knowledge": ""}
        if not text:
            return result
        s = text.replace("\r", "").strip()

        # tìm các phần bằng regex (case-insensitive)
        parts = re.split(r"(?:\n|^)\s*(EVALUATION\s*:|SUGGESTIONS\s*:|KNOWLEDGE\s*:)\s*", s, flags=re.IGNORECASE)
        # parts sẽ có pattern: [maybe text before, header1, content1, header2, content2,...]
        # dựng dict từ đó
        cur_key = None
        buf = {"evaluation": "", "suggestions": "", "knowledge": ""}
        i = 0
        while i < len(parts):
            part = parts[i].strip()
            if re.match(r"(?i)^EVALUATION\s*:$", part):
                # next piece is content
                if i + 1 < len(parts):
                    buf["evaluation"] = parts[i+1].strip()
                    i += 2
                    continue
            if re.match(r"(?i)^SUGGESTIONS\s*:$", part):
                if i + 1 < len(parts):
                    buf["suggestions"] = parts[i+1].strip()
                    i += 2
                    continue
            if re.match(r"(?i)^KNOWLEDGE\s*:$", part):
                if i + 1 < len(parts):
                    buf["knowledge"] = parts[i+1].strip()
                    i += 2
                    continue
            i += 1

        # nếu parser không tìm được, fallback lấy toàn bộ text vào evaluation
        if not buf["evaluation"] and not buf["suggestions"] and not buf["knowledge"]:
            buf["evaluation"] = s

        return buf

   
