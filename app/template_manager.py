import os
import re

TEMPLATE_PATH = os.path.join("data", "Quiz.html")

def generate_quiz_html(questions_list, user_name="Student") -> str:
    """Injects generated questions into the Quiz.html template and prepares it for rendering.
    
    Args:
        questions_list: A list of 10 question dicts.
        user_name: Pre-populated name for personalization.
        
    Returns:
        The full modified HTML content as a string.
    """
    if not os.path.exists(TEMPLATE_PATH):
        raise FileNotFoundError(f"Quiz template not found at {TEMPLATE_PATH}")
        
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    # 1. Add MathJax in head for high-quality LaTeX rendering
    mathjax_script = """
    <script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    <script>
    window.MathJax = {
      tex: {
        inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
        displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']]
      },
      options: {
        skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre']
      }
    };
    </script>
    """
    # Insert before </head>
    html_content = html_content.replace("</head>", f"{mathjax_script}\n</head>")
    
    # 2. Pre-fill user name in the input field
    html_content = html_content.replace(
        'value=""', f'value="{user_name}"'
    ).replace(
        'placeholder="Enter your name"', f'placeholder="Enter your name" value="{user_name}"'
    )
    
    # 3. Generate HTML question containers
    questions_html = ""
    for i, q in enumerate(questions_list):
        q_num = i + 1
        questions_html += f"""
    <!-- Question {q_num} -->
    <div class="question-container" id="question{q_num}" style="display: none;">
        <div class="question">
            <p>{q['question']}</p>
            <div class="options" id="options{q_num}">
        """
        for opt in q['options']:
            is_correct = "true" if opt.get('correct', False) else "false"
            questions_html += f'                <div class="option" data-correct="{is_correct}">{opt["text"]}</div>\n'
            
        # Add detailed explanation container
        explanation_content = q.get('explanation', '').replace('"', '&quot;')
        questions_html += f"""            </div>
            <div class="explanation" data-custom="true" style="display: none; margin-top: 15px; font-style: italic; color: #444; border-left: 3px solid #5B8DFF; padding-left: 10px; background-color: #f9f9f9; padding-top: 8px; padding-bottom: 8px; border-radius: 0 4px 4px 0;">
                {explanation_content}
            </div>
        </div>
    </div>
        """
        
    # 4. Replace hardcoded question containers in the template
    # The questions are located between '<div class="progress-status" id="progressStatus"></div>' and '<!-- Progress Bar -->'
    pattern = r'(<div class="progress-status" id="progressStatus"></div>).*?(<!-- Progress Bar -->)'
    html_content = re.sub(
        pattern, 
        rf'\1\n{questions_html}\n    \2', 
        html_content, 
        flags=re.DOTALL
    )
    
    # 5. Adapt submitQuiz JavaScript to display custom explanation
    old_explanation_js = 'explanation.innerHTML = `Correct answer: ${correctOption.innerHTML}`;'
    new_explanation_js = """
        if (explanation.getAttribute('data-custom') === 'true') {
            explanation.style.display = 'block';
            explanation.innerHTML = `<strong>Correct Answer:</strong> ${correctOption.innerHTML}<br><br><strong>Explanation:</strong> ${explanation.innerHTML.trim()}`;
        } else {
            explanation.innerHTML = `Correct answer: ${correctOption.innerHTML}`;
        }
    """
    html_content = html_content.replace(old_explanation_js, new_explanation_js)
    
    # 6. Adapt showPreviousResult JavaScript to clear custom explanation formatting on retry
    old_show_prev_js = """function showPreviousResult() {
  	let quizSubmitted = false;
    resultPage.style.display = 'none';
    document.querySelector('.quiz-container').style.display = 'block';
    updateOptionColors();
    showQuestion(currentQuestion);
}"""
    # Change let quizSubmitted to global quizSubmitted and hide explanations
    new_show_prev_js = """function showPreviousResult() {
    quizSubmitted = false;
    resultPage.style.display = 'none';
    document.querySelector('.quiz-container').style.display = 'block';
    // Hide all explanation blocks
    document.querySelectorAll('.explanation').forEach(el => {
        el.style.display = 'none';
        // reset if it was custom
        if (el.getAttribute('data-custom') === 'true') {
            const lines = el.innerHTML.split('<br><br><strong>Explanation:</strong>');
            if (lines.length > 1) {
                el.innerHTML = lines[1].replace('<strong>Explanation:</strong>', '').trim();
            }
        }
    });
    updateOptionColors();
    showQuestion(currentQuestion);
}"""
    html_content = html_content.replace(old_show_prev_js, new_show_prev_js)
    
    return html_content
