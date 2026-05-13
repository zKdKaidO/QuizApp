import os
import re
import uuid
import json
import random
from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client

# Cấu hình đường dẫn templates chuẩn cho Vercel (chạy từ thư mục api/)
base_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_dir, '..', 'templates')

app = Flask(__name__, template_folder=template_dir)

# --- KẾT NỐI SUPABASE ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Supabase Init Error: {e}")

def parse_and_shuffle_quiz(raw_text):
    """
    Logic chính: Tách câu hỏi, xáo trộn thứ tự đáp án và gán lại nhãn A, B, C...
    """
    questions = []
    # Tách các khối dựa trên "Câu X:" hoặc số thứ tự "X)"
    blocks = re.split(r'(?:Câu\s*\d+[:\.]|\d+[\)\.])', raw_text)
    
    for block in blocks:
        block = block.strip()
        if not block: continue
        
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if not lines: continue
        
        q_content = lines[0]
        options_raw = []
        is_mcq = False 
        original_correct_label = ""
        
        # Bước 1: Thu thập nội dung đáp án và xác định câu đúng gốc
        for line in lines[1:]:
            # Nhận diện nhãn đáp án và nội dung
            match = re.match(r'^(\*?)\s*([A-E])[\.\)]\s*(.*)', line)
            if match:
                is_mcq = True
                is_star = match.group(1) == '*'
                label = match.group(2)
                text = match.group(3)
                
                options_raw.append({"text": text, "was_correct": is_star})
                if is_star:
                    original_correct_label = label
            
            elif line.lower().startswith("answer:"):
                ans_val = line.split(":", 1)[1].strip().upper()
                if len(ans_val) == 1:
                    original_correct_label = ans_val

        # Xử lý trường hợp dùng "Answer: X" thay vì dấu "*"
        if original_correct_label and not any(opt["was_correct"] for opt in options_raw):
            for i, opt in enumerate(options_raw):
                if chr(65 + i) == original_correct_label:
                    opt["was_correct"] = True

        if is_mcq and options_raw:
            # BƯỚC 2: XÀO ĐÁP ÁN (SHUFFLE)
            random.shuffle(options_raw)
            
            # BƯỚC 3: GÁN LẠI NHÃN A, B, C... VÀ TÌM ĐÁP ÁN ĐÚNG MỚI
            final_options = []
            new_correct_label = ""
            for i, opt in enumerate(options_raw):
                new_label = chr(65 + i)
                final_options.append({"label": new_label, "text": opt["text"]})
                if opt.get("was_correct"):
                    new_correct_label = new_label

            questions.append({
                "question": q_content,
                "options": final_options,
                "answer": new_correct_label
            })
            
    return questions

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html', shared_data='null')

@app.route('/quiz/<quiz_id>')
def view_quiz(quiz_id):
    """Lấy đề thi cụ thể từ kho lưu trữ Supabase."""
    if not supabase: 
        return "Database connection missing.", 500
    
    try:
        res = supabase.table("quizzes").select("questions").eq("id", quiz_id).maybe_single().execute()
        if not res.data:
            return "Quiz not found or has been deleted.", 404
            
        return render_template('index.html', shared_data=json.dumps(res.data['questions']))
    except Exception as e:
        return f"Error retrieving data: {str(e)}", 500

@app.route('/generate', methods=['POST'])
def generate():
    """Xử lý văn bản thô để tạo bản xem trước (preview) của đề thi."""
    data = request.json
    raw_text = data.get('text', '')
    questions = parse_and_shuffle_quiz(raw_text)
    
    if not questions:
        return jsonify({"error": "No valid multiple-choice questions found."}), 400

    # Trả về câu hỏi để hiển thị preview cho người dùng
    return jsonify({"questions": questions})

@app.route('/save-quiz', methods=['POST'])
def save_quiz():
    """Lưu vĩnh viễn đề thi vào Supabase."""
    if not supabase: return jsonify({"error": "Database missing"}), 500
    
    data = request.json
    title = data.get('title', 'Untitled Quiz')
    questions = data.get('questions')
    
    try:
        # Lưu vào bảng 'quizzes' theo cấu trúc bạn đã thiết lập
        res = supabase.table("quizzes").insert({
            "title": title,
            "questions": questions,
            "author": "PHẠM NHẬT NAM"
        }).execute()
        
        if res.data:
            quiz_id = res.data[0]['id']
            share_link = f"{request.host_url}quiz/{quiz_id}"
            return jsonify({"success": True, "share_link": share_link})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get-library', methods=['GET'])
def get_library():
    """Lấy danh sách các đề thi đã lưu để hiển thị ở Sidebar bên phải."""
    if not supabase: return jsonify([])
    try:
        # Chỉ lấy tiêu đề và ID để tối ưu tốc độ tải
        res = supabase.table("quizzes").select("id, title, created_at").order("created_at", desc=True).execute()
        return jsonify(res.data)
    except:
        return jsonify([])

# Đảm bảo Vercel nhận diện được app
app = app