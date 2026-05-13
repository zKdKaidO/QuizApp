import os
import re
import uuid
import json
import random
from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client

# 1. Setup paths correctly for Vercel
base_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_dir, '..', 'templates')

app = Flask(__name__, template_folder=template_dir)

# 2. Supabase Connection (Ensure env vars are set in Vercel)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Supabase Init Error: {e}")

def parse_and_shuffle_quiz(raw_text):
    """Core logic: Parse, shuffle options, and re-label A, B, C..."""
    questions = []
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
        
        for line in lines[1:]:
            match = re.match(r'^(\*?)\s*([A-E])[\.\)]\s*(.*)', line)
            if match:
                is_mcq = True
                options_raw.append({"text": match.group(3), "was_correct": (match.group(1) == '*')})
                if match.group(1) == '*': original_correct_label = match.group(2)
            elif line.lower().startswith("answer:"):
                ans_val = line.split(":", 1)[1].strip().upper()
                if len(ans_val) == 1: original_correct_label = ans_val

        if original_correct_label and not any(opt["was_correct"] for opt in options_raw):
            for i, opt in enumerate(options_raw):
                if chr(65 + i) == original_correct_label: opt["was_correct"] = True

        if is_mcq and options_raw:
            random.shuffle(options_raw) # SHUFFLE HERE
            final_options = []
            new_correct_label = ""
            for i, opt in enumerate(options_raw):
                new_label = chr(65 + i)
                final_options.append({"label": new_label, "text": opt["text"]})
                if opt.get("was_correct"): new_correct_label = new_label
            questions.append({"question": q_content, "options": final_options, "answer": new_correct_label})
    return questions

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html', shared_data='null')

@app.route('/quiz/<quiz_id>')
def view_quiz(quiz_id):
    if not supabase: return "Database missing.", 500
    try:
        res = supabase.table("quizzes").select("questions").eq("id", quiz_id).maybe_single().execute()
        if not res.data: return "Quiz not found.", 404
        return render_template('index.html', shared_data=json.dumps(res.data['questions']))
    except Exception as e:
        return f"Database Error: {str(e)}", 500

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    raw_text = data.get('text', '')
    questions = parse_and_shuffle_quiz(raw_text)
    if not questions: return jsonify({"error": "No questions found."}), 400
    return jsonify({"questions": questions})

@app.route('/save-quiz', methods=['POST'])
def save_quiz():
    if not supabase: return jsonify({"error": "Database missing"}), 500
    data = request.json
    try:
        res = supabase.table("quizzes").insert({
            "title": data.get('title', 'Untitled'),
            "questions": data.get('questions'),
            "author": "NAM_STUDIO"
        }).execute()
        if res.data:
            return jsonify({"success": True, "share_link": f"{request.host_url}quiz/{res.data[0]['id']}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get-library', methods=['GET'])
def get_library():
    if not supabase: return jsonify([])
    try:
        res = supabase.table("quizzes").select("id, title, created_at").order("created_at", desc=True).execute()
        return jsonify(res.data)
    except:
        return jsonify([])

# Ensure Vercel finds the app
app = app