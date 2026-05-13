import os
import re
import json
import random
from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client

base_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_dir, '..', 'templates')

app = Flask(__name__, template_folder=template_dir)

# --- BỌC THÉP CHO SUPABASE CONNECTION ---
# Dùng .strip() để diệt gọn khoảng trắng hay ngoặc kép rác do copy/paste
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().strip('"').strip("'")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip().strip('"').strip("'")

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"CRITICAL INIT ERROR - Lỗi khởi tạo Supabase: {e}")

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
    return questions

@app.route('/')
def index():
    return render_template('index.html', shared_data='null')

@app.route('/quiz/<quiz_id>')
def view_quiz(quiz_id):
    if not supabase: return "Database not connected", 500
    try:
        res = supabase.table("quizzes").select("questions").eq("id", quiz_id).maybe_single().execute()
        # Kiểm tra xem có data hay không, tránh lỗi NoneType
        if not hasattr(res, 'data') or not res.data:
            return "Quiz not found", 404
        return render_template('index.html', shared_data=json.dumps(res.data['questions']))
    except Exception as e:
        print(f"VIEW ERROR: {e}")
        return f"Server Error: {str(e)}", 500

@app.route('/generate', methods=['POST'])
def generate():
    # Thêm or {} để chống lỗi sập khi payload json bị trống
    data = request.json or {}
    title = data.get('title', 'Untitled Quiz')
    questions = parse_and_shuffle(data.get('text', ''))
    
    if not questions: return jsonify({"error": "No questions found"}), 400

    share_link = None
    if supabase:
        try:
            res = supabase.table("quizzes").insert({
                "title": title,
                "questions": questions,
                "author": "PHẠM NHẬT NAM"
            }).execute()
            
            if hasattr(res, 'data') and res.data:
                share_link = f"{request.host_url}quiz/{res.data[0]['id']}"
        except Exception as e:
            # Ghi lỗi ra log Vercel chứ không làm sập web
            print(f"INSERT ERROR: {e}")

    return jsonify({"questions": questions, "share_link": share_link})

@app.route('/get-library', methods=['GET'])
def get_library():
    if not supabase: return jsonify([])
    try:
        res = supabase.table("quizzes").select("id, title, created_at").order("created_at", desc=True).limit(10).execute()
        if hasattr(res, 'data') and res.data:
            return jsonify(res.data)
        return jsonify([])
    except Exception as e:
        print(f"LIBRARY ERROR: {e}")
        return jsonify([])

app = app