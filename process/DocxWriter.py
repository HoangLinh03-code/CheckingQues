from docx import Document
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from typing import Dict
import re
from copy import deepcopy
import zipfile
from lxml import etree  # Cần import lxml

# ==================== DOCX WRITER V7 (XML/ZIP SURGERY) ====================
class DocxWriter:
    """
    Ghi kết quả bằng thao tác ZIP và XML trực tiếp.
    Workflow:
    1. Parse (dùng python-docx) để lấy vị trí
    2. Đọc input_docx.zip, lấy word/document.xml
    3. Parse XML bằng lxml
    4. Tạo XML bảng (dùng python-docx)
    5. Chèn XML bảng vào cây lxml (từ cuối lên)
    6. Tạo output_docx.zip, copy tất cả file từ gốc
    7. Ghi đè word/document.xml đã chỉnh sửa vào output_docx.zip
    """
    
    # (Các phương thức add_evaluation_table, _set_cell_border, _set_cell_background
    # giữ nguyên y hệt như file gốc của bạn)
    
    @staticmethod
    def add_evaluation_table(doc: Document, question_num: int, 
                            evaluation_result: Dict):
        """
        Thêm bảng đánh giá 3 hàng × 2 cột
        (GIỮ NGUYÊN)
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
        """Set border cho cell (GIỮ NGUYÊN)"""
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
        """Set background color cho cell (GIỮ NGUYÊN)"""
        cell_properties = cell._element.get_or_add_tcPr()
        cell_shading = OxmlElement('w:shd')
        cell_shading.set(qn('w:fill'), color_hex)
        cell_properties.append(cell_shading)
    
    
    @staticmethod
    def create_output_docx(input_docx: str, questions_results: Dict[int, Dict],
                          output_path: str):
        """
        WORKFLOW (FIXED V7): Thao tác ZIP/XML trực tiếp
        """
        from process.EnhancedDocx import EnhancedDocxParser
        # Bỏ shutil
        
        print(f"\n[DocxWriter] 📋 Bắt đầu tạo file output (Chế độ XML Surgery)...")
        
        # Bước 1: Parse để lấy thông tin vị trí
        print(f"[DocxWriter] 🔍 Đang parse {input_docx} để xác định vị trí...")
        parser = EnhancedDocxParser(input_docx, debug=False)
        questions = parser.parse_questions_with_numbering()
        
        # Lấy namespace từ parser
        namespaces = parser.namespaces
        # Thêm các namespace còn thiếu (nếu có)
        namespaces['w'] = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        
        # Bước 2: Chuẩn bị danh sách vị trí chèn
        insert_positions = []
        for qnum, q_data in questions.items():
            if qnum in questions_results:
                end_para = q_data.get('end_paragraph', -1)
                
                if end_para >= 0:
                    insert_at_index = end_para + 1  # Chèn SAU end_paragraph
                    insert_positions.append({
                        'qnum': qnum,
                        'insert_at_index': insert_at_index,
                        'result': questions_results[qnum]
                    })
                    print(f"[DocxWriter] 📍 Lập kế hoạch chèn Câu {qnum} tại vị trí para {insert_at_index}")
                else:
                    print(f"[DocxWriter] ⚠️ Câu {qnum}: end_paragraph không hợp lệ ({end_para})")
        
        # Bước 3: Sắp xếp từ cuối lên để chèn
        insert_positions.sort(key=lambda x: x['insert_at_index'], reverse=True)
        print(f"\n[DocxWriter] 🔧 Bắt đầu chèn {len(insert_positions)} bảng (từ cuối lên)...")

        try:
            # Bước 4: Mở file ZIP gốc (input)
            with zipfile.ZipFile(input_docx, 'r') as zin:
                # Đọc document.xml
                xml_content = zin.read('word/document.xml')
                
            # Bước 5: Parse XML bằng lxml
            parser_lxml = etree.XMLParser(recover=True, no_network=True)
            root = etree.fromstring(xml_content, parser=parser_lxml)
            
            # Tìm body (thử các namespace phổ biến)
            body = root.find('w:body', namespaces)
            if body is None:
                body = root.find('body') # Fallback
            
            if body is None:
                 raise Exception("Không tìm thấy thẻ <w:body> trong document.xml")

            # Lấy tất cả elements con (paras và tables)
            # Chúng ta phải đếm <w:p> để khớp với index của python-docx
            p_elements = body.findall('.//w:p', namespaces)
            total_paras_xml = len(p_elements)
            print(f"[DocxWriter] 📄 File XML có {total_paras_xml} paragraphs (<w:p>)")

            # Bước 6: Chèn bảng
            for item in insert_positions:
                qnum = item['qnum']
                insert_at_index = item['insert_at_index']
                result = item['result']
                
                # Tạo XML của bảng
                temp_doc = Document()
                DocxWriter.add_evaluation_table(temp_doc, qnum, result)
                table_xml_elements = []
                for element in temp_doc.element.body:
                    if element.tag.endswith('p') or element.tag.endswith('tbl'):
                        table_xml_elements.append(deepcopy(element))
                
                if not any(el.tag.endswith('tbl') for el in table_xml_elements):
                    print(f"[DocxWriter] ⚠️ Không tạo được XML bảng cho Câu {qnum}")
                    continue
                
                # Tìm vị trí chèn trong XML
                if insert_at_index < total_paras_xml:
                    # Tìm <w:p> element mốc
                    target_p_element = p_elements[insert_at_index]
                    
                    # Chèn các elements (para, table, para) vào TRƯỚC mốc
                    for element in reversed(table_xml_elements):
                        target_p_element.addprevious(element)
                    print(f"[DocxWriter] ✅ Đã chèn XML Câu {qnum} tại vị trí {insert_at_index}")
                else:
                    # Chèn vào cuối body
                    for element in table_xml_elements:
                        body.append(element)
                    print(f"[DocxWriter] ✅ Đã thêm XML Câu {qnum} vào cuối body")
            
            # Bước 7: Ghi lại file XML mới
            # Cần khai báo namespaces để lxml giữ lại prefix (w:, m:)
            final_xml = etree.tostring(root, encoding='UTF-8', standalone=True)
            
            # Bước 8: Ghi lại vào ZIP mới (output_path)
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                # Copy tất cả file từ zip gốc (input)
                with zipfile.ZipFile(input_docx, 'r') as zin:
                    for item in zin.infolist():
                        if item.filename != 'word/document.xml':
                            # Copy y hệt file gốc
                            zout.writestr(item, zin.read(item.filename))
                
                # Ghi file document.xml đã bị sửa đổi
                zout.writestr('word/document.xml', final_xml)

            print(f"\n[DocxWriter] 💾 Đã lưu file (bảo toàn media): {output_path}")

        except Exception as e:
            print(f"[DocxWriter] ❌ LỖI NGHIÊM TRỌNG khi thao tác ZIP/XML: {str(e)}")
            import traceback
            traceback.print_exc()
            print(f"[DocxWriter] ⚠️ File output có thể bị hỏng.")