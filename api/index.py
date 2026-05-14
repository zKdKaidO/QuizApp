import os
import re
import uuid
import json
import random
from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client

base_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_dir, '..', 'templates')

app = Flask(__name__, template_folder=template_dir)

# --- SUPABASE CONNECTION ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

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
            
            # --- CODE CŨ: Xáo trộn vị trí các đáp án A, B, C, D ---
            random.shuffle(opts_raw)
            
            final_opts = []
            new_ans = ""
            for i, o in enumerate(opts_raw):
                lbl = chr(65 + i)
                final_opts.append({"label": lbl, "text": o["text"]})
                if o["correct"]: new_ans = lbl
            questions.append({"question": q_text, "options": final_opts, "answer": new_ans})
    
    # --- TÍNH NĂNG MỚI ĐƯỢC THÊM VÀO ĐÂY ---
    # Xáo trộn toàn bộ danh sách các câu hỏi trước khi trả về cho Frontend
    if questions:
        random.shuffle(questions)
        
    return questions

@app.route('/')
def index():
    return render_template('index.html', shared_data='null')

@app.route('/quiz/<quiz_id>')
def view_quiz(quiz_id):
    if not supabase: return "Database not connected", 500
    res = supabase.table("quizzes").select("questions").eq("id", quiz_id).maybe_single().execute()
    if not res.data: return "Quiz not found", 404
    return render_template('index.html', shared_data=json.dumps(res.data['questions']))

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    title = data.get('title', 'Untitled Quiz')
    questions = parse_and_shuffle(data.get('text', ''))
    
    if not questions: return jsonify({"error": "No questions found"}), 400

    share_link = None
    if supabase:
        # Tự động lưu vào Supabase ngay khi nhấn Build
        res = supabase.table("quizzes").insert({
            "title": title,
            "questions": questions,
            "author": "PHẠM NHẬT NAM"
        }).execute()
        if res.data:
            share_link = f"{request.host_url}quiz/{res.data[0]['id']}"

    return jsonify({"questions": questions, "share_link": share_link})

@app.route('/get-library', methods=['GET'])
def get_library():
    if not supabase: return jsonify([])
    res = supabase.table("quizzes").select("id, title, created_at").order("created_at", desc=True).limit(10).execute()
    return jsonify(res.data)

app = app