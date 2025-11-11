# -*- coding: utf-8 -*-
from typing import List, Dict
from PyQt5.QtCore import QThread, pyqtSignal
from process.AICheck import AIQuestionChecker
import os
from process.EnhancedDocx import EnhancedDocxParser
import time
from process.DocxWriter import DocxWriter
import traceback
import re


class CheckThread(QThread):
    """Thread xử lý với hỗ trợ câu phụ (1.a, 2.b, ...)"""
    
    progress = pyqtSignal(str)
    finished_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)
    
    def __init__(self, input_paths: List[str], prompt_path: str, 
                project_id: str, creds):
        super().__init__()
        self.input_paths = input_paths
        self.prompt_path = prompt_path
        self.project_id = project_id
        self.creds = creds
        self.stop_requested = False
    
    def stop(self):
        self.stop_requested = True
    
    @staticmethod
    def _sort_question_ids(question_ids: list) -> list:
        """
        Sắp xếp danh sách ID câu hỏi (hỗ trợ câu phụ)
        
        Ví dụ: ["1", "1.a", "1.b", "2", "2.a", "10"]
        -> ["1", "1.a", "1.b", "2", "2.a", "10"]
        """
        def parse_id(qid):
            """Parse ID thành (số chính, chữ phụ)"""
            match = re.match(r'^(\d+)(?:\.([a-z]))?$', str(qid))
            if match:
                main_num = int(match.group(1))
                sub_letter = match.group(2) if match.group(2) else ''
                return (main_num, sub_letter)
            # Fallback
            try:
                return (int(qid), '')
            except:
                return (999999, str(qid))
        
        return sorted(question_ids, key=parse_id)
    
    def run(self):
        try:
            # Load prompt
            self.progress.emit("📄 Đang load prompt...")
            with open(self.prompt_path, 'r', encoding='utf-8') as f:
                prompt_content = f.read()
            
            # Init AI
            self.progress.emit("🤖 Đang khởi tạo AI...")
            checker = AIQuestionChecker(self.project_id, self.creds)
            
            # Output folder
            output_folder = "output_check"
            os.makedirs(output_folder, exist_ok=True)
            
            output_files = []
            
            # Xử lý từng file
            for idx, docx_path in enumerate(self.input_paths):
                if self.stop_requested:
                    break
                
                filename = os.path.basename(docx_path)
                self.progress.emit(f"\n{'='*60}")
                self.progress.emit(f"📁 [{idx+1}/{len(self.input_paths)}] {filename}")
                self.progress.emit(f"{'='*60}\n")
                
                try:
                    # Parse với Enhanced Parser
                    self.progress.emit("📖 Đang đọc file (bao gồm ảnh & công thức)...")
                    parser = EnhancedDocxParser(docx_path)
                    questions = parser.parse_questions_with_numbering()
                    dependencies = parser.detect_question_dependencies(questions)
                    
                    self.progress.emit(f"✔️ Tìm thấy {len(questions)} câu hỏi")
                    stats = parser.get_statistics()
                    self.progress.emit(f"   📷 {stats['total_images']} hình ảnh")
                    self.progress.emit(f"   🔢 Ảnh công thức: {stats['formula_images']}, Ảnh minh họa: {stats['illustration_images']}")
                    
                    questions_with_solution = sum(1 for q in questions.values() if len(q.get('solution_text', [])) > 0)
                    self.progress.emit(f"   💡 {questions_with_solution}/{len(questions)} câu có lời giải\n")
                    
                    # Hiển thị danh sách câu hỏi
                    sorted_qids = self._sort_question_ids(list(questions.keys()))
                    self.progress.emit(f"   📝 Danh sách: {', '.join(sorted_qids)}\n")
                    
                    # Check từng câu
                    questions_results = {}
                    correct_count = 0
                    
                    dep_count = sum(1 for d in dependencies.values() if d['depends_on'])
                    if dep_count > 0:
                        self.progress.emit(f"   🔗 {dep_count} câu có phụ thuộc")
                    
                    # Check từng câu
                    questions_results = {}
                    correct_count = 0
                    
                    for qid in sorted_qids:
                        if self.stop_requested:
                            break
                        
                        self.progress.emit(f"🔍 Đang check Câu {qid}...")
                        
                        # === XÂY DỰNG CONTEXT (chỉ cho tự luận) ===
                        context = parser.build_context_for_question(questions, qid)
                        
                        # === LOG RÕ RÀNG VỀ CONTEXT ===
                        q_type = questions[qid].get('question_type', 'unknown')
                        
                        if context:
                            # Đếm số câu trong context
                            context_qids = [line.split('Câu ')[1].split(':')[0] 
                                        for line in context.split('\n') 
                                        if line.strip().startswith('### Câu')]
                            
                            self.progress.emit(f"   📚 Context: {len(context_qids)} câu trước ({', '.join(context_qids)})")
                            self.progress.emit(f"   ⚠️  AI sẽ phân tích xem Câu {qid} có phụ thuộc hay không")
                        else:
                            if q_type == parser.QUESTION_TYPE_ESSAY:
                                self.progress.emit(f"   📝 Tự luận - Câu đầu tiên (không có context)")
                            else:
                                self.progress.emit(f"   ✅ {q_type} - Không cần context")
                        
                        # === GỌI AI CHECK ===
                        result = checker.check_question(
                            questions[qid],
                            prompt_content,
                            context_text=context
                        )
                        
                        questions_results[qid] = result
                        
                        # === LOG KẾT QUẢ ===
                        if result['is_correct']:
                            status = "✅ CHÍNH XÁC"
                            correct_count += 1
                        else:
                            status = "❌ CẦN SỬA"
                        
                        self.progress.emit(f"   ➜ {status}")
                        
                        # Hiển thị phần phân tích quan hệ (nếu có)
                        if not result['is_correct'] and '[Phân tích quan hệ]:' in result['evaluation']:
                            # Trích xuất dòng phân tích quan hệ
                            eval_lines = result['evaluation'].split('\n')
                            for line in eval_lines:
                                if '[Phân tích quan hệ]:' in line or '[Kiểm tra câu trước]:' in line:
                                    self.progress.emit(f"   📌 {line.strip()}")
                                    break
                        
                        if not result['is_correct']:
                            eval_short = result['evaluation'][:100]
                            if len(result['evaluation']) > 100:
                                eval_short += "..."
                            self.progress.emit(f"   📌 {eval_short}")
                        
                        time.sleep(0.5)
                    
                    # Tạo output
                    self.progress.emit("\n📊 Đang tạo file output...")
                    
                    output_filename = f"checked_{filename}"
                    output_path = os.path.join(output_folder, output_filename)
                    
                    DocxWriter.create_output_docx(
                        docx_path,
                        questions_results,
                        output_path
                    )
                    
                    output_files.append(output_path)
                    
                    self.progress.emit(f"✅ Hoàn thành: {output_filename}")
                    self.progress.emit(f"   📈 {correct_count}/{len(questions)} câu chính xác\n")
                    
                except Exception as e:
                    self.progress.emit(f"❌ Lỗi: {str(e)}\n")
                    traceback.print_exc()
                    continue
            
            self.progress.emit("\n" + "="*60)
            self.progress.emit("🎉 HOÀN THÀNH!")
            self.progress.emit("="*60)
            self.progress.emit(f"\n📂 Folder: {output_folder}")
            self.progress.emit(f"📊 Đã xử lý: {len(output_files)}/{len(self.input_paths)} file\n")
            
            self.finished_signal.emit(output_files)
            
        except Exception as e:
            self.error_signal.emit(f"Lỗi: {str(e)}\n{traceback.format_exc()}")