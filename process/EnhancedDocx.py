# -*- coding: utf-8 -*-
import re
import os
import zipfile
import base64
from typing import Dict, List, Tuple, Optional
from docx import Document
from lxml import etree
from collections import defaultdict
import traceback

class EnhancedDocxParser:
    """Parser nâng cao với hỗ trợ câu phụ (1.a, 2.b) và câu tự luận"""
    
    # Định nghĩa các dạng câu hỏi
    QUESTION_TYPE_MULTIPLE_CHOICE = "multiple_choice"
    QUESTION_TYPE_TRUE_FALSE = "true_false"
    QUESTION_TYPE_FILL_BLANK = "fill_blank"
    QUESTION_TYPE_ESSAY = "essay"  # TỰ LUẬN MỚI
    QUESTION_TYPE_UNKNOWN = "unknown"
    
    def __init__(self, docx_path: str, debug: bool = True):
        self.docx_path = docx_path
        self.debug = debug
        
        try:
            self.doc = Document(docx_path)
            self.log(f"✓ Đã load document: {os.path.basename(docx_path)}")
        except Exception as e:
            self.log(f"✗ Lỗi load document: {str(e)}")
            raise
        
        # Lưu trữ media
        self.image_map = {}
        self.equation_map = {}
        
        # Namespace
        self.namespaces = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
            'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
            'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
            'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
            'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
            'v': 'urn:schemas-microsoft-com:vml',
            'o': 'urn:schemas-microsoft-com:office:office',
            'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
        }
        
        try:
            self._load_relationships()
            self._load_media()
        except Exception as e:
            self.log(f"⚠️ Lỗi load media (không ảnh hưởng parsing): {str(e)}")
        try:
            filename = os.path.basename(self.docx_path)
            self.document_type_hint = self._get_document_type_hint(filename)
            self.log(f"✓ Gợi ý loại tài liệu (từ tên file): {self.document_type_hint}")
        except Exception as e:
            self.log(f"⚠️ Lỗi lấy gợi ý tên file: {str(e)}")
            self.document_type_hint = self.QUESTION_TYPE_UNKNOWN
    def log(self, message: str):
        if self.debug:
            print(f"[Parser] {message}")
    
    def _load_relationships(self):
        """Load document relationships với error handling"""
        self.relationships = {}
        try:
            with zipfile.ZipFile(self.docx_path, 'r') as docx_zip:
                if 'word/_rels/document.xml.rels' in docx_zip.namelist():
                    rels_xml = docx_zip.read('word/_rels/document.xml.rels')
                    rels_root = etree.fromstring(rels_xml)
                    
                    for rel in rels_root:
                        rel_id = rel.get('Id')
                        rel_type = rel.get('Type')
                        rel_target = rel.get('Target')
                        
                        if rel_id:
                            self.relationships[rel_id] = {
                                'type': rel_type or '',
                                'target': rel_target or ''
                            }
                    
                    self.log(f"✓ Loaded {len(self.relationships)} relationships")
                else:
                    self.log("⚠️ Không tìm thấy document.xml.rels")
        except Exception as e:
            self.log(f"✗ Lỗi load relationships: {str(e)}")
    
    def _load_media(self):
        """Load tất cả media files với error handling"""
        try:
            with zipfile.ZipFile(self.docx_path, 'r') as docx_zip:
                media_files = [f for f in docx_zip.namelist() 
                              if f.startswith('word/media/')]
                
                self.log(f"✓ Tìm thấy {len(media_files)} media files")
                
                loaded_count = 0
                for media_file in media_files:
                    try:
                        media_data = docx_zip.read(media_file)
                        media_base64 = base64.b64encode(media_data).decode('utf-8')
                        
                        filename = os.path.basename(media_file)
                        file_ext = os.path.splitext(filename)[1].lower()
                        media_type = self._classify_media_type(file_ext)
                        
                        for rid, rel in self.relationships.items():
                            if rel['target'].endswith(filename):
                                self.image_map[rid] = {
                                    'filename': filename,
                                    'base64': media_base64,
                                    'path': media_file,
                                    'extension': file_ext,
                                    'media_type': media_type
                                }
                                loaded_count += 1
                                break
                    
                    except Exception as e:
                        self.log(f"⚠️ Lỗi load {media_file}: {str(e)}")
                        continue
                
                self.log(f"✓ Loaded {loaded_count}/{len(media_files)} media files")
        
        except Exception as e:
            self.log(f"✗ Lỗi load media: {str(e)}")
    
    def _classify_media_type(self, extension: str) -> str:
        """Phân loại media type"""
        equation_formats = ['.wmf', '.emf']
        image_formats = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg']
        
        if extension in equation_formats:
            return 'equation'
        elif extension in image_formats:
            return 'image'
        else:
            return 'other'
    
    def _to_lxml(self, base_oxml_elem):
        """Convert docx element sang lxml với error handling"""
        try:
            xml_bytes = etree.tostring(base_oxml_elem)
            return etree.fromstring(xml_bytes)
        except Exception as e:
            self.log(f"✗ Lỗi convert to lxml: {str(e)}")
            return None
    
    def get_paragraph_numbering(self, paragraph) -> bool:
        """Kiểm tra paragraph có numbering không"""
        try:
            p_element = paragraph._element
            lxml_p = self._to_lxml(p_element)
            if lxml_p is None:
                return False
            
            num_pr = lxml_p.xpath('.//w:numPr', namespaces=self.namespaces)
            return len(num_pr) > 0
        except Exception as e:
            self.log(f"⚠️ Lỗi get numbering: {str(e)}")
            return False
    
    def extract_paragraph_images(self, paragraph) -> List[Dict]:
        """Extract images từ paragraph"""
        images = []
        try:
            p_element = paragraph._element
            lxml_p = self._to_lxml(p_element)
            if lxml_p is None:
                return images
            
            # Modern drawing
            pic_elements = lxml_p.xpath('.//pic:pic//a:blip', namespaces=self.namespaces)
            for blip in pic_elements:
                try:
                    r_embed = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                    if r_embed and r_embed in self.image_map:
                        img_info = self.image_map[r_embed]
                        images.append({
                            'rId': r_embed,
                            'filename': img_info['filename'],
                            'base64': img_info['base64'],
                            'extension': img_info['extension'],
                            'media_type': img_info['media_type']
                        })
                except Exception as e:
                    self.log(f"⚠️ Lỗi extract modern drawing: {str(e)}")
                    continue
            
            # VML drawing
            vml_images = lxml_p.xpath('.//v:imagedata', namespaces=self.namespaces)
            for vml_img in vml_images:
                try:
                    r_id = vml_img.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                    if r_id and r_id in self.image_map:
                        img_info = self.image_map[r_id]
                        images.append({
                            'rId': r_id,
                            'filename': img_info['filename'],
                            'base64': img_info['base64'],
                            'extension': img_info['extension'],
                            'media_type': img_info['media_type']
                        })
                except Exception as e:
                    self.log(f"⚠️ Lỗi extract VML: {str(e)}")
                    continue
            
            # OLE objects
            ole_objects = lxml_p.xpath('.//o:OLEObject', namespaces=self.namespaces)
            for ole in ole_objects:
                try:
                    r_id = ole.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                    ole_type = ole.get('Type', '')
                    if r_id and r_id in self.image_map:
                        img_info = self.image_map[r_id]
                        images.append({
                            'rId': r_id,
                            'filename': img_info['filename'],
                            'base64': img_info['base64'],
                            'extension': img_info['extension'],
                            'media_type': 'ole_equation',
                            'ole_type': ole_type
                        })
                except Exception as e:
                    self.log(f"⚠️ Lỗi extract OLE: {str(e)}")
                    continue
        
        except Exception as e:
            self.log(f"⚠️ Lỗi extract images: {str(e)}")
        
        return images
    
    def extract_paragraph_equations(self, paragraph) -> List[Dict]:
        """Extract equations từ paragraph"""
        equations = []
        try:
            p_element = paragraph._element
            lxml_p = self._to_lxml(p_element)
            if lxml_p is None:
                return equations
            
            # MathML
            math_elements = lxml_p.xpath('.//m:oMath', namespaces=self.namespaces)
            for math_elem in math_elements:
                try:
                    math_text = self._extract_math_text(math_elem)
                    if math_text:
                        equations.append({
                            'type': 'mathml',
                            'content': math_text,
                            'xml': etree.tostring(math_elem, encoding='unicode')[:200]
                        })
                except Exception as e:
                    self.log(f"⚠️ Lỗi extract MathML: {str(e)}")
                    continue
            
            # Equation field codes
            fld_simple = lxml_p.xpath('.//w:fldSimple', namespaces=self.namespaces)
            for fld in fld_simple:
                try:
                    instr = fld.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}instr', '')
                    if 'EQ' in instr or 'EMBED' in instr:
                        equations.append({
                            'type': 'field_code',
                            'content': instr
                        })
                except Exception as e:
                    self.log(f"⚠️ Lỗi extract field code: {str(e)}")
                    continue
        
        except Exception as e:
            self.log(f"⚠️ Lỗi extract equations: {str(e)}")
        
        return equations
    
    
    
    
    def _extract_math_text(self, math_elem) -> str:
        """Extract text từ MathML"""
        try:
            texts = math_elem.xpath('.//m:t/text()', namespaces=self.namespaces)
            return ''.join(texts).strip()
        except:
            return ""
    
    def _get_document_type_hint(self, filename: str) -> str:
        """
        Phân tích tên file để đưa ra gợi ý về loại câu hỏi (TL, TN)
        """
        try:
            filename_lower = filename.lower()
            
            # Tự luận / Tự luận Học liệu
            if filename_lower.startswith('tl_hl_') or filename_lower.startswith('tl_'):
                self.log(f"   [Hint] Phát hiện Tự Luận (TL/TL_HL) từ tên file.")
                return self.QUESTION_TYPE_ESSAY
            
            # Trắc nghiệm
            if filename_lower.startswith('tn_'):
                self.log(f"   [Hint] Phát hiện Trắc Nghiệm (TN) từ tên file.")
                return self.QUESTION_TYPE_MULTIPLE_CHOICE
            
            return self.QUESTION_TYPE_UNKNOWN
        
        except Exception as e:
            self.log(f"⚠️ Lỗi _get_document_type_hint: {str(e)}")
            return self.QUESTION_TYPE_UNKNOWN
    
    
    def _detect_question_type(self, text: str) -> str:
        """Phát hiện dạng câu hỏi - CẢI TIẾN hỗ trợ tự luận"""
        try:
            # Điền khuyết: có [[...]]
            if re.search(r'\[\[.*?\]\]', text):
                return self.QUESTION_TYPE_FILL_BLANK
            
            # --- BẮT ĐẦU KHỐI SỬA ---
            # (Sửa lỗi: Phân biệt MULTIPLE_CHOICE (A.) và TRUE_FALSE (a.))

            # Ưu tiên 1: Trắc nghiệm (A. B. C. D.)
            # Đây là tín hiệu mạnh nhất, phải được check trước.
            has_uppercase_options = bool(re.search(r'\b[A-D]\.', text))
            if has_uppercase_options:
                return self.QUESTION_TYPE_MULTIPLE_CHOICE
            
            # Ưu tiên 2: Đúng/Sai (a. b. c. d.)
            # Tín hiệu yếu hơn, chỉ tìm chữ thường.
            # SỬA LỖI: Bỏ re.IGNORECASE để phân biệt 'A.' và 'a.'
            has_lowercase_options = bool(re.search(r'\b[a-d][\.\)]', text))
            
            is_true_false_check = has_lowercase_options and not (
                text.strip().startswith('A.') or
                text.strip().startswith('B.') or
                text.strip().startswith('C.') or
                text.strip().startswith('D.')
            )

            if is_true_false_check:
                 return self.QUESTION_TYPE_TRUE_FALSE
            
            # --- KẾT THÚC KHỐI SỬA ---

            # Tự luận: không có đáp án trắc nghiệm
            # Thường có từ khóa: "Giải thích", "Trình bày", "Chứng minh", "Phân tích"
            
            # SỬA: Bổ sung keywords từ các file Tự luận (TL_TOAN7...)
            essay_keywords = ['giải thích', 'trình bày', 'chứng minh', 'phân tích', 
                    'tính toán', 'nêu', 'cho biết', 'hãy', 'tìm',
                    'so sánh', 'thực hiện'] 
            
            text_lower = text.lower()
            if any(keyword in text_lower for keyword in essay_keywords):
                return self.QUESTION_TYPE_ESSAY
            
            return self.QUESTION_TYPE_UNKNOWN
        except Exception as e:
            self.log(f"⚠️ Lỗi detect question type: {str(e)}")
            return self.QUESTION_TYPE_UNKNOWN
    
    def _parse_question_number(self, text: str, in_question_context: bool = False) -> Optional[str]:
        """
        Parse số câu hỏi - HỖ TRỢ CẢ CÂU PHỤ
        
        [FIX V13]: Thêm tham số 'in_question_context'.
        Nếu True, chỉ chạy các pattern mạnh (Câu X, Bài X)
        để tránh "xé nhỏ" câu hỏi.
        """
        try:
            text_stripped = text.strip()
            
            # Pattern 1: "Câu X" hoặc "Câu X.Y" (Mạnh)
            match = re.match(r'^\s*`{0,3}\s*\*?\*?\s*(?:\[.*?\])?\s*Câu\s+(\d+(?:\.[a-z])?)\s*[:\.\)]?\s*\*?\*?',
                           text_stripped, re.IGNORECASE)
            if match:
                return match.group(1)
            
            # Pattern 2: "Question X" hoặc "Question X.Y" (Mạnh)
            match = re.match(r'^\s*`{0,3}\s*Question\s+(\d+(?:\.[a-z])?)\s*[:\.\)]?',
                           text_stripped, re.IGNORECASE)
            if match:
                return match.group(1)
            
            # Pattern 3: "Bài X" hoặc "Bài X.Y" (Mạnh)
            match = re.match(r'^\s*`{0,3}\s*Bài\s+(\d+(?:\.[a-z])?)\s*[:\.\)]?',
                           text_stripped, re.IGNORECASE)
            if match:
                return match.group(1)
            
            # === CÁC PATTERN YẾU ===
            # Chỉ chạy các pattern này nếu chúng ta KHÔNG ở trong 1 câu hỏi
            if not in_question_context:
                
                # Pattern 4: Chỉ số và chữ cái "X.Y" (ví dụ: "1.a", "2.b") (Yếu)
                match = re.match(r'^\s*`{0,3}\s*(\d+\.[a-z])\s*[\.\)\-]\s+',
                               text_stripped)
                if match:
                    return match.group(1)
                
                # Pattern 5: Chỉ số "X." hoặc "X)" (ví dụ: "1.", "2)") (Yếu)
                match = re.match(r'^\s*`{0,3}\s*(\d+)\s*[\.\)\-]\s+\w',
                               text_stripped)
                if match:
                    return match.group(1)
            
            return None
        except Exception as e:
            self.log(f"⚠️ Lỗi parse question number: {str(e)}")
            return None
    
    def _is_solution_start_marker(self, text: str) -> bool:
        """Kiểm tra marker bắt đầu lời giải"""
        try:
            text_lower = text.lower().strip()
            
            solution_markers = [
                'lời giải',
                'giải:',
                'đáp án:',
                'hướng dẫn:',
                'giải thích:',
                'phân tích:',
                'bài giải:',
                'lời giải ####',
                'lời giải chi tiết',
                'cách giải:',
                'phương pháp:'
            ]
            
            if text_lower.startswith('lời giải'):
                return True
            
            if re.match(r'^[=\-*]{3,}.*?(lời giải|giải|đáp án).*?[=\-*]{3,}', text_lower):
                return True
            
            return False
        except Exception as e:
            self.log(f"⚠️ Lỗi check solution marker: {str(e)}")
            return False
    
    def _is_solution_end_marker(self, text: str) -> bool:
        """Kiểm tra marker kết thúc lời giải"""
        try:
            text_lower = text.lower().strip()
            
            end_markers = [
                'hết lời giải',
                'kết thúc lời giải',
                '--- hết ---',
                '=== hết ===',
                'end solution',
                'vậy đáp án là',
                'chọn đáp án',
                'đáp án đúng là',
                'suy ra đáp án đúng là',
                'vậy đáp án đúng là',
                'vậy đáp án sai là'
            ]
            
            for marker in end_markers:
                if marker in text_lower:
                    return True
            
            if text_lower.endswith('```'):
                return True

            return False
        except Exception as e:
            return False
    
    def _is_next_question_marker(self, text: str) -> bool:
        """Kiểm tra có phải câu hỏi mới không - CẢI TIẾN"""
        return self._parse_question_number(text) is not None
    
    def parse_questions_with_numbering(self) -> Dict[str, Dict]:
        """
        Parse câu hỏi - HỖ TRỢ CÂU PHỤ (1.a, 2.b) VÀ HỌC LIỆU (CONTEXT)
        
        Returns:
            Dict[str, Dict]: Key là string (ví dụ: "1", "1.a", "2", "2.c")
        """
        questions = {}
        current_question_id = None
        current_question_data = self._init_question_data()
        
        # Trạng thái
        in_question = False
        in_solution = False
        paragraphs_after_question = 0
        solution_end_paragraph = None
        
        # Context (Học liệu)
        current_context = []
        
        self.log("\n" + "="*70)
        self.log("BẮT ĐẦU PARSE CÂU HỎI V11 - HỖ TRỢ CÂU PHỤ & TỰ LUẬN")
        self.log("="*70)
        
        try:
            total_paragraphs = len(self.doc.paragraphs)
            self.log(f"✓ Tổng số paragraphs: {total_paragraphs}")
            
            if total_paragraphs == 0:
                self.log("✗ Document không có paragraph nào!")
                return questions
            
            for idx, para in enumerate(self.doc.paragraphs):
                try:
                    text = para.text.strip()
                    # Bỏ qua các dòng trống ngay từ đầu
                    if not text:
                        continue
                        
                    has_numbering = self.get_paragraph_numbering(para)
                    text_lower = text.lower()
                    
                    # ===============================================
                    # ƯU TIÊN 1: PHÁT HIỆN CONTEXT RESET (HỌC LIỆU / PHẦN)
                    # ===============================================
                    # === START FIX (P3) ===
                    is_context_reset = (
                        text_lower.startswith('học liệu') or 
                        text_lower.startswith('chủ đề') or
                        re.match(r'^\s*phần\s+[ivx\d]+\b', text_lower)
                    )
                    # === END FIX (P3) ===
                    
                    if is_context_reset:
                        # === LƯU CÂU CŨ TRƯỚS KHI RESET ===
                        if current_question_id is not None:
                            if solution_end_paragraph is not None:
                                current_question_data['end_paragraph'] = solution_end_paragraph
                            else:
                                current_question_data['end_paragraph'] = idx - 1
                            
                            questions[current_question_id] = current_question_data.copy()
                            self.log(f"✅ Lưu Câu {current_question_id} (trước context mới)")
                            
                            # Reset
                            current_question_id = None
                            current_question_data = self._init_question_data()
                        
                        # === RESET CONTEXT MỚI ===
                        current_context = [text]
                        self.log(f"\n   [Context] 🔄 RESET Context (Học liệu/Phần mới) -> {text[:50]}...")
                        
                        in_question = False 
                        in_solution = False
                        
                        continue # Đọc paragraph tiếp theo
                    
                    # ===============================================
                    # ƯU TIÊN 2: PHÁT HIỆN CÂU HỎI MỚI ("CÂU X")
                    # ===============================================
                    question_id = self._parse_question_number(text, in_question)
                    
                    if question_id is not None:
                        
                        # --- Xử lý ID trùng lặp ---
                        original_question_id = question_id
                        suffix_num = 0
                        while question_id in questions:
                            suffix_num += 1
                            suffix_char = chr(96 + suffix_num) # (a=97)
                            question_id = f"{original_question_id}.{suffix_char}"
                        
                        if original_question_id != question_id:
                            self.log(f"   ⚠️ Phát hiện ID trùng lặp ('{original_question_id}'), đổi tên -> {question_id}")
                        
                        # --- Lưu câu cũ ---
                        if current_question_id is not None:
                            if solution_end_paragraph is not None:
                                current_question_data['end_paragraph'] = solution_end_paragraph
                            else:
                                current_question_data['end_paragraph'] = idx - 1
                            
                            questions[current_question_id] = current_question_data.copy()
                            self.log(f"✅ Lưu Câu {current_question_id} "
                                    f"[{current_question_data['start_paragraph']} -> {current_question_data['end_paragraph']}] "
                                    f"(Loại: {current_question_data['question_type']}) "
                                    f"(Lời giải: {'Có' if current_question_data['solution_text'] else 'Không'})")
                        
                        # --- Bắt đầu câu mới ---
                        current_question_id = question_id
                        current_question_data = self._init_question_data()
                        
                        # --- Gộp "Học liệu" (current_context) vào ---
                        combined_question_text = []
                        if current_context:
                            combined_question_text.extend(current_context)
                        
                        if text:
                            combined_question_text.append(text)
                        
                        current_question_data['question_text'] = combined_question_text
                        
                        # --- Cập nhật trạng thái ---
                        current_question_data['source'] = f'paragraph_{idx}'
                        current_question_data['start_paragraph'] = idx
                        detected_type_on_start = self._detect_question_type(text)
                        
                        # Ưu tiên 1: Lấy loại từ text (nếu khác UNKNOWN)
                        if detected_type_on_start != self.QUESTION_TYPE_UNKNOWN:
                            current_question_data['question_type'] = detected_type_on_start
                        # Ưu tiên 2: Lấy loại từ GỢI Ý TÊN FILE
                        elif self.document_type_hint != self.QUESTION_TYPE_UNKNOWN:
                            current_question_data['question_type'] = self.document_type_hint
                            self.log(f"   ✓ Gán loại (từ Tên file) -> {self.document_type_hint}")
                        # Ưu tiên 3: Mặc định là UNKNOWN
                        else:
                            current_question_data['question_type'] = self.QUESTION_TYPE_UNKNOWN
                        current_question_data['question_id'] = question_id
                        
                        in_question = True
                        in_solution = False
                        solution_end_paragraph = None
                        paragraphs_after_question = 0
                        
                        self.log(f"\n📝 Phát hiện Câu {question_id} tại para {idx}")
                        
                        # --- Extract media ---
                        para_images = self.extract_paragraph_images(para)
                        para_equations = self.extract_paragraph_equations(para)
                        self._add_images_to_section(current_question_data, para_images, 'question')
                        current_question_data['question_equations'].extend(para_equations)
                        
                        continue # Đã xử lý, đọc paragraph tiếp theo
                    
                    # ===============================================
                    # ƯU TIÊN 3: XỬ LÝ NỘI DUNG BÊN TRONG CÂU HỎI
                    # ===============================================
                    if in_question and current_question_id is not None:
                        paragraphs_after_question += 1
                        
                        # Bỏ qua metadata
                        if text.startswith('[') and text.endswith(']'):
                            continue
                        
                        # Bỏ qua tiêu đề
                        if re.match(r'^[IVX]+\.\s*\w+', text):
                            continue

                        # --- Kiểm tra bắt đầu lời giải ---
                        if not in_solution and self._is_solution_start_marker(text):
                            in_solution = True
                            solution_end_paragraph = idx
                            self.log(f"   📘 BẮT ĐẦU LỜI GIẢI tại para {idx}")
                            current_question_data['solution_text'].append(text)
                            current_question_data['solution_start_paragraph'] = idx
                            
                            para_images = self.extract_paragraph_images(para)
                            para_equations = self.extract_paragraph_equations(para)
                            self._add_images_to_section(current_question_data, para_images, 'solution')
                            current_question_data['solution_equations'].extend(para_equations)
                            continue
                        
                        # === START FIX (P4) ===
                        # Vô hiệu hóa logic kiểm tra kết thúc lời giải
                        # Một câu hỏi/lời giải chỉ kết thúc khi gặp
                        # (ƯU TIÊN 1) hoặc (ƯU TIÊN 2)
                        
                        # --- Kiểm tra kết thúc lời giải ---
                        # if in_solution and self._is_solution_end_marker(text):
                        #     solution_end_paragraph = idx
                        #     current_question_data['solution_text'].append(text)
                        #     self.log(f"   📕 KẾT THÚC LỜI GIẢI tại para {idx}")
                        #     in_solution = False
                        #     in_question = False # Kết thúc câu
                        #     continue
                        
                        # === END FIX (P4) ===
                        
                        # --- Thu thập content (nếu text có nội dung) ---
                        if text:
                            para_images = self.extract_paragraph_images(para)
                            para_equations = self.extract_paragraph_equations(para)
                            
                            if in_solution:
                                current_question_data['solution_text'].append(text)
                                solution_end_paragraph = idx # LUÔN CẬP NHẬT
                                self._add_images_to_section(current_question_data, para_images, 'solution')
                                current_question_data['solution_equations'].extend(para_equations)
                            else:
                                current_question_data['question_text'].append(text)
                                self._add_images_to_section(current_question_data, para_images, 'question')
                                current_question_data['question_equations'].extend(para_equations)
                                
                                # Cập nhật loại câu hỏi
                                detected_type = self._detect_question_type(text)
                                current_type = current_question_data['question_type']
                                
                                # Tín hiệu mạnh nhất (MC, FB) luôn ghi đè
                                strongest_signals = [self.QUESTION_TYPE_MULTIPLE_CHOICE, 
                                                     self.QUESTION_TYPE_FILL_BLANK]

                                if detected_type in strongest_signals:
                                    if current_type != detected_type:
                                        self.log(f"   ✓ Cập nhật loại (Tín hiệu mạnh) -> {detected_type}")
                                        current_question_data['question_type'] = detected_type
                                
                                # Xử lý tín hiệu ESSAY
                                elif detected_type == self.QUESTION_TYPE_ESSAY:
                                    if current_type == self.QUESTION_TYPE_UNKNOWN:
                                        self.log(f"   ✓ Cập nhật loại (Tín hiệu Essay) -> {detected_type}")
                                        current_question_data['question_type'] = detected_type
                                
                                # Xử lý tín hiệu TRUE_FALSE
                                elif detected_type == self.QUESTION_TYPE_TRUE_FALSE:
                                    # Chỉ cập nhật nếu loại hiện tại là UNKNOWN
                                    # (KHÔNG ghi đè lên ESSAY, vì a) b) có thể là 1 phần của câu tự luận)
                                    if current_type == self.QUESTION_TYPE_UNKNOWN:
                                        self.log(f"   ✓ Cập nhật loại (Tín hiệu TF) -> {detected_type}")
                                        current_question_data['question_type'] = detected_type
                        
                        # --- Giới hạn an toàn ---
                        if paragraphs_after_question > 50:
                            self.log(f"   ⚠️ Quá 50 paragraphs, dừng câu {current_question_id}")
                            in_question = False
                            in_solution = False
                        
                        continue # Đã xử lý (hoặc bỏ qua), đọc paragraph tiếp theo

                    # ===============================================
                    # ƯU TIÊN 4: THÊM VÀO CONTEXT (NẾU KHÔNG PHẢI 3 ƯU TIÊN TRÊN)
                    # ===============================================
                    # (Đang ở ngoài câu hỏi, và có 1 context đang active)
                    if not in_question and current_context and text:
                         # Bỏ qua các marker [VD] hoặc dòng trống
                        if not text.startswith('[') and not text.startswith('='):
                            current_context.append(text)
                            self.log(f"   [Context] Thêm vào Context -> {text[:50]}...")
                            continue # Đọc paragraph tiếp theo
                    
                    # (Tất cả các dòng rác khác sẽ bị bỏ qua ở đây)

                except Exception as e:
                    self.log(f"✗ Lỗi xử lý paragraph {idx}: {str(e)}")
                    self.log(traceback.format_exc())
                    continue
            
            # --- Lưu câu cuối cùng ---
            if current_question_id is not None:
                if solution_end_paragraph is not None:
                    current_question_data['end_paragraph'] = solution_end_paragraph
                else:
                    current_question_data['end_paragraph'] = len(self.doc.paragraphs) - 1
                
                questions[current_question_id] = current_question_data
                self.log(f"✅ Lưu Câu {current_question_id} (cuối) "
                        f"[{current_question_data['start_paragraph']} -> {current_question_data['end_paragraph']}] "
                        f"(Loại: {current_question_data['question_type']})")
            
            self.log("\n" + "="*70)
            self.log(f"KẾT QUẢ: {len(questions)} câu hỏi")
            
            # Thống kê loại câu
            type_counts = defaultdict(int)
            for q in questions.values():
                type_counts[q['question_type']] += 1
            
            self.log("THỐNG KÊ LOẠI CÂU:")
            for qtype, count in type_counts.items():
                self.log(f"  - {qtype}: {count} câu")
            
            self.log("="*70)
            
        except Exception as e:
            self.log(f"✗ LỖI NGHIÊM TRỌNG trong parse_questions: {str(e)}")
            self.log(traceback.format_exc())
        
        return questions
    
    def _init_question_data(self) -> Dict:
        """Khởi tạo cấu trúc dữ liệu câu hỏi"""
        return {
            'question_id': '',  # MỚI: ID câu hỏi (có thể là "1.a")
            'question_text': [],
            'question_images': [],
            'question_images_formula': [],
            'question_images_illustration': [],
            'question_equations': [],
            'solution_text': [],
            'solution_images': [],
            'solution_images_formula': [],
            'solution_images_illustration': [],
            'solution_equations': [],
            'source': '',
            'question_type': self.QUESTION_TYPE_UNKNOWN,
            'start_paragraph': -1,
            'end_paragraph': -1,
            'solution_start_paragraph': -1
        }
    
    def _add_images_to_section(self, question_data: dict, images: List[Dict], section: str):
        """Thêm ảnh vào section"""
        try:
            prefix = f"{section}_"
            
            for img in images:
                question_data[f'{prefix}images'].append(img)
                media_type = img.get('media_type', 'other')
                
                if media_type == 'equation' or media_type == 'ole_equation':
                    question_data[f'{prefix}images_formula'].append(img)
                elif media_type == 'image':
                    question_data[f'{prefix}images_illustration'].append(img)
        except Exception as e:
            self.log(f"⚠️ Lỗi add images to section: {str(e)}")
    
    def get_statistics(self) -> Dict:
        """Thống kê với error handling"""
        try:
            numbered_count = sum(1 for p in self.doc.paragraphs if self.get_paragraph_numbering(p))
            
            total_images = len(self.image_map)
            formula_images = sum(1 for img in self.image_map.values() if img['media_type'] == 'equation')
            illustration_images = sum(1 for img in self.image_map.values() if img['media_type'] == 'image')
            other_images = sum(1 for img in self.image_map.values() if img['media_type'] == 'other')
            
            stats = {
                'total_paragraphs': len(self.doc.paragraphs),
                'numbered_paragraphs': numbered_count,
                'total_tables': len(self.doc.tables),
                'total_images': total_images,
                'formula_images': formula_images,
                'illustration_images': illustration_images,
                'other_images': other_images,
                'file_path': self.docx_path
            }
            
            return stats
        except Exception as e:
            self.log(f"✗ Lỗi tính thống kê: {str(e)}")
            return {
                'total_paragraphs': 0,
                'numbered_paragraphs': 0,
                'total_tables': 0,
                'total_images': 0,
                'formula_images': 0,
                'illustration_images': 0,
                'other_images': 0,
                'file_path': self.docx_path,
                'error': str(e)
            }

    def detect_question_dependencies(self, questions: Dict) -> Dict:
        """
        Phát hiện quan hệ phụ thuộc giữa các câu - THÔNG MINH
        
        Quy tắc:
        - Câu phụ (1.a, 2.b) LUÔN phụ thuộc câu trước
        - Câu tự luận (essay) LUÔN phụ thuộc câu trước (trừ câu đầu)
        - Câu trắc nghiệm KHÔNG phụ thuộc
        
        Returns:
            Dict[qid] = {
                'depends_on': list,  # Danh sách câu phụ thuộc
                'context_questions': list,  # Câu cần gửi context cho AI
            }
        """
        dependencies = {}
        sorted_qids = self._sort_question_ids_for_dependency(list(questions.keys()))
        
        for idx, qid in enumerate(sorted_qids):
            q_data = questions[qid]
            q_type = q_data.get('question_type', self.QUESTION_TYPE_UNKNOWN)
            
            dependencies[qid] = {
                'depends_on': [],
                'context_questions': []
            }
            
            # === QUY TẮC 1: Câu phụ (1.a, 2.b, ...) ===
            match = re.match(r'^(\d+)\.([a-z])$', qid)
            if match:
                parent_num = match.group(1)
                sub_letter = match.group(2)
                
                # Tìm tất cả câu phụ trước đó của cùng câu cha
                for prev_qid in sorted_qids[:idx]:
                    prev_match = re.match(r'^(\d+)\.([a-z])$', prev_qid)
                    if prev_match and prev_match.group(1) == parent_num:
                        prev_letter = prev_match.group(2)
                        if prev_letter < sub_letter:
                            dependencies[qid]['depends_on'].append(prev_qid)
                            dependencies[qid]['context_questions'].append(prev_qid)
                
                # Thêm câu cha (nếu tồn tại)
                if parent_num in questions:
                    dependencies[qid]['depends_on'].append(parent_num)
                    dependencies[qid]['context_questions'].append(parent_num)
            
            # === QUY TẮC 2: Câu tự luận (1, 2, 3, ...) ===
            elif q_type == self.QUESTION_TYPE_ESSAY:
                # Tìm câu trước đó (cùng nhóm)
                if idx > 0:
                    prev_qid = sorted_qids[idx - 1]
                    prev_q_data = questions[prev_qid]
                    prev_type = prev_q_data.get('question_type', self.QUESTION_TYPE_UNKNOWN)
                    
                    # Chỉ phụ thuộc nếu câu trước cũng là tự luận
                    if prev_type == self.QUESTION_TYPE_ESSAY:
                        dependencies[qid]['depends_on'].append(prev_qid)
                        dependencies[qid]['context_questions'].append(prev_qid)
            
            # === QUY TẮC 3: Trắc nghiệm → Không phụ thuộc ===
            # (Đã mặc định rỗng ở trên)
        
        return dependencies

    def build_context_for_question(self, questions: Dict, current_qid: str) -> str:
        """
        Xây dựng context CHỈ cho câu CÙNG HỌC LIỆU
        
        Logic:
        - Chỉ áp dụng cho Tự luận
        - Phát hiện học liệu của câu hiện tại (từ question_text)
        - Chỉ lấy các câu CÙNG học liệu đó
        
        Returns:
            str: Context text (hoặc rỗng nếu không cần)
        """
        current_q = questions.get(current_qid)
        if not current_q:
            return ""
        
        # Chỉ xử lý tự luận
        q_type = current_q.get('question_type', self.QUESTION_TYPE_UNKNOWN)
        if q_type != self.QUESTION_TYPE_ESSAY:
            return ""
        
        # === BƯỚC 1: Xác định học liệu của câu hiện tại ===
        current_hoc_lieu = self._extract_hoc_lieu_from_question(current_q)
        
        if not current_hoc_lieu:
            # Không có học liệu → không cần context
            return ""
        
        # Sắp xếp câu theo thứ tự
        sorted_qids = self._sort_question_ids_for_dependency(list(questions.keys()))
        
        # Tìm vị trí câu hiện tại
        try:
            current_idx = sorted_qids.index(current_qid)
        except ValueError:
            return ""
        
        # Nếu là câu đầu tiên trong học liệu → Không có context
        if current_idx == 0:
            return ""
        
        # === BƯỚC 2: Lấy CÁC CÂU TRƯỚC CÙNG HỌC LIỆU ===
        context_qids = []
        
        for prev_qid in sorted_qids[:current_idx]:
            prev_q = questions[prev_qid]
            prev_type = prev_q.get('question_type', self.QUESTION_TYPE_UNKNOWN)
            
            # Chỉ lấy câu tự luận
            if prev_type != self.QUESTION_TYPE_ESSAY:
                continue
            
            # Kiểm tra cùng học liệu
            prev_hoc_lieu = self._extract_hoc_lieu_from_question(prev_q)
            
            if prev_hoc_lieu == current_hoc_lieu:
                context_qids.append(prev_qid)
        
        # === BƯỚC 3: Xây dựng context text ===
        if not context_qids:
            return ""
        
        context_text = "\n\n" + "="*70
        context_text += f"\nCONTEXT - CÁC CÂU TRƯỚC ({current_hoc_lieu})"
        context_text += "\n" + "="*70
        context_text += "\n[LƯU Ý]: Câu hiện tại CÓ THỂ phụ thuộc hoặc ĐỘC LẬP với các câu dưới đây."
        context_text += f"\n[QUAN TRỌNG]: Tất cả câu dưới đây đều thuộc {current_hoc_lieu}."
        context_text += "\n" + "="*70 + "\n"
        
        for ctx_qid in context_qids:
            ctx_q = questions[ctx_qid]
            
            context_text += f"\n### Câu {ctx_qid}:\n"
            
            # Thêm đề bài (BỎ QUA dòng "Học liệu X" / "Phần X")
            if ctx_q.get('question_text'):
                question_lines = ctx_q.get('question_text', [])
                filtered_lines = []
                for line in question_lines:
                    # === START FIX (P3) ===
                    line_lower = line.lower().strip()
                    if not (line_lower.startswith('học liệu') or 
                            line_lower.startswith('chủ đề') or 
                            re.match(r'^\s*phần\s+[ivx\d]+\b', line_lower)):
                        filtered_lines.append(line)
                    # === END FIX (P3) ===
                
                context_text += "\n".join(filtered_lines)
            
            # Thêm lời giải
            if ctx_q.get('solution_text'):
                context_text += f"\n\n[Lời giải Câu {ctx_qid}]:\n"
                solution_lines = ctx_q.get('solution_text', [])
                
                cleaned_solution = []
                for line in solution_lines:
                    line_stripped = line.strip()
                    if line_stripped and \
                    not line_stripped.lower().startswith('lời giải') and \
                    not all(c in '=-*#' for c in line_stripped):
                        cleaned_solution.append(line)
                
                context_text += "\n".join(cleaned_solution)
            else:
                context_text += "\n\n[Câu này KHÔNG CÓ lời giải]"
            
            # Thông tin ảnh
            if ctx_q.get('question_images') or ctx_q.get('solution_images'):
                img_count = len(ctx_q.get('question_images', [])) + len(ctx_q.get('solution_images', []))
                context_text += f"\n[Câu này có {img_count} hình ảnh]"
            
            context_text += "\n" + "─"*70 + "\n"
        
        return context_text


    def _get_question_group(self, qid: str) -> str:
        """
        Lấy nhóm của câu hỏi
        
        Ví dụ:
        - "1" → "1"
        - "1.a" → "1"
        - "2.b" → "2"
        """
        match = re.match(r'^(\d+)', qid)
        if match:
            return match.group(1)
        return qid

    def _sort_question_ids_for_dependency(self, question_ids: list) -> list:
        """Sắp xếp câu hỏi (1, 1.a, 1.b, 2, 2.a, ...)"""
        def parse_id(qid):
            match = re.match(r'^(\d+)(?:\.([a-z]))?$', str(qid))
            if match:
                main_num = int(match.group(1))
                sub_letter = match.group(2) if match.group(2) else ''
                return (main_num, sub_letter)
            try:
                return (int(qid), '')
            except:
                return (999999, str(qid))
        
        return sorted(question_ids, key=parse_id)
    def _extract_hoc_lieu_from_question(self, question_data: Dict) -> str:
        """
        Trích xuất tên học liệu từ question_text
        
        VD: 
        - "Học liệu 1. Người ta dùng..." → "Học liệu 1"
        - "Học liệu 2. Cho tam giác..." → "Học liệu 2"
        - "Chủ đề A. ..." → "Chủ đề A"
        - "PHẦN I. TRẮC NGHIỆM" -> "Phần I"
        
        Returns:
            str: Tên học liệu (hoặc rỗng nếu không tìm thấy)
        """
        question_text = question_data.get('question_text', [])
        
        if not question_text:
            return ""
        
        # Kiểm tra dòng đầu tiên
        first_line = question_text[0].strip().lower()
        
        # Pattern: "Học liệu 1", "Chủ đề A", "Phần I"
        import re
        # === START FIX (P3) ===
        match = re.match(r'^(học liệu \d+|chủ đề [a-z0-9]+|phần\s+[ivx\d]+)', first_line, re.IGNORECASE)
        # === END FIX (P3) ===
        
        if match:
            return match.group(1).title()  # "Học Liệu 1", "Chủ Đề A", "Phần I"
        
        # Kiểm tra các dòng tiếp theo (phòng trường hợp dòng đầu là số câu)
        for line in question_text[:3]:  # Chỉ check 3 dòng đầu
            line_stripped = line.strip().lower()
            # === START FIX (P3) ===
            match = re.match(r'^(học liệu \d+|chủ đề [a-z0-9]+|phần\s+[ivx\d]+)', line_stripped, re.IGNORECASE)
            # === END FIX (P3) ===
            if match:
                return match.group(1).title()
        
        return ""