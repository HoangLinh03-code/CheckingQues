"""
EnhancedDocxParser V8 - FIX DIVISION BY ZERO ERROR
Cải tiến:
- Xử lý an toàn các phép chia
- Thêm error handling toàn diện
- Log chi tiết để debug
"""

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
    """Parser nâng cao với xử lý lỗi an toàn"""
    
    # Định nghĩa các dạng câu hỏi
    QUESTION_TYPE_MULTIPLE_CHOICE = "multiple_choice"
    QUESTION_TYPE_TRUE_FALSE = "true_false"
    QUESTION_TYPE_FILL_BLANK = "fill_blank"
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
            self.log(traceback.format_exc())
    
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
                    r_id = ole.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
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
    
    def _detect_question_type(self, text: str) -> str:
        """Phát hiện dạng câu hỏi"""
        try:
            # Điền khuyết: có [[...]]
            if re.search(r'\[\[.*?\]\]', text):
                return self.QUESTION_TYPE_FILL_BLANK
            
            # Đúng/Sai: có a), b), c), d) và không có A. B. C. D.
            has_lowercase_options = bool(re.search(r'\b[a-d]\)', text, re.IGNORECASE))
            has_uppercase_options = bool(re.search(r'\b[A-D]\.', text))
            
            if has_lowercase_options and not has_uppercase_options:
                return self.QUESTION_TYPE_TRUE_FALSE
            
            # Trắc nghiệm: có A. B. C. D.
            if has_uppercase_options:
                return self.QUESTION_TYPE_MULTIPLE_CHOICE
            
            return self.QUESTION_TYPE_UNKNOWN
        except Exception as e:
            self.log(f"⚠️ Lỗi detect question type: {str(e)}")
            return self.QUESTION_TYPE_UNKNOWN
    
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
                'lời giải ####'
            ]
            
            for marker in solution_markers:
                if text_lower.startswith(marker):
                    return True
            
            return False
        except Exception as e:
            self.log(f"⚠️ Lỗi check solution marker: {str(e)}")
            return False
    
    def _is_next_question_marker(self, text: str) -> bool:
        """Kiểm tra marker câu hỏi tiếp theo"""
        try:
            patterns = [
                r'^\s*\*?\*?\s*(?:\[.*?\])?\s*Câu\s+(\d+)\s*[:\.]?\s*\*?\*?',
                r'^\s*Question\s+(\d+)\s*[:\.]?',
                r'^\s*(\d+)\s*[\.\)\-]\s+',
            ]
            
            for pattern in patterns:
                if re.match(pattern, text, re.IGNORECASE):
                    return True
            
            return False
        except Exception as e:
            self.log(f"⚠️ Lỗi check next question marker: {str(e)}")
            return False
    
    def _check_duplicate_question(self, questions: Dict, new_question_text: str) -> Optional[int]:
        """Kiểm tra câu hỏi lặp"""
        try:
            new_text_clean = re.sub(r'\s+', ' ', new_question_text.lower().strip())
            
            for qnum, q_data in questions.items():
                existing_text = ' '.join(q_data.get('question_text', []))
                existing_clean = re.sub(r'\s+', ' ', existing_text.lower().strip())
                
                if new_text_clean in existing_clean or existing_clean in new_text_clean:
                    return qnum
            
            return None
        except Exception as e:
            self.log(f"⚠️ Lỗi check duplicate question: {str(e)}")
            return None
    
    def _check_duplicate_answers(self, text: str) -> Dict:
        """Kiểm tra đáp án lặp"""
        try:
            answer_pattern = r'\b([A-D])\.\s*([^\n]+)'
            answers = re.findall(answer_pattern, text, re.MULTILINE)
            
            if not answers:
                return {'has_duplicate': False, 'details': ''}
            
            # Kiểm tra trùng chỉ số
            answer_letters = [a[0] for a in answers]
            if len(answer_letters) != len(set(answer_letters)):
                duplicate_letters = [l for l in set(answer_letters) if answer_letters.count(l) > 1]
                return {
                    'has_duplicate': True,
                    'details': f"Đáp án lặp chỉ số: {', '.join(duplicate_letters)}"
                }
            
            # Kiểm tra trùng nội dung
            answer_contents = [re.sub(r'\s+', ' ', a[1].strip().lower()) for a in answers]
            seen = set()
            duplicates = []
            for i, content in enumerate(answer_contents):
                if content in seen and content:
                    duplicates.append(answer_letters[i])
                seen.add(content)
            
            if duplicates:
                return {
                    'has_duplicate': True,
                    'details': f"Đáp án lặp nội dung: {', '.join(duplicates)}"
                }
            
            return {'has_duplicate': False, 'details': ''}
        except Exception as e:
            self.log(f"⚠️ Lỗi check duplicate answers: {str(e)}")
            return {'has_duplicate': False, 'details': ''}
    
    def parse_questions_with_numbering(self) -> Dict[int, Dict]:
        """Parse câu hỏi với phát hiện dạng và kiểm tra lặp"""
        questions = {}
        current_question_num = None
        current_question_data = self._init_question_data()
        
        list_item_counter = 0
        in_question = False
        in_solution = False
        paragraphs_after_question = 0
        solution_end_paragraph = None
        
        self.log("\n" + "="*70)
        self.log("BẮT ĐẦU PARSE CÂU HỎI V8")
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
                    has_numbering = self.get_paragraph_numbering(para)
                    
                    # CASE 1: Paragraph có numbering → Câu hỏi mới
                    if has_numbering:
                        list_item_counter += 1
                        
                        # Lưu câu cũ
                        if current_question_num is not None:
                            if solution_end_paragraph is not None:
                                current_question_data['end_paragraph'] = solution_end_paragraph
                            else:
                                current_question_data['end_paragraph'] = idx - 1
                            
                            questions[current_question_num] = current_question_data.copy()
                            self.log(f"✓ Lưu Câu {current_question_num} "
                                    f"[{current_question_data['question_type']}] "
                                    f"end={current_question_data['end_paragraph']}")
                        
                        # Kiểm tra câu lặp
                        duplicate_of = self._check_duplicate_question(questions, text)
                        
                        # Bắt đầu câu mới
                        current_question_num = list_item_counter
                        current_question_data = self._init_question_data()
                        current_question_data['question_text'] = [text] if text else []
                        current_question_data['source'] = f'paragraph_{idx}_numbered'
                        current_question_data['start_paragraph'] = idx
                        current_question_data['question_type'] = self._detect_question_type(text)
                        current_question_data['duplicate_of'] = duplicate_of
                        
                        in_question = True
                        in_solution = False
                        solution_end_paragraph = None
                        paragraphs_after_question = 0
                        
                        self.log(f"\n📝 Phát hiện CÂU {current_question_num} "
                                f"[{current_question_data['question_type']}] "
                                f"start={idx}")
                        
                        if duplicate_of:
                            self.log(f"   ⚠️ CÂU LẶP của Câu {duplicate_of}")
                        
                        # Extract images & equations
                        para_images = self.extract_paragraph_images(para)
                        para_equations = self.extract_paragraph_equations(para)
                        self._add_images_to_section(current_question_data, para_images, 'question')
                        current_question_data['question_equations'].extend(para_equations)
                    
                    # CASE 2: Đang trong câu hỏi
                    elif in_question and current_question_num is not None:
                        paragraphs_after_question += 1
                        
                        # Kiểm tra câu hỏi tiếp theo
                        if self._is_next_question_marker(text):
                            self.log(f"   🛑 Phát hiện câu tiếp, dừng")
                            in_question = False
                            in_solution = False
                            continue
                        
                        # Kiểm tra bắt đầu lời giải
                        if not in_solution and self._is_solution_start_marker(text):
                            in_solution = True
                            self.log(f"   📘 BẮT ĐẦU LỜI GIẢI: {text[:50]}...")
                            current_question_data['solution_text'].append(text)
                            current_question_data['solution_start_paragraph'] = idx
                            
                            para_images = self.extract_paragraph_images(para)
                            para_equations = self.extract_paragraph_equations(para)
                            if para_images or para_equations:
                                self._add_images_to_section(current_question_data, para_images, 'solution')
                                current_question_data['solution_equations'].extend(para_equations)
                            
                            continue
                        
                        # Bỏ qua metadata
                        if text.startswith('[') and text.endswith(']'):
                            continue
                        
                        # Thu thập content
                        para_images = self.extract_paragraph_images(para)
                        para_equations = self.extract_paragraph_equations(para)
                        target_section = 'solution' if in_solution else 'question'
                        
                        if para_images or para_equations:
                            self._add_images_to_section(current_question_data, para_images, target_section)
                            if target_section == 'solution':
                                current_question_data['solution_equations'].extend(para_equations)
                            else:
                                current_question_data['question_equations'].extend(para_equations)
                        
                        if text:
                            if in_solution:
                                current_question_data['solution_text'].append(text)
                                solution_end_paragraph = idx
                            else:
                                current_question_data['question_text'].append(text)
                                # Kiểm tra đáp án lặp
                                dup_check = self._check_duplicate_answers(text)
                                if dup_check['has_duplicate']:
                                    current_question_data['answer_duplication'] = dup_check['details']
                                    self.log(f"   ⚠️ {dup_check['details']}")
                        
                        # Giới hạn
                        if paragraphs_after_question > 30:
                            self.log(f"   ⚠️ Quá 30 paragraphs, dừng")
                            in_question = False
                            in_solution = False
                
                except Exception as e:
                    self.log(f"✗ Lỗi xử lý paragraph {idx}: {str(e)}")
                    self.log(traceback.format_exc())
                    continue
            
            # Lưu câu cuối
            if current_question_num is not None:
                if solution_end_paragraph is not None:
                    current_question_data['end_paragraph'] = solution_end_paragraph
                else:
                    current_question_data['end_paragraph'] = len(self.doc.paragraphs) - 1
                
                questions[current_question_num] = current_question_data
                self.log(f"✓ Lưu Câu {current_question_num} (cuối) "
                        f"end={current_question_data['end_paragraph']}")
            
            self.log("\n" + "="*70)
            self.log(f"KẾT QUẢ: {len(questions)} câu hỏi")
            self.log("="*70)
            
        except Exception as e:
            self.log(f"✗ LỖI NGHIÊM TRỌNG trong parse_questions: {str(e)}")
            self.log(traceback.format_exc())
        
        return questions
    
    def _init_question_data(self) -> Dict:
        """Khởi tạo cấu trúc dữ liệu câu hỏi"""
        return {
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
            'duplicate_of': None,
            'answer_duplication': '',
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