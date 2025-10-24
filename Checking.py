"""
CheckDe_V2.py - IMPROVED: Đọc hình ảnh, công thức toán, XML structure
- Trích xuất hình ảnh embedded
- Đọc công thức MathML/Equation
- Parse XML linh hoạt
- Bảng đánh giá 3 hàng × 2 cột
- Chỉ check CHÍNH XÁC (không cần check đủ)
"""
import sys
import os
import glob
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QMessageBox, QTextEdit, QProgressBar,
    QGroupBox, QLineEdit, QRadioButton
)
from PyQt5.QtGui import QFont
from api.callApi import get_credentials
from process.CheckThread import CheckThread
from dotenv import load_dotenv
from pathlib import Path
# ==================== LOAD ENV (chỉ khi chạy local) ====================
try:
    # Nếu chạy local bằng Python thì mới cần load file .env
    if not getattr(sys, 'frozen', False):
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            print(f"✅ Loaded local .env: {env_path}")
        else:
            print("⚠️ Không tìm thấy file .env — có thể đang chạy bản .exe build")
except Exception as e:
    print(f"⚠️ Lỗi khi load .env (bỏ qua vì không ảnh hưởng build): {e}")
# ==================== MAIN WINDOW (giữ nguyên UI cũ) ====================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Check Đề Thi V2 - Hỗ trợ Hình ảnh & Công thức")
        self.resize(1000, 700)
        
        self.input_mode = "file"
        self.input_paths = []
        self.prompt_path = ""
        self.check_thread = None
        
        try:
            self.creds, self.project_id = get_credentials()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể load credentials: {str(e)}")
            sys.exit(1)
        
        self.setup_ui()
        self.apply_styles()
    
    def setup_ui(self):
        main_layout = QHBoxLayout()
        
        # === LEFT PANEL ===
        left_panel = QVBoxLayout()
        
        # 1. Chọn chế độ input
        mode_group = QGroupBox("📂 Chế Độ Input")
        mode_layout = QVBoxLayout()
        
        self.radio_file = QRadioButton("Chọn 1 file DOCX")
        self.radio_folder = QRadioButton("Chọn folder chứa nhiều DOCX")
        self.radio_file.setChecked(True)
        
        self.radio_file.toggled.connect(lambda: self.set_input_mode("file"))
        self.radio_folder.toggled.connect(lambda: self.set_input_mode("folder"))
        
        mode_layout.addWidget(self.radio_file)
        mode_layout.addWidget(self.radio_folder)
        mode_group.setLayout(mode_layout)
        
        # 2. Chọn input
        input_group = QGroupBox("📑 Chọn Input")
        input_layout = QVBoxLayout()
        
        self.input_label = QLineEdit("Chưa chọn")
        self.input_label.setReadOnly(True)
        
        self.btn_select_input = QPushButton("Chọn File/Folder")
        self.btn_select_input.clicked.connect(self.select_input)
        
        input_layout.addWidget(QLabel("Input:"))
        input_layout.addWidget(self.input_label)
        input_layout.addWidget(self.btn_select_input)
        input_group.setLayout(input_layout)
        
        # 3. Chọn prompt
        prompt_group = QGroupBox("📋 Prompt Check")
        prompt_layout = QVBoxLayout()
        
        self.prompt_label = QLineEdit("Chưa chọn prompt")
        self.prompt_label.setReadOnly(True)
        
        self.btn_select_prompt = QPushButton("Chọn File Prompt (.txt)")
        self.btn_select_prompt.clicked.connect(self.select_prompt)
        
        self.btn_edit_prompt = QPushButton("Sửa Prompt")
        self.btn_edit_prompt.clicked.connect(self.edit_prompt)
        
        prompt_btn_layout = QHBoxLayout()
        prompt_btn_layout.addWidget(self.btn_select_prompt)
        prompt_btn_layout.addWidget(self.btn_edit_prompt)
        
        prompt_layout.addWidget(QLabel("Prompt:"))
        prompt_layout.addWidget(self.prompt_label)
        prompt_layout.addLayout(prompt_btn_layout)
        prompt_group.setLayout(prompt_layout)
        
        # 4. Control buttons
        control_layout = QHBoxLayout()
        
        self.btn_start = QPushButton("▶️ BẮT ĐẦU CHECK")
        self.btn_start.clicked.connect(self.start_check)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-size: 14pt;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        
        self.btn_stop = QPushButton("⏸️ DỪNG")
        self.btn_stop.clicked.connect(self.stop_check)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-size: 12pt;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        
        control_layout.addWidget(self.btn_start)
        control_layout.addWidget(self.btn_stop)
        
        # 5. Progress
        progress_group = QGroupBox("📊 Tiến Độ")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        
        progress_layout.addWidget(self.progress_bar)
        progress_group.setLayout(progress_layout)
        
        # Add to left panel
        left_panel.addWidget(mode_group)
        left_panel.addWidget(input_group)
        left_panel.addWidget(prompt_group)
        left_panel.addLayout(control_layout)
        left_panel.addWidget(progress_group)
        left_panel.addStretch()
        
        # === RIGHT PANEL ===
        right_panel = QVBoxLayout()
        
        log_group = QGroupBox("📋 Log Xử Lý")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        
        right_panel.addWidget(log_group)
        
        # === MAIN LAYOUT ===
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        left_widget.setMaximumWidth(400)
        
        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        
        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget)
        
        self.setLayout(main_layout)
    
    def apply_styles(self):
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', Arial;
                font-size: 10pt;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
            QLineEdit, QTextEdit {
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                padding: 5px;
            }
            QProgressBar {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #2ecc71;
            }
        """)
    
    def set_input_mode(self, mode):
        self.input_mode = mode
        if mode == "file":
            self.btn_select_input.setText("Chọn File DOCX")
        else:
            self.btn_select_input.setText("Chọn Folder")
        self.input_label.setText("Chưa chọn")
        self.input_paths = []
    
    def select_input(self):
        if self.input_mode == "file":
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Chọn file DOCX", "", "Word Files (*.docx)"
            )
            if file_path:
                self.input_paths = [file_path]
                self.input_label.setText(os.path.basename(file_path))
                self.log_text.append(f"✔️ Đã chọn file: {os.path.basename(file_path)}")
        else:
            folder_path = QFileDialog.getExistingDirectory(
                self, "Chọn folder chứa DOCX"
            )
            if folder_path:
                docx_files = glob.glob(os.path.join(folder_path, "*.docx"))
                if docx_files:
                    self.input_paths = docx_files
                    self.input_label.setText(f"{folder_path} ({len(docx_files)} files)")
                    self.log_text.append(f"✔️ Đã chọn folder: {len(docx_files)} file DOCX")
                else:
                    QMessageBox.warning(self, "Cảnh báo", "Không tìm thấy file DOCX nào trong folder!")
    
    def select_prompt(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file prompt", "", "Text Files (*.txt)"
        )
        if file_path:
            self.prompt_path = file_path
            self.prompt_label.setText(os.path.basename(file_path))
            self.log_text.append(f"✔️ Đã chọn prompt: {os.path.basename(file_path)}")
    
    def edit_prompt(self):
        if not self.prompt_path or not os.path.exists(self.prompt_path):
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn file prompt trước!")
            return
        
        import platform
        if platform.system() == 'Windows':
            os.system(f'notepad "{self.prompt_path}"')
        elif platform.system() == 'Darwin':
            os.system(f'open -e "{self.prompt_path}"')
        else:
            os.system(f'xdg-open "{self.prompt_path}"')
        
        self.log_text.append(f"📝 Đã mở prompt để chỉnh sửa")
    
    def start_check(self):
        if not self.input_paths:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn file/folder input!")
            return
        
        if not self.prompt_path or not os.path.exists(self.prompt_path):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn file prompt!")
            return
        
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log_text.clear()
        self.progress_bar.setValue(0)
        
        self.check_thread = CheckThread(
            self.input_paths,
            self.prompt_path,
            self.project_id,
            self.creds
        )
        
        self.check_thread.progress.connect(self.update_log)
        self.check_thread.finished_signal.connect(self.on_finished)
        self.check_thread.error_signal.connect(self.on_error)
        
        self.check_thread.start()
    
    def stop_check(self):
        if self.check_thread and self.check_thread.isRunning():
            reply = QMessageBox.question(
                self, "Xác nhận",
                "Bạn có chắc muốn dừng?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.check_thread.stop()
                self.log_text.append("\n⏸️ Đang dừng...")
    
    def update_log(self, message):
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def on_finished(self, output_files):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setValue(100)
        
        QMessageBox.information(
            self, "Hoàn thành",
            f"✔️ Đã xử lý xong {len(output_files)} file!\n\n"
            f"📁 Kết quả trong folder: output_check"
        )
    
    def on_error(self, error_msg):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        
        QMessageBox.critical(self, "Lỗi", error_msg)


# ==================== MAIN ====================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())