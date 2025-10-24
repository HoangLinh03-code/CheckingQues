# -*- coding: utf-8 -*-
from typing import List, Dict
from PyQt5.QtCore import QThread, pyqtSignal
from process.AICheck import AIQuestionChecker
import os
from process.EnhancedDocx import EnhancedDocxParser
import time
from process.DocxWriter import DocxWriter
import traceback

# ==================== PROCESSING THREAD V2 ====================
class CheckThread(QThread):
    """Thread xử lý với Enhanced Parser"""
    
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
                    
                    self.progress.emit(f"✔️ Tìm thấy {len(questions)} câu hỏi")
                    stats = parser.get_statistics()
                    self.progress.emit(f"   📷 {stats['total_images']} hình ảnh")
                    self.progress.emit(f"   📐 Ảnh công thức: {stats['formula_images']}, Ảnh minh họa: {stats['illustration_images']}")
                    
                    questions_with_solution = sum(1 for q in questions.values() if len(q.get('solution_text', [])) > 0)
                    self.progress.emit(f"   💡 {questions_with_solution}/{len(questions)} câu có lời giải\n")
                    
                    # Check từng câu
                    questions_results = {}
                    correct_count = 0
                    
                    for qnum in sorted(questions.keys()):
                        if self.stop_requested:
                            break
                        
                        self.progress.emit(f"🔍 Đang check Câu {qnum}...")
                        
                        result = checker.check_question(
                            questions[qnum],
                            prompt_content
                        )
                        
                        questions_results[qnum] = result
                        
                        if result['is_correct']:
                            status = "✅ CHÍNH XÁC"
                            correct_count += 1
                        else:
                            status = "❌ CẦN SỬA"
                        
                        self.progress.emit(f"   ➜ {status}")
                        
                        if not result['is_correct']:
                            eval_short = result['evaluation'][:80] + "..."
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