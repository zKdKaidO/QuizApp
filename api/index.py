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

# --- KẾT NỐI SUPABASE ---
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f">>> ERROR [INIT]: Sụp đổ ngay lúc kết nối Supabase: {e}")
        traceback.print_exc()

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
    return render_template('index.html', shared_data='null')

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json or {}
    questions = parse_and_shuffle(data.get('text', ''))
    if not questions: return jsonify({"error": "No questions found"}), 400
    return jsonify({"questions": questions})

@app.route('/save-quiz', methods=['POST'])
def save_quiz():
    data = request.json or {}
    title = data.get('title', 'Untitled Quiz')
    questions = data.get('questions', [])
    
    if not supabase: return jsonify({"error": "Supabase not connected"}), 500
    if not questions: return jsonify({"error": "No questions to save"}), 400
    
    try:
        res = supabase.table("quizzes").insert({
            "title": title,
            "questions": questions,
            "author": "PHẠM NHẬT NAM"
        }).execute()
        if hasattr(res, 'data') and res.data:
            share_link = f"{request.host_url}quiz/{res.data[0]['id']}"
            return jsonify({"success": True, "share_link": share_link})
        return jsonify({"error": "Dữ liệu không được ghi nhận"}), 500
    except Exception as e:
        return jsonify({"error": f"Database Insert Error: {str(e)}"}), 500

@app.route('/get-library', methods=['GET'])
def get_library():
    if not supabase: return jsonify([])
    try:
        res = supabase.table("quizzes").select("id, title, created_at").order("created_at", desc=True).limit(15).execute()
        if hasattr(res, 'data') and res.data: return jsonify(res.data)
        return jsonify([])
    except Exception as e:
        return jsonify([])

# --- TÍNH NĂNG MỚI 1: XÓA QUÍZ ---
@app.route('/delete-quiz/<quiz_id>', methods=['DELETE'])
def delete_quiz(quiz_id):
    if not supabase: return jsonify({"error": "Database not connected"}), 500
    try:
        supabase.table("quizzes").delete().eq("id", quiz_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/quiz/<quiz_id>')
def view_quiz(quiz_id):
    if not supabase: return "Database not connected", 500
    try:
        # TÍNH NĂNG MỚI: Lấy cả Title để hiển thị cho đẹp
        res = supabase.table("quizzes").select("title, questions").eq("id", quiz_id).maybe_single().execute()
        if not hasattr(res, 'data') or not res.data: return "Quiz not found", 404
        
        shared_payload = {
            "title": res.data.get('title', 'SHARED QUIZ'),
            "questions": res.data['questions']
        }
        return render_template('index.html', shared_data=json.dumps(shared_payload))
    except Exception as e:
        return f"Server Error: {str(e)}", 500

app = app