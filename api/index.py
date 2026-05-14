import os
import re
import json
import random
import traceback
from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client

base_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_dir, '..', 'templates')

app = Flask(__name__, template_folder=template_dir)

print(">>> LOG [INIT]: Đang khởi tạo ứng dụng Flask...")

# --- LẤY BIẾN MÔI TRƯỜNG ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().strip('"').strip("'")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip().strip('"').strip("'")

print(f">>> LOG [INIT]: URL Supabase lấy được: {SUPABASE_URL}")
print(f">>> LOG [INIT]: Độ dài Key lấy được: {len(SUPABASE_KEY)} ký tự (Nếu = 0 là chưa lấy được biến!)")

# --- KẾT NỐI SUPABASE ---
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        print(">>> LOG [INIT]: Đang gọi hàm create_client() của Supabase...")
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print(">>> LOG [INIT]: Khởi tạo create_client() THÀNH CÔNG!")
    except Exception as e:
        print(f">>> ERROR [INIT]: Sụp đổ ngay lúc kết nối Supabase: {e}")
        traceback.print_exc()
else:
    print(">>> ERROR [INIT]: Không tìm thấy biến môi trường SUPABASE_URL hoặc SUPABASE_KEY.")

def parse_and_shuffle(raw_text):
    questions = []
    blocks = re.split(r'(?:Câu\s*\d+[:\.]|\d+[\)\.])', raw_text)
    for block in blocks:
        block = block.strip()
        if not block: continue
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if not lines or len(lines) < 2: continue
        q_text = lines[0]
        opts_raw = []
        is_mcq = False
        ans_label = ""
        for line in lines[1:]:
            m = re.match(r'^(\*?)\s*([A-E])[\.\)]\s*(.*)', line)
            if m:
                is_mcq = True
                opts_raw.append({"text": m.group(3), "correct": (m.group(1) == '*')})
                if m.group(1) == '*': ans_label = m.group(2)
            elif line.lower().startswith("answer:"):
                ans_label = line.split(":", 1)[1].strip().upper()
        
        if is_mcq and opts_raw:
            if ans_label and not any(o['correct'] for o in opts_raw):
                idx = ord(ans_label) - 65
                if 0 <= idx < len(opts_raw): opts_raw[idx]['correct'] = True
            
            random.shuffle(opts_raw)
            final_opts = []
            new_ans = ""
            for i, o in enumerate(opts_raw):
                lbl = chr(65 + i)
                final_opts.append({"label": lbl, "text": o["text"]})
                if o["correct"]: new_ans = lbl
            questions.append({"question": q_text, "options": final_opts, "answer": new_ans})
    
    if questions:
        random.shuffle(questions)
    return questions

@app.route('/')
def index():
    print(">>> LOG [ROUTE]: Có người truy cập trang chủ /")
    return render_template('index.html', shared_data='null')

@app.route('/generate', methods=['POST'])
def generate():
    print(">>> LOG [ROUTE]: Đang gọi /generate để xem trước đề...")
    data = request.json or {}
    questions = parse_and_shuffle(data.get('text', ''))
    if not questions: 
        print(">>> ERROR [GENERATE]: Không bóc tách được câu hỏi nào từ raw_text.")
        return jsonify({"error": "No questions found"}), 400
    
    print(f">>> LOG [GENERATE]: Bóc tách thành công {len(questions)} câu hỏi.")
    return jsonify({"questions": questions})

@app.route('/save-quiz', methods=['POST'])
def save_quiz():
    print(">>> LOG [SAVE]: Bắt đầu chạy hàm lưu đề thi /save-quiz")
    data = request.json or {}
    title = data.get('title', 'Untitled Quiz')
    questions = data.get('questions', [])
    
    if not supabase: 
        print(">>> ERROR [SAVE]: supabase client chưa được khởi tạo (bị None).")
        return jsonify({"error": "Supabase not connected"}), 500
    if not questions: 
        print(">>> ERROR [SAVE]: Mảng questions truyền xuống bị rỗng.")
        return jsonify({"error": "No questions to save"}), 400
    
    try:
        print(f">>> LOG [SAVE]: Đang chèn dữ liệu vào bảng 'quizzes' (Title: {title})...")
        res = supabase.table("quizzes").insert({
            "title": title,
            "questions": questions,
            "author": "PHẠM NHẬT NAM"
        }).execute()
        
        print(f">>> LOG [SAVE]: Phản hồi từ Supabase: {res}")
        
        if hasattr(res, 'data') and res.data:
            share_link = f"{request.host_url}quiz/{res.data[0]['id']}"
            print(f">>> LOG [SAVE]: LƯU THÀNH CÔNG! Đã tạo link: {share_link}")
            return jsonify({"success": True, "share_link": share_link})
        else:
            print(">>> ERROR [SAVE]: Không có lỗi Exception nhưng API không trả về res.data")
            return jsonify({"error": "Dữ liệu không được ghi nhận"}), 500
            
    except Exception as e:
        print(f">>> ERROR [SAVE]: Văng Exception khi Insert dữ liệu: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Database Insert Error: {str(e)}"}), 500

@app.route('/get-library', methods=['GET'])
def get_library():
    print(">>> LOG [LIBRARY]: Đang gọi hàm lấy danh sách thư viện /get-library...")
    if not supabase: 
        print(">>> ERROR [LIBRARY]: supabase client bị None.")
        return jsonify([])
    try:
        res = supabase.table("quizzes").select("id, title, created_at").order("created_at", desc=True).limit(15).execute()
        if hasattr(res, 'data') and res.data:
            print(f">>> LOG [LIBRARY]: Lấy thành công {len(res.data)} bộ đề cũ.")
            return jsonify(res.data)
        
        print(">>> LOG [LIBRARY]: Truy vấn ok nhưng bảng chưa có data (trống).")
        return jsonify([])
    except Exception as e:
        print(f">>> ERROR [LIBRARY]: Lỗi khi lấy thư viện: {e}")
        return jsonify([])

@app.route('/quiz/<quiz_id>')
def view_quiz(quiz_id):
    print(f">>> LOG [VIEW]: Có người truy cập mở đề thi ID: {quiz_id}")
    if not supabase: 
        print(">>> ERROR [VIEW]: supabase client bị None.")
        return "Database not connected", 500
    try:
        res = supabase.table("quizzes").select("questions").eq("id", quiz_id).maybe_single().execute()
        if not hasattr(res, 'data') or not res.data:
            print(">>> ERROR [VIEW]: Truy vấn thành công nhưng không tìm thấy đề.")
            return "Quiz not found", 404
        
        print(">>> LOG [VIEW]: Tải đề thành công, đang đẩy vào render_template.")
        return render_template('index.html', shared_data=json.dumps(res.data['questions']))
    except Exception as e:
        print(f">>> ERROR [VIEW]: Lỗi văng Exception khi truy vấn ID: {e}")
        return f"Server Error: {str(e)}", 500

app = app