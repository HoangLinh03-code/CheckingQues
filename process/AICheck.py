from typing import Dict
from api.callApi import VertexClient


# ==================== AI CHECKER V4 ====================
class AIQuestionChecker:
    """
    AI Checker với output chuẩn format
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
        # Tạo prompt
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
            question_text += "\n📝 LỜI GIẢI\n"
            question_text += "="*50 + "\n"
            question_text += "\n".join(question_data['solution_text'])
                
        full_prompt = (
            f"{prompt_content}\n\n"
            "---\n\n"
            "## CÂU HỎI CẦN ĐÁNH GIÁ\n\n"
            f"{question_text}\n\n"
            "---\n\n"
            "## YÊU CẦU OUTPUT\n\n"
            "Trả về CHÍNH XÁC theo format sau (KHÔNG thêm bớt gì):\n\n"
            "```\n"
            "IS_CORRECT: YES/NO\n"
            "####\n"
            "EVALUATION:\n"
            "[Nếu YES: Chỉ viết 'Câu hỏi chính xác']\n"
            "[Nếu NO: Viết ngắn gọn sai ở đâu (1-2 câu)]\n"
            "####\n"
            "SUGGESTIONS:\n"
            "[Gợi ý làm bài theo từng bước, MỖI BƯỚC 1 DÒNG]\n"
            "- Bước 1: ...\n"
            "- Bước 2: ...\n"
            "- Bước 3: ...\n"
            "####\n"
            "KNOWLEDGE:\n"
            "[Viết lại công thức/định lý cốt lõi - TỐI ĐA 3 DÒNG]\n"
            "[Chỉ ghi kiến thức CHÍNH XÁC, KHÔNG giải thích thêm]\n"
            "```\n\n"
            "LƯU Ý:\n"
            "- PHẢI có đủ 4 phần: IS_CORRECT, EVALUATION, SUGGESTIONS, KNOWLEDGE\n"
            "- Phân cách bằng #### (4 dấu thăng)\n"
            "- Không viết thêm text ngoài format trên"
        )
        
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
                result['suggestions'] = "Đọc kỹ đề bài và áp dụng kiến thức đã học"
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
                result['evaluation'] = content
            
            # SUGGESTIONS
            elif 'SUGGESTIONS:' in part or 'SUGGESTIONS :' in part:
                content = part.split('SUGGESTIONS:', 1)[-1].strip()
                content = content.split('SUGGESTIONS :', 1)[-1].strip() if 'SUGGESTIONS :' in part else content
                content = content.split('####')[0].strip()
                result['suggestions'] = content
            
            # KNOWLEDGE
            elif 'KNOWLEDGE:' in part or 'KNOWLEDGE :' in part:
                content = part.split('KNOWLEDGE:', 1)[-1].strip()
                content = content.split('KNOWLEDGE :', 1)[-1].strip() if 'KNOWLEDGE :' in part else content
                content = content.split('####')[0].strip()
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
                    if content:
                        result['evaluation'] = content
                
                elif line.startswith('SUGGESTIONS:') or line.startswith('SUGGESTIONS :'):
                    current_section = 'suggestions'
                    content = line.split(':', 1)[-1].strip()
                    if content:
                        result['suggestions'] = content
                
                elif line.startswith('KNOWLEDGE:') or line.startswith('KNOWLEDGE :'):
                    current_section = 'knowledge'
                    content = line.split(':', 1)[-1].strip()
                    if content:
                        result['knowledge'] = content
                
                elif current_section and line and not line.startswith('IS_CORRECT'):
                    if result[current_section]:
                        result[current_section] += '\n' + line
                    else:
                        result[current_section] = line
        
        return result