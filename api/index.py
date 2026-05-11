import os
import re
from flask import Flask, render_template, request, jsonify

# 1. Xác định đường dẫn thư mục templates trước khi tạo app
base_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_dir, '..', 'templates')

# 2. Khởi tạo app MỘT LẦN DUY NHẤT
app = Flask(__name__, template_folder=template_dir)

def parse_quiz_text(raw_text):
    questions = []
    # Tách các khối dựa trên "Câu X:" hoặc số thứ tự "X)"
    blocks = re.split(r'(?:Câu\s*\d+[:\.]|\d+[\)\.])', raw_text)
    
    for block in blocks:
        block = block.strip()
        if not block: continue
        
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if not lines: continue
        
        q_content = lines[0]
        options = []
        correct_ans = ""
        is_mcq = False 
        
        for line in lines[1:]:
            match = re.match(r'^(\*?)\s*([A-E])[\.\)]\s*(.*)', line)
            if match:
                is_mcq = True
                is_correct = match.group(1) == '*'
                label = match.group(2)
                text = match.group(3)
                
                options.append({"label": label, "text": text})
                if is_correct:
                    correct_ans = label
            
            elif line.lower().startswith("answer:"):
                ans_content = line.split(":", 1)[1].strip()
                if len(ans_content) == 1 and ans_content.upper() in "ABCDE":
                    correct_ans = ans_content.upper()
        
        if is_mcq and options:
            questions.append({
                "question": q_content,
                "options": options,
                "answer": correct_ans
            })
    return questions

# 3. Định nghĩa các Route
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    raw_text = data.get('text', '')
    questions = parse_quiz_text(raw_text)
    return jsonify(questions)

app = app