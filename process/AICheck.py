from typing import Dict
from api.callApi import VertexClient
import re

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