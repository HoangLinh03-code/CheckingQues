from docx import Document
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from typing import Dict
import re
from copy import deepcopy


class DocxWriter:
    """
    Ghi kết quả với bảng đánh giá - Hỗ trợ câu phụ (1.a, 2.b, ...)
    + Thêm hàng "Gợi ý sửa lại"
    """
    
    @staticmethod
    def add_evaluation_table(doc: Document, question_id: str, 
                            evaluation_result: Dict):
        """
        Thêm bảng đánh giá 3 hàng × 2 cột (THEO YÊU CẦU)
        Gộp "Gợi ý sửa lỗi" vào ô "Kết luận".
        
        Args:
            question_id: ID câu hỏi (có thể là "1", "1.a", "2.c", ...)
        """
        doc.add_paragraph()
        
        # --- THAY ĐỔI: TẠO BẢNG 3x2 ---
        num_rows = 3 # Quay lại 3 hàng theo yêu cầu
        table = doc.add_table(rows=num_rows, cols=2)
        table.style = 'Table Grid'
        
        # Set độ rộng cột
        for row in table.rows:
            row.cells[0].width = Inches(1.8)
            row.cells[1].width = Inches(5.2)
        
        row_idx = 0
        
        # === ROW 1: Tiêu đề & Kết luận (GỘP) === (row_idx = 0)
        header_cell = table.rows[row_idx].cells[0]
        header_cell.text = f"Đánh giá câu {question_id}"
        header_cell.vertical_alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        for paragraph in header_cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(12)
        
        DocxWriter._set_cell_background(header_cell, "D9E1F2")
        DocxWriter._set_cell_border(header_cell)
        
        # Cột 2 Row 1: Kết luận (GỘP)
        conclusion_cell = table.rows[row_idx].cells[1]

        if evaluation_result['is_correct']:
            status_text = f"✅ Câu {question_id} CHÍNH XÁC"
            bg_color = "8eeda0"
            eval_text = evaluation_result.get('evaluation', 'Câu hỏi chính xác')
            
            # --- Áp dụng TRỰC TIẾP cho trường hợp 'CHÍNH XÁC' ---
            conclusion_cell.text = status_text
            p_status = conclusion_cell.paragraphs[0]
            p_status.alignment = WD_ALIGN_PARAGRAPH.CENTER # Căn giữa
            
            for run in p_status.runs:
                run.font.bold = True
                run.font.size = Pt(11)
        else:
            # (Trường hợp CHƯA CHÍNH XÁC)
            status_text = f"⚠️ Câu {question_id} CHƯA CHÍNH XÁC"
            bg_color = "ecc296"
            
            # Lấy thông tin (Evaluation)
            eval_text = evaluation_result.get('evaluation', 'Không rõ lý do')
            if eval_text == "Câu hỏi chính xác": # Dọn dẹp trường hợp thừa
                eval_text = "Cần xem lại"
            
            # Lấy thông tin (Fix Suggestion)
            fix_text = evaluation_result.get('fix_suggestion', '')

            # --- Paragraph 1: Tiêu đề (CĂN GIỮA) ---
            conclusion_cell.text = status_text
            p_status = conclusion_cell.paragraphs[0]
            p_status.alignment = WD_ALIGN_PARAGRAPH.CENTER 
            
            for run in p_status.runs:
                run.font.bold = True
                run.font.size = Pt(11)
    
            # --- Paragraph 2: Thêm lý do (CĂN TRÁI) ---
            if eval_text:
                conclusion_cell.add_paragraph() # Thêm dòng trống
                p_eval = conclusion_cell.add_paragraph()
                p_eval.alignment = WD_ALIGN_PARAGRAPH.LEFT
                
                run_eval = p_eval.add_run(eval_text)
                run_eval.font.bold = True
                run_eval.font.size = Pt(11)
            
            # --- Paragraph 3: Thêm GỢI Ý SỬA LỖI (GỘP VÀO ĐÂY) ---
            if fix_text:
                conclusion_cell.add_paragraph() # Thêm dòng trống
                
                # Thêm tiêu đề "Gợi ý sửa lỗi"
                p_fix_label = conclusion_cell.add_paragraph()
                p_fix_label.alignment = WD_ALIGN_PARAGRAPH.LEFT
                run_fix_label = p_fix_label.add_run("Gợi ý sửa lỗi:")
                run_fix_label.font.bold = True
                run_fix_label.font.color.rgb = RGBColor(255, 0, 0)  # Màu đỏ
                run_fix_label.font.size = Pt(10)

                # Thêm nội dung sửa lỗi (màu đỏ)
                p_fix_content = conclusion_cell.add_paragraph()
                p_fix_content.alignment = WD_ALIGN_PARAGRAPH.LEFT
                run_fix_content = p_fix_content.add_run(fix_text)
                run_fix_content.font.size = Pt(10)
                run_fix_content.font.bold = True
        
        DocxWriter._set_cell_background(conclusion_cell, bg_color)
        DocxWriter._set_cell_border(conclusion_cell)
        
        row_idx += 1
        
        # === ROW 2: Gợi ý làm bài === (row_idx = 1)
        label_cell = table.rows[row_idx].cells[0]
        label_cell.text = "Gợi ý làm bài"
        label_cell.vertical_alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        for paragraph in label_cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(10)
        
        DocxWriter._set_cell_background(label_cell, "D9E1F2")
        DocxWriter._set_cell_border(label_cell)
        
        # Nội dung gợi ý
        sugg_cell = table.rows[row_idx].cells[1]
        sugg_text = evaluation_result.get('suggestions', 'Không có gợi ý')
        sugg_cell.text = sugg_text
        
        for paragraph in sugg_cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in paragraph.runs:
                run.font.size = Pt(10)
        
        DocxWriter._set_cell_border(sugg_cell)
        
        row_idx += 1
        
        # === ROW 3: Kiến thức liên quan === (row_idx = 2)
        knowledge_label = table.rows[row_idx].cells[0]
        knowledge_label.text = "Kiến thức liên quan"
        knowledge_label.vertical_alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        for paragraph in knowledge_label.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(10)
        
        DocxWriter._set_cell_background(knowledge_label, "D9E1F2")
        DocxWriter._set_cell_border(knowledge_label)
        
        # Nội dung kiến thức
        knowledge_cell = table.rows[row_idx].cells[1]
        knowledge_text = evaluation_result.get('knowledge', 'Không có thông tin')
        knowledge_cell.text = knowledge_text
        
        for paragraph in knowledge_cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in paragraph.runs:
                run.font.size = Pt(10)
        
        DocxWriter._set_cell_border(knowledge_cell)
        
        doc.add_paragraph()
    
    @staticmethod
    def _set_cell_border(cell):
        """Set border cho cell"""
        tc = cell._element
        tcPr = tc.get_or_add_tcPr()
        
        tcBorders = OxmlElement('w:tcBorders')
        for edge in ('top', 'left', 'bottom', 'right'):
            edge_element = OxmlElement(f'w:{edge}')
            edge_element.set(qn('w:val'), 'single')
            edge_element.set(qn('w:sz'), '4')
            edge_element.set(qn('w:space'), '0')
            edge_element.set(qn('w:color'), '000000')
            tcBorders.append(edge_element)
        
        tcPr.append(tcBorders)
    
    @staticmethod
    def _set_cell_background(cell, color_hex):
        """Set background color cho cell"""
        cell_properties = cell._element.get_or_add_tcPr()
        cell_shading = OxmlElement('w:shd')
        cell_shading.set(qn('w:fill'), color_hex)
        cell_properties.append(cell_shading)
    
    @staticmethod
    def _sort_question_ids(question_ids: list) -> list:
        """
        Sắp xếp danh sách ID câu hỏi (hỗ trợ câu phụ)
        
        Ví dụ: ["1", "1.a", "1.b", "2", "2.a", "10", "10.c"]
        -> ["1", "1.a", "1.b", "2", "2.a", "10", "10.c"]
        """
        def parse_id(qid):
            """Parse ID thành (số chính, chữ phụ)"""
            match = re.match(r'^(\d+)(?:\.([a-z]))?$', str(qid))
            if match:
                main_num = int(match.group(1))
                sub_letter = match.group(2) if match.group(2) else ''
                return (main_num, sub_letter)
            # Fallback: nếu không match, coi như số nguyên
            try:
                return (int(qid), '')
            except:
                return (999999, str(qid))  # Đẩy xuống cuối
        
        return sorted(question_ids, key=parse_id)
    
    @staticmethod
    def create_output_docx(input_docx: str, questions_results: Dict[str, Dict],
                          output_path: str):
        """
        Tạo file output với bảng đánh giá
        
        Args:
            questions_results: Dict với key là string (ví dụ: "1", "1.a", "2.c")
        """
        from process.EnhancedDocx import EnhancedDocxParser
        import shutil
        
        print(f"\n[DocxWriter] Bắt đầu tạo file output...")
        shutil.copy2(input_docx, output_path)
        print(f"[DocxWriter] Đã copy file gốc")
        
        print(f"[DocxWriter] Đang parse để xác định vị trí chèn bảng...")
        parser = EnhancedDocxParser(input_docx, debug=False)
        questions = parser.parse_questions_with_numbering()
        
        doc = Document(output_path)
        total_paras = len(doc.paragraphs)
        print(f"[DocxWriter] Document có {total_paras} paragraphs")
        
        # Chuẩn bị danh sách vị trí chèn
        insert_positions = []
        for qid, q_data in questions.items():
            if qid in questions_results:
                end_para = q_data.get('end_paragraph', -1)
                
                if end_para >= 0 and end_para < total_paras:
                    insert_positions.append({
                        'qid': qid,
                        'position': end_para + 1,
                        'result': questions_results[qid]
                    })
                    
                    has_solution = len(q_data.get('solution_text', [])) > 0
                    print(f"[DocxWriter] Câu {qid}: "
                          f"start={q_data['start_paragraph']}, "
                          f"end={end_para}, "
                          f"insert_at={end_para + 1}, "
                          f"solution={'Có' if has_solution else 'Không'}")
                else:
                    print(f"[DocxWriter] Câu {qid}: end_paragraph không hợp lệ ({end_para})")
        
        # Sắp xếp từ cuối lên để chèn (tránh lệch index)
        insert_positions.sort(key=lambda x: x['position'], reverse=True)
        
        print(f"\n[DocxWriter] Bắt đầu chèn {len(insert_positions)} bảng đánh giá...")
        
        # Chèn bảng từ cuối lên đầu
        for item in insert_positions:
            qid = item['qid']
            position = item['position']
            result = item['result']
            
            try:
                # Tạo bảng tạm
                temp_doc = Document()
                DocxWriter.add_evaluation_table(temp_doc, qid, result)
                
                # Lấy table element
                table_element = None
                for element in temp_doc.element.body:
                    if element.tag.endswith('tbl'):
                        table_element = element
                        break
                
                if table_element is None:
                    print(f"[DocxWriter] Không tìm thấy table element cho Câu {qid}")
                    continue
                
                # Chèn vào đúng vị trí
                if position < len(doc.paragraphs):
                    # Thêm paragraph trống trước
                    empty_para = doc.paragraphs[position]._element.addprevious(
                        deepcopy(doc.add_paragraph()._element)
                    )
                    
                    # Chèn table
                    doc.paragraphs[position]._element.addprevious(
                        deepcopy(table_element)
                    )
                    
                    # Thêm paragraph trống sau
                    doc.paragraphs[position]._element.addprevious(
                        deepcopy(doc.add_paragraph()._element)
                    )
                    
                    print(f"[DocxWriter] Đã chèn bảng đánh giá cho Câu {qid} tại vị trí {position}")
                else:
                    # Thêm vào cuối document
                    doc.add_paragraph()
                    doc._element.body.append(deepcopy(table_element))
                    doc.add_paragraph()
                    
                    print(f"[DocxWriter] Đã thêm bảng đánh giá cho Câu {qid} vào cuối document")
                
            except Exception as e:
                print(f"[DocxWriter] Lỗi chèn bảng cho Câu {qid}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"\n[DocxWriter] Đang lưu file...")
        doc.save(output_path)
        
        print(f"[DocxWriter] Hoàn thành: {output_path}")
        print(f"[DocxWriter] Đã thêm {len(insert_positions)} bảng đánh giá")
        print(f"[DocxWriter] " + "="*60 + "\n")