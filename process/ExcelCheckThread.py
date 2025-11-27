# from typing import Any
# from PyQt5.QtCore import QThread, pyqtSignal
# from openpyxl import load_workbook
# from openpyxl.styles import Alignment, Font
# import os
# import traceback
# import openpyxl.utils
# from process.AICheck import AIQuestionExcelChecker  # import class mới

# class ExcelCheckThread(QThread):
#     """Thread xử lý Excel song song (có progress signal)"""
#     progress = pyqtSignal(str)
#     finished_signal = pyqtSignal(list)
#     error_signal = pyqtSignal(str)

#     def __init__(self, input_paths, prompt_path, project_id, creds):
#         super().__init__()
#         self.input_paths = input_paths
#         self.prompt_path = prompt_path
#         self.project_id = project_id
#         self.creds = creds
#         self.stop_requested = False

#     def stop(self):
#         """Dừng thread an toàn"""
#         self.stop_requested = True

#     def get_last_filled_col(self, ws):
#         """Xác định cột cuối cùng có dữ liệu thực sự"""
#         last_col = 0
#         for cell in ws[1]:
#             if cell.value not in (None, "", " "):
#                 last_col = cell.column
#         return last_col or 1

#     def run(self):
#         try:
#             # --- Load Prompt ---
#             self.progress.emit("📋 Đang load prompt...")
#             with open(self.prompt_path, "r", encoding="utf-8") as f:
#                 prompt_text = f.read().strip()
#             if not prompt_text:
#                 raise Exception("Prompt rỗng — vui lòng chọn lại file prompt hợp lệ!")

#             # --- Khởi tạo AI Excel Checker ---
#             self.progress.emit("🤖 Đang khởi tạo AI Checker chuyên dụng cho Excel...")
#             checker = AIQuestionExcelChecker(self.project_id, self.creds)

#             # --- Tạo folder output ---
#             output_folder = "output_excel"
#             os.makedirs(output_folder, exist_ok=True)

#             processed_files = []

#             # --- Duyệt từng file Excel ---
#             for idx, file_path in enumerate(self.input_paths):
#                 if self.stop_requested:
#                     break

#                 filename = os.path.basename(file_path)
#                 self.progress.emit(f"\n📘 [{idx+1}/{len(self.input_paths)}] {filename}")

#                 if not file_path.lower().endswith(".xlsx"):
#                     self.progress.emit(f"⚠️ Bỏ qua {filename} (không phải file Excel)")
#                     continue

#                 try:
#                     wb = load_workbook(file_path)
#                 except Exception as e:
#                     self.progress.emit(f"❌ Không thể đọc file {filename}: {e}")
#                     continue

#                 # --- Duyệt từng sheet ---
#                 for sheetname in wb.sheetnames:
#                     ws = wb[sheetname]
#                     self.progress.emit(f"📄 Sheet: {sheetname}")

#                     # Xác định các cột chính
#                     header_map = {str(cell.value).strip().lower(): cell.column for cell in ws[1] if cell.value}

#                     def find_col_by_keywords(keywords):
#                         for h, col_idx in header_map.items():
#                             for kw in keywords:
#                                 if kw in h:
#                                     return col_idx
#                         return None

#                     col_question = find_col_by_keywords(
#                         ["đề", "de bai", "đề bài", "de", "đề bài câu hỏi","Đề bài câu hỏi", "Nội dung câu hỏi"]
#                     ) or 1
#                     col_materials = find_col_by_keywords(
#                         ["học liệu", "hoc lieu", "tài liệu", "tailieu","Học liệu"]
#                     )
#                     col_options = find_col_by_keywords(
#                         ["phương", "phuong", "đáp án", "dap an", "Phương án câu hỏi", "hướng dẫn giải", "Phương án câu hỏi", "Hướng dẫn giải"]
#                     )

#                     if not (col_question and col_materials and col_options):
#                         self.progress.emit(f"⚠️ Bỏ qua sheet '{sheetname}' (thiếu cột bắt buộc cho phân tích câu hỏi)")
#                         continue

