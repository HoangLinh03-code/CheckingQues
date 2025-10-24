from docx import Document
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from typing import Dict
import re
from copy import deepcopy


# ==================== DOCX WRITER V6 (WORKFLOW FIXED) ====================
class DocxWriter:
    """
    Ghi kết quả với bảng đánh giá - ĐẢM BẢO CHÈN SAU LỜI GIẢI
    Workflow:
    1. Copy file gốc
    2. Xác định vị trí end_paragraph của mỗi câu (đã bao gồm lời giải)
    3. Chèn bảng NGAY SAU end_paragraph
    4. Chèn từ cuối lên để tránh lệch index
    """
    
    @staticmethod
    def add_evaluation_table(doc: Document, question_num: int, 
                            evaluation_result: Dict):
        """
        Thêm bảng đánh giá 3 hàng × 2 cột
        
        Row 1: Tiêu đề | Kết luận
        Row 2: Gợi ý làm bài
        Row 3: Kiến thức liên quan
        """
        doc.add_paragraph()
        
        # Tạo bảng 3x2
        table = doc.add_table(rows=3, cols=2)
        table.style = 'Table Grid'
        
        # Set độ rộng cột
        for row in table.rows:
            row.cells[0].width = Inches(1.5)
            row.cells[1].width = Inches(4.5)
        
        # === ROW 1: Tiêu đề & Kết luận ===
        header_cell = table.rows[0].cells[0]
        header_cell.text = f"Đánh giá câu {question_num}"
        
        for paragraph in header_cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(12)
        
        DocxWriter._set_cell_background(header_cell, "4472C4")
        DocxWriter._set_cell_border(header_cell)
        
        # Cột 2 Row 1: Kết luận
        conclusion_cell = table.rows[0].cells[1]
        
        if evaluation_result['is_correct']:
            status_text = f"✅ Câu {question_num} CHÍNH XÁC"
            bg_color = "C6E0B4"
        else:
            status_text = f"⚠️ Câu {question_num} CHƯA CHÍNH XÁC"
            bg_color = "F4B084"
            # Thêm lý do ngắn gọn
            eval_text = evaluation_result.get('evaluation', '')
            if eval_text and eval_text != "Câu hỏi chính xác":
                status_text += f"\n\n{eval_text}"
        
        conclusion_cell.text = status_text
        
        for paragraph in conclusion_cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(11)
        
        DocxWriter._set_cell_background(conclusion_cell, bg_color)
        DocxWriter._set_cell_border(conclusion_cell)
        
        # === ROW 2: Gợi ý làm bài ===
        label_cell = table.rows[1].cells[0]
        label_cell.text = "Gợi ý làm bài"
        
        for paragraph in label_cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(10)
        
        DocxWriter._set_cell_background(label_cell, "D9E1F2")
        DocxWriter._set_cell_border(label_cell)
        
        # Nội dung gợi ý
        sugg_cell = table.rows[1].cells[1]
        sugg_text = evaluation_result.get('suggestions', 'Không có gợi ý')
        sugg_cell.text = sugg_text
        
        for paragraph in sugg_cell.paragraphs:
            for run in paragraph.runs:
                run.font.size = Pt(10)
        
        DocxWriter._set_cell_border(sugg_cell)
        
        # === ROW 3: Kiến thức liên quan ===
        knowledge_label = table.rows[2].cells[0]
        knowledge_label.text = "Kiến thức"
        
        for paragraph in knowledge_label.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(10)
        
        DocxWriter._set_cell_background(knowledge_label, "D9E1F2")
        DocxWriter._set_cell_border(knowledge_label)
        
        # Nội dung kiến thức
        knowledge_cell = table.rows[2].cells[1]
        knowledge_text = evaluation_result.get('knowledge', 'Không có thông tin')
        knowledge_cell.text = knowledge_text
        
        for paragraph in knowledge_cell.paragraphs:
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
    def create_output_docx(input_docx: str, questions_results: Dict[int, Dict],
                          output_path: str):
        """
        WORKFLOW CHÍNH XÁC:
        1. Copy file gốc sang output
        2. Parse để lấy end_paragraph của mỗi câu (đã bao gồm lời giải)
        3. Chèn bảng đánh giá NGAY SAU end_paragraph
        4. Chèn từ cuối lên đầu để tránh lệch index
        """
        from process.EnhancedDocx import EnhancedDocxParser
        import shutil
        
        # Bước 1: Copy file gốc
        print(f"\n[DocxWriter] 📋 Bắt đầu tạo file output...")
        shutil.copy2(input_docx, output_path)
        print(f"[DocxWriter] ✓ Đã copy file gốc")
        
        # Bước 2: Parse để lấy thông tin vị trí
        print(f"[DocxWriter] 🔍 Đang parse để xác định vị trí chèn bảng...")
        parser = EnhancedDocxParser(input_docx, debug=False)
        questions = parser.parse_questions_with_numbering()
        
        # Bước 3: Mở file đã copy
        doc = Document(output_path)
        total_paras = len(doc.paragraphs)
        print(f"[DocxWriter] 📄 Document có {total_paras} paragraphs")
        
        # Bước 4: Chuẩn bị danh sách vị trí chèn
        insert_positions = []
        for qnum, q_data in questions.items():
            if qnum in questions_results:
                end_para = q_data.get('end_paragraph', -1)
                
                if end_para >= 0 and end_para < total_paras:
                    insert_positions.append({
                        'qnum': qnum,
                        'position': end_para + 1,  # Chèn NGAY SAU end_paragraph
                        'result': questions_results[qnum]
                    })
                    
                    has_solution = len(q_data.get('solution_text', [])) > 0
                    print(f"[DocxWriter] 📍 Câu {qnum}: "
                          f"start={q_data['start_paragraph']}, "
                          f"end={end_para}, "
                          f"insert_at={end_para + 1}, "
                          f"solution={'Có' if has_solution else 'Không'}")
                else:
                    print(f"[DocxWriter] ⚠️ Câu {qnum}: end_paragraph không hợp lệ ({end_para})")
        
        # Bước 5: Sắp xếp từ cuối lên để chèn (tránh lệch index)
        insert_positions.sort(key=lambda x: x['position'], reverse=True)
        
        print(f"\n[DocxWriter] 🔧 Bắt đầu chèn {len(insert_positions)} bảng đánh giá...")
        
        # Bước 6: Chèn bảng từ cuối lên đầu
        for item in insert_positions:
            qnum = item['qnum']
            position = item['position']
            result = item['result']
            
            try:
                # Tạo bảng tạm trong document mới
                temp_doc = Document()
                DocxWriter.add_evaluation_table(temp_doc, qnum, result)
                
                # Lấy tất cả elements từ temp_doc (bao gồm paragraph trống và table)
                table_element = None
                for element in temp_doc.element.body:
                    if element.tag.endswith('tbl'):  # Tìm table element
                        table_element = element
                        break
                
                if table_element is None:
                    print(f"[DocxWriter] ⚠️ Không tìm thấy table element cho Câu {qnum}")
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
                    
                    print(f"[DocxWriter] ✅ Đã chèn bảng đánh giá cho Câu {qnum} tại vị trí {position}")
                else:
                    # Thêm vào cuối document
                    doc.add_paragraph()
                    doc._element.body.append(deepcopy(table_element))
                    doc.add_paragraph()
                    
                    print(f"[DocxWriter] ✅ Đã thêm bảng đánh giá cho Câu {qnum} vào cuối document")
                
            except Exception as e:
                print(f"[DocxWriter] ❌ Lỗi chèn bảng cho Câu {qnum}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        # Bước 7: Lưu file
        print(f"\n[DocxWriter] 💾 Đang lưu file...")
        doc.save(output_path)
        
        print(f"[DocxWriter] ✅ Hoàn thành: {output_path}")
        print(f"[DocxWriter] 📊 Đã thêm {len(insert_positions)} bảng đánh giá")
        print(f"[DocxWriter] " + "="*60 + "\n")