from flask import Flask, render_template, request, jsonify
import re

app = Flask(__name__)

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
        is_mcq = False # Cờ kiểm tra xem có phải trắc nghiệm không
        
        for line in lines[1:]:
            # Regex nhận diện các lựa chọn A, B, C, D, E
            match = re.match(r'^(\*?)\s*([A-E])[\.\)]\s*(.*)', line)
            if match:
                is_mcq = True
                is_correct = match.group(1) == '*'
                label = match.group(2)
                text = match.group(3)
                
                options.append({"label": label, "text": text})
                if is_correct:
                    correct_ans = label
            
            # Nếu dòng bắt đầu bằng "Answer:", kiểm tra nếu chưa có correct_ans từ dấu *
            elif line.lower().startswith("answer:"):
                ans_content = line.split(":", 1)[1].strip()
                # Nếu Answer là một chữ cái đơn lẻ (A, B, C...)
                if len(ans_content) == 1 and ans_content.upper() in "ABCDE":
                    correct_ans = ans_content.upper()
                # Nếu là Answer dạng văn bản dài -> đây là câu tự luận, cờ is_mcq vẫn là False
        
        # Chỉ thêm vào danh sách nếu là câu hỏi trắc nghiệm (có các option)
        if is_mcq and options:
            questions.append({
                "question": q_content,
                "options": options,
                "answer": correct_ans
            })
    return questions

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    raw_text = data.get('text', '')
    questions = parse_quiz_text(raw_text)
    return jsonify(questions)

app = Flask(__name__)

if __name__ == '__main__':
    app.run(debug=True)