#                     # Các cột phụ thêm nếu có
#                     extra_context_cols = [
#                         (h, cidx) for h, cidx in header_map.items()
#                         if cidx not in (col_question, col_materials, col_options)
#                         and not any(k in h for k in ["đánh giá","gợi ý","kiến thức","danh gia","goi y","kien thuc"])
#                     ]

#                     # --- Tạo 3 cột mới ---
#                     last_col = self.get_last_filled_col(ws)
#                     col_eval = last_col + 1
#                     col_sugg = last_col + 2
#                     col_know = last_col + 3

#                     ws.cell(1, col_eval, "Đánh giá câu hỏi")
#                     ws.cell(1, col_sugg, "Gợi ý làm bài")
#                     ws.cell(1, col_know, "Kiến thức liên quan")

#                     for col in [col_eval, col_sugg, col_know]:
#                         ws.cell(1, col).alignment = Alignment(horizontal="center", vertical="center")
#                         ws.cell(1, col).font = Font(bold=False)

#                     max_eval_len = max_sugg_len = max_know_len = len("Đánh giá câu hỏi")
#                     max_row = ws.max_row

#                     def read_cell_safe(r, c):
#                         try:
#                             v = ws.cell(row=r, column=c).value
#                             return "" if v is None else str(v).strip()
#                         except Exception:
#                             return ""

#                     # --- Duyệt từng dòng ---
#                     for row_idx in range(2, max_row + 1):
#                         if self.stop_requested:
#                             break

#                         question_text = read_cell_safe(row_idx, col_question)
#                         if not question_text:
#                             continue

#                         materials_text = read_cell_safe(row_idx, col_materials) if col_materials else ""
#                         options_text = read_cell_safe(row_idx, col_options) if col_options else ""

#                         extras = [f"{h}: {read_cell_safe(row_idx, cidx)}" for h, cidx in extra_context_cols if read_cell_safe(row_idx, cidx)]

#                         # --- Chuẩn bị dữ liệu ---
#                         question_data = {
#                             "question_text": [question_text],
#                             "question_images": [],
#                             "solution_text": [],
#                             "question_equations": [],
#                             "solution_equations": [],
#                             "materials": materials_text,
#                             "options": options_text,
#                             "extras": extras
#                         }

#                         # --- Gọi AI ---
#                         result = checker.check_question(question_data, prompt_text)
#                         self.progress.emit(f"🔹 Dòng {row_idx} kết quả: {result}")

#                         # --- Ghi kết quả vào Excel ---
#                         ws.cell(row_idx, col_eval, result.get("evaluation", ""))
#                         ws.cell(row_idx, col_sugg, result.get("suggestions", ""))
#                         ws.cell(row_idx, col_know, result.get("knowledge", ""))

#                         for col, val in [(col_eval, result.get("evaluation","")),
#                                          (col_sugg, result.get("suggestions","")),
#                                          (col_know, result.get("knowledge",""))]:
#                             ws.cell(row_idx, col).alignment = Alignment(wrap_text=True, vertical="top", horizontal="left")
#                             if col == col_eval:
#                                 max_eval_len = max(max_eval_len, len(val))
#                             elif col == col_sugg:
#                                 max_sugg_len = max(max_sugg_len, len(val))
#                             elif col == col_know:
#                                 max_know_len = max(max_know_len, len(val))

#                     # --- Giãn cột ---
#                     def adjust_column_width(col_letter, max_len):
#                         ws.column_dimensions[col_letter].width = min(max_len + 2, 80)

#                     adjust_column_width(openpyxl.utils.get_column_letter(col_eval), max_eval_len)
#                     adjust_column_width(openpyxl.utils.get_column_letter(col_sugg), max_sugg_len)
#                     adjust_column_width(openpyxl.utils.get_column_letter(col_know), max_know_len)

#                 # --- Lưu file ---
#                 out_path = os.path.join(output_folder, f"checked_{filename}")
#                 try:
#                     wb.save(out_path)
#                     processed_files.append(out_path)
#                     self.progress.emit(f"💾 Đã lưu: {out_path}")
#                 except Exception as e:
#                     self.progress.emit(f"❌ Lỗi khi lưu {filename}: {e}")

