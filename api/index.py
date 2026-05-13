import os
import re
import uuid
import json
import random
from flask import Flask, render_template, request, jsonify
from upstash_redis import Redis

base_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_dir, '..', 'templates')

app = Flask(__name__, template_folder=template_dir)

# Kết nối Vercel KV (Redis)
try:
    redis = Redis.from_env()
except Exception:
    redis = None

def parse_quiz_text(raw_text):
    questions = []
    blocks = re.split(r'(?:Câu\s*\d+[:\.]|\d+[\)\.])', raw_text)
    
    for block in blocks:
        block = block.strip()
        if not block: continue
        
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if not lines: continue
        
        q_content = lines[0]
        options_raw = []
        original_correct_label = ""
        is_mcq = False 
        
        # Bước 1: Parse thô để lấy nội dung và xác định câu đúng gốc
        for line in lines[1:]:
            match = re.match(r'^(\*?)\s*([A-E])[\.\)]\s*(.*)', line)
            if match:
                is_mcq = True
                is_star_correct = match.group(1) == '*'
                label = match.group(2)
                text = match.group(3)
                
                options_raw.append({"text": text, "was_correct": is_star_correct})
                if is_star_correct:
                    original_correct_label = label
            
            elif line.lower().startswith("answer:"):
                ans_val = line.split(":", 1)[1].strip().upper()
                if len(ans_val) == 1:
                    original_correct_label = ans_val

        # Nếu dùng format "Answer: X", đánh dấu lại flag was_correct cho option đó
        if original_correct_label and not any(opt["was_correct"] for opt in options_raw):
            for i, opt in enumerate(options_raw):
                # Map A->0, B->1...
                if chr(65 + i) == original_correct_label:
                    opt["was_correct"] = True

        if is_mcq and options_raw:
            # BƯỚC 2: XÀO ĐÁP ÁN (SHUFFLE)
            random.shuffle(options_raw)
            
            # BƯỚC 3: GÁN LẠI NHÃN A, B, C, D VÀ TÌM ĐÁP ÁN ĐÚNG MỚI
            final_options = []
            new_correct_label = ""
            for i, opt in enumerate(options_raw):
                new_label = chr(65 + i) # Tạo nhãn A, B, C...
                final_options.append({"label": new_label, "text": opt["text"]})
                if opt["was_correct"]:
                    new_correct_label = new_label

            questions.append({
                "question": q_content,
                "options": final_options,
                "answer": new_correct_label
            })
            
    return questions

@app.route('/')
def index():
    return render_template('index.html', shared_data='null')

@app.route('/quiz/<quiz_id>')
def view_quiz(quiz_id):
    if not redis: return "Redis error", 500
    quiz_data = redis.get(f"quiz:{quiz_id}")
    if not quiz_data: return "Hết hạn hoặc không tồn tại.", 404
    return render_template('index.html', shared_data=quiz_data)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    raw_text = data.get('text', '')
    questions = parse_quiz_text(raw_text)
    
    if not questions:
        return jsonify({"error": "No questions"}), 400

    share_link = None
    if redis:
        quiz_id = str(uuid.uuid4())[:8]
        redis.set(f"quiz:{quiz_id}", json.dumps(questions), ex=8640000)
        share_link = f"{request.host_url}quiz/{quiz_id}"
    
    return jsonify({"questions": questions, "share_link": share_link})

app = app