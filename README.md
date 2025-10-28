# 🧠 Checking Question

**Checking Question** là một dự án **Python sử dụng AI (Gemini API)** để **tự động kiểm tra và đánh giá đề thi**.  
Công cụ này giúp rà soát **nội dung câu hỏi**, **đáp án**, **lời giải**, và **đưa ra bảng đánh giá chi tiết** cho từng câu hỏi.

---

## 🚀 Tính năng chính

- ✅ Kiểm tra cấu trúc câu hỏi trong đề thi (nội dung – đáp án – lời giải)
- 🧩 Đưa ra nhận xét và đánh giá tự động theo tiêu chí cấu hình sẵn
- 📊 Xuất bảng đánh giá dạng bảng 2x3 trong file `.docx`
- 🔁 Đầu vào: **file `.docx` hoặc `.xml`**
- 💾 Đầu ra: **file `.docx` đã qua kiểm tra và chấm điểm**

---

## ⚙️ Yêu cầu hệ thống

- **Python**: `>= 3.10`
- **Kết nối Internet** để gọi **API Gemini**
- Khuyến nghị: chạy trong **môi trường ảo (virtual environment)** để tránh xung đột thư viện.

---

## 📦 Cài đặt

### 1️. Clone dự án
```bash
git clone https://github.com/HoangLinh03-code/CheckingQues
cd CheckingQues
```

### 2. Tạo môi trường ảo
#### Trên windows
```bash
python -m venv venv
venv\Scripts\activate
```
#### Trên linux
```bash
python3 -m venv venv
source venv/bin/activate
```
### 3. Cài các thư viện cần thiết
```bash
pip install -r requirements.txt
```
### 4. Chạy chương trình
#### Trên windows
```bash
python Checking.py
```
#### Trên linux
```bash
python3 Checking.py
```