#             self.progress.emit("\n🎉 Hoàn thành toàn bộ file Excel!")
#             self.finished_signal.emit(processed_files)

#         except Exception as e:
#             err_msg = f"❌ Lỗi tổng thể: {str(e)}\n{traceback.format_exc()}"
#             self.error_signal.emit(err_msg)



from typing import Any, Dict, List
from PyQt5.QtCore import QThread, pyqtSignal
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import column_index_from_string, get_column_letter
import os
import traceback
import openpyxl.utils
from process.AICheck import AIQuestionExcelChecker  # import class mới
from openpyxl.worksheet.worksheet import Worksheet

class ExcelCheckThread(QThread):
    """Thread xử lý Excel song song (có progress signal)"""
    progress = pyqtSignal(str)
    finished_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    def __init__(self, input_paths, prompt_path, project_id, creds):
        super().__init__()
        self.input_paths = input_paths
        self.prompt_path = prompt_path
        self.project_id = project_id
        self.creds = creds
        self.stop_requested = False

    def stop(self):
        """Dừng thread an toàn"""
        self.stop_requested = True

   
    def get_last_filled_col(self, ws: Worksheet):
        """Xác định cột cuối cùng có header thực sự (trả về index int)."""
        last_col = 0
        for cell in ws[1]:
            if cell.value not in (None, "", " "):
                # cell.column có thể là số hoặc chữ tuỳ phiên bản openpyxl
                col = cell.column
                if isinstance(col, str):
                    try:
                        col = column_index_from_string(col)
                    except Exception:
                        # fallback: ignore
                        continue
                last_col = max(last_col, int(col))
        return last_col or 1
    
    def read_cell_safe(self, ws: Worksheet, r, c):
        try:
            if isinstance(c, str):
                c = column_index_from_string(c)
            v = ws.cell(row=int(r), column=int(c)).value
            return "" if v is None else str(v).strip()
        except Exception:
            return ""
    def write_cell_safe(self, ws: Worksheet, r, c, v):
        try:
            if isinstance(c, str):
                c = column_index_from_string(c)

            # ⚡ Fix lỗi công thức: nếu chuỗi bắt đầu bằng "=" hoặc "-"
            if isinstance(v, str) and v.strip().startswith(("=", "-")):
                v = "'" + v  # thêm dấu nháy đơn để ép Excel hiểu là text

            ws.cell(row=int(r), column=int(c), value=v)
        except Exception:
            return
    def get_valid_sheets(self,wb) -> List[str]:
        """
        Lấy danh sách sheet thực tế có dữ liệu.
        Trả về list sheetname hợp lệ.
        """
        valid_sheets = []
        for sheetname in wb.sheetnames:
            ws: Worksheet = wb[sheetname]
            # Check có dữ liệu ngoài header
            has_data = False
            for row in ws.iter_rows(min_row=2):
                for cell in row:
                    if cell.value not in (None, "", " "):
                        has_data = True
                        break
                if has_data:
                    break
            if has_data:
                valid_sheets.append(sheetname)
            else:
                print(f"⚠️ Bỏ qua sheet '{sheetname}' (trống hoặc không có dữ liệu thực tế)")
        return valid_sheets   

    def run(self):
        try:
            # --- Load Prompt ---
            self.progress.emit("📋 Đang load prompt...")
            with open(self.prompt_path, "r", encoding="utf-8") as f:
                prompt_text = f.read().strip()
            if not prompt_text:
                raise Exception("Prompt rỗng — vui lòng chọn lại file prompt hợp lệ!")

            # --- Khởi tạo AI Excel Checker ---
            self.progress.emit("🤖 Đang khởi tạo AI Checker chuyên dụng cho Excel...")
            checker = AIQuestionExcelChecker(self.project_id, self.creds)

            # --- Tạo folder output ---
            output_folder = "output_excel"
            os.makedirs(output_folder, exist_ok=True)

            processed_files = []

            # --- Duyệt từng file Excel ---
            for idx, file_path in enumerate(self.input_paths):
                if self.stop_requested:
                    break

                filename = os.path.basename(file_path)
                self.progress.emit(f"\n📘 [{idx+1}/{len(self.input_paths)}] {filename}")

                if not file_path.lower().endswith(".xlsx"):
                    self.progress.emit(f"⚠️ Bỏ qua {filename} (không phải file Excel)")
                    continue

                try:
                    wb = load_workbook(file_path)
                except Exception as e:
                    self.progress.emit(f"❌ Không thể đọc file {filename}: {e}")
                    continue
                
                valid_sheets = self.get_valid_sheets(wb)
                if not valid_sheets:
                    self.progress.emit(f"⚠️ Bỏ qua file '{filename}' (không có sheet hợp lệ để xử lý)")
                    continue
                # --- Duyệt từng sheet ---
                # for sheetname in wb.sheetnames:
                for sheetname in valid_sheets:
                    ws: Worksheet = wb[sheetname]
                    self.progress.emit(f"📄 Sheet: {sheetname}")

                    # Xác định các cột chính
                    header_map = {str(cell.value).strip().lower(): cell.column for cell in ws[1] if cell.value}

                    def find_col_by_keywords(keywords):
                        for h, col_idx in header_map.items():
                            for kw in keywords:
                                if kw in h:
                                    return col_idx
                        return None

                    col_question = find_col_by_keywords(
                        ["đề", "de bai", "đề bài", "de", "đề bài câu hỏi","Phương án câu hỏi","Đề bài câu hỏi", "Nội dung câu hỏi"]
                    ) or 1
                    col_materials = find_col_by_keywords(
                        ["học liệu", "hoc lieu", "tài liệu", "tailieu","Học liệu"]
                    )
                    col_options = find_col_by_keywords(
                        ["phương", "phuong", "đáp án", "dap an", "hướng dẫn giải", "Phương án câu hỏi", "Hướng dẫn giải"]
                    )

                    if not (col_question and col_materials and col_options):
                        self.progress.emit(f"⚠️ Bỏ qua sheet '{sheetname}' (thiếu cột bắt buộc cho phân tích câu hỏi)")
                        continue

                    # Các cột phụ thêm nếu có
                    extra_context_cols = [
                        (h, cidx) for h, cidx in header_map.items()
                        if cidx not in (col_question, col_materials, col_options)
                        and not any(k in h for k in ["đánh giá","gợi ý","kiến thức","danh gia","goi y","kien thuc"])
                    ]

                    # --- Tạo 3 cột mới ---
                    last_col = self.get_last_filled_col(ws)
                    col_eval = last_col + 1
                    col_sugg = last_col + 2
                    col_know = last_col + 3

                    ws.cell(1, col_eval, "Đánh giá câu hỏi")
                    ws.cell(1, col_sugg, "Gợi ý làm bài")
                    ws.cell(1, col_know, "Kiến thức liên quan")

                    for col in [col_eval, col_sugg, col_know]:
                        ws.cell(1, col).alignment = Alignment(horizontal="center", vertical="center")
                        ws.cell(1, col).font = Font(bold=False)

                    max_eval_len = max_sugg_len = max_know_len = len("Đánh giá câu hỏi")
                    max_row = ws.max_row

                    def read_cell_safe(r, c):
                        try:
                            v = ws.cell(row=r, column=c).value
                            return "" if v is None else str(v).strip()
                        except Exception:
                            return ""
                    question_list = []
                    row_map = []  # lưu vị trí dòng để ghi kết quả sau

                    for row_idx in range(2, max_row + 1):
                        if self.stop_requested:
                            break

                        question_text = read_cell_safe(row_idx, col_question)
                        if not question_text:
                            continue

                        materials_text = read_cell_safe(row_idx, col_materials) if col_materials else ""
                        options_text = read_cell_safe(row_idx, col_options) if col_options else ""
                        extras = [f"{h}: {read_cell_safe(row_idx, cidx)}" for h, cidx in extra_context_cols if read_cell_safe(row_idx, cidx)]

                        question_list.append({
                            "question_text": [question_text],
                            "question_images": [],
                            "solution_text": [],
                            "question_equations": [],
                            "solution_equations": [],
                            "materials": materials_text,
                            "options": options_text,
                            "extras": extras
                        })
                        row_map.append(row_idx)

                    # --- Gửi batch lên AI ---
                    if question_list:
                        self.progress.emit(f"🚀 Gửi {len(question_list)} câu hỏi lên AI (chia chunk nếu cần)...")
                        results: List[Dict[str,str]] = checker.check_questions_batch(question_list, prompt_text)

                        self.progress.emit(f"DEBUG: Dạng dữ liệu trả về = {type(results)}")
                        if isinstance(results, list):
                            self.progress.emit(f"DEBUG: Phần tử đầu tiên = {type(results[0])}, giá trị = {results[0]}")

                        # for (row_idx, result) in zip(row_map, results):
                        #     ws.cell(row_idx, col_eval, result.get("evaluation", ""))
                        #     ws.cell(row_idx, col_sugg, result.get("suggestions", ""))
                        #     ws.cell(row_idx, col_know, result.get("knowledge", ""))
                        # for (row_idx, result) in zip(row_map, results):
                        #     self.write_cell_safe(ws, row_idx, col_eval, result.get("evaluation", ""))
                        #     self.write_cell_safe(ws, row_idx, col_sugg, result.get("suggestions", ""))
                        #     self.write_cell_safe(ws, row_idx, col_know, result.get("knowledge", ""))

                        #     # cập nhật max lengths (nếu cần để auto-width)
                        #     max_eval_len = max(max_eval_len, len(result.get("evaluation", "") or ""))
                        #     max_sugg_len = max(max_sugg_len, len(result.get("suggestions", "") or ""))
                        #     max_know_len = max(max_know_len, len(result.get("knowledge", "") or ""))
                        for (row_idx, result) in zip(row_map, results):
                            eval_text = result.get("evaluation", "") or ""
                            sugg_text = result.get("suggestions", "") or ""
                            know_text = result.get("knowledge", "") or ""

                            self.write_cell_safe(ws, row_idx, col_eval, eval_text)
                            self.write_cell_safe(ws, row_idx, col_sugg, sugg_text)
                            self.write_cell_safe(ws, row_idx, col_know, know_text)

                            # cập nhật max lengths (dùng cho auto width)
                            max_eval_len = max(max_eval_len, len(eval_text))
                            max_sugg_len = max(max_sugg_len, len(sugg_text))
                            max_know_len = max(max_know_len, len(know_text))

                            # --- Tự động giãn dòng ---
                            current_height = ws.row_dimensions[row_idx].height
                            if not current_height or current_height <= 15:  # chỉ giãn nếu chưa chỉnh thủ công
                                # Ước lượng độ cao dòng theo số dòng text (mỗi ~80 ký tự xem như xuống 1 dòng)
                                eval_lines = len(eval_text) // 80 + 1
                                sugg_lines = len(sugg_text) // 80 + 1
                                know_lines = len(know_text) // 80 + 1

                                max_lines = max(eval_lines, sugg_lines, know_lines)
                                base_height = 15  # chiều cao mặc định (đơn vị: points)
                                ws.row_dimensions[row_idx].height = min(base_height * max_lines, 200)                           

                      

                    # --- Giãn cột ---
                    def adjust_column_width(col_letter, max_len):
                        ws.column_dimensions[col_letter].width = min(max_len + 2, 80)

                    adjust_column_width(openpyxl.utils.get_column_letter(col_eval), max_eval_len)
                    adjust_column_width(openpyxl.utils.get_column_letter(col_sugg), max_sugg_len)
                    adjust_column_width(openpyxl.utils.get_column_letter(col_know), max_know_len)

                # --- Lưu file ---
                out_path = os.path.join(output_folder, f"checked_{filename}")
                try:
                    wb.save(out_path)
                    processed_files.append(out_path)
                    self.progress.emit(f"💾 Đã lưu: {out_path}")
                except Exception as e:
                    self.progress.emit(f"❌ Lỗi khi lưu {filename}: {e}")

            self.progress.emit("\n🎉 Hoàn thành toàn bộ file Excel!")
            self.finished_signal.emit(processed_files)

        except Exception as e:
            err_msg = f"❌ Lỗi tổng thể: {str(e)}\n{traceback.format_exc()}"
            self.error_signal.emit(err_msg)
