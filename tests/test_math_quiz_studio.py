import os
import json
import pytest
from app import db_manager as db
from app import ai_generator as ai
from app import ocr_manager as ocr
from app import template_manager as tm

@pytest.fixture(autouse=True)
def setup_test_db():
    """Cleans up the database file before and after tests."""
    # Ensure test runs on local SQLite
    if os.environ.get("MONGODB_URI"):
        del os.environ["MONGODB_URI"]
        
    db_file = os.path.join("data", "local_quiz.db")
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass
            
    db.init_db()
    yield
    
    # Cleanup again
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass

def test_user_auth():
    """Tests password hashing, registration, and login verification."""
    username = "test_user@example.com"
    password = "secretpassword"
    name = "Test User"
    
    # Test registration
    registered = db.register_user(username, password, name)
    assert registered is True
    
    # Test duplicate registration
    duplicate = db.register_user(username, password, name)
    assert duplicate is False
    
    # Test authentication success
    user = db.authenticate_user(username, password)
    assert user is not None
    assert user["username"] == username
    assert user["name"] == name
    
    # Test authentication failure
    wrong_pwd = db.authenticate_user(username, "wrongpassword")
    assert wrong_pwd is None
    
    wrong_usr = db.authenticate_user("wrong_user", password)
    assert wrong_usr is None

def test_quiz_storage():
    """Tests saving and retrieving quizzes from the database."""
    username = "quiz_user@example.com"
    db.register_user(username, "pass", "Quiz User")
    
    input_details = {"question_text": "Solve $x + 2 = 5$"}
    questions = [
        {
            "question": "Solve $x + 2 = 5$",
            "options": [
                {"text": "$2$", "correct": False},
                {"text": "$3$", "correct": True},
                {"text": "$4$", "correct": False},
                {"text": "$5$", "correct": False}
            ],
            "explanation": "Subtract 2 from both sides."
        }
    ]
    
    # Save quiz
    quiz_id = db.save_quiz(username, "question_based", input_details, questions)
    assert quiz_id is not None
    assert len(quiz_id) > 0
    
    # Retrieve specific quiz
    retrieved = db.get_quiz(quiz_id)
    assert retrieved is not None
    assert retrieved["username"] == username
    assert retrieved["quiz_type"] == "question_based"
    assert retrieved["input_details"] == input_details
    assert len(retrieved["questions"]) == 1
    assert retrieved["questions"][0]["question"] == "Solve $x + 2 = 5$"
    
    # Retrieve user quiz history
    history = db.get_user_quizzes(username)
    assert len(history) == 1
    assert history[0]["quiz_id"] == quiz_id

def test_mock_ai_generation():
    """Tests the Mock AI generation capability."""
    os.environ["MOCK_AI"] = "true"
    
    param_data = {
        "class_level": "Class 10",
        "subject": "Mathematics",
        "topic": "Trigonometry",
        "level": "Moderate",
        "type_style": "Numerical"
    }
    
    questions = ai.generate_quiz(use_online=False, mode=2, data=param_data)
    assert len(questions) == 10
    
    for i, q in enumerate(questions):
        assert "question" in q
        assert "options" in q
        assert "explanation" in q
        assert len(q["options"]) == 4
        # Verify exactly one correct answer
        correct_count = sum(1 for opt in q["options"] if opt.get("correct") is True)
        assert correct_count == 1
        
    del os.environ["MOCK_AI"]

def test_template_manager():
    """Tests HTML generation by template_manager."""
    questions = [
        {
            "question": "Solve $y - 3 = 7$",
            "options": [
                {"text": "$4$", "correct": False},
                {"text": "$10$", "correct": True}
            ],
            "explanation": "Add 3 to both sides."
        }
    ]
    
    html = tm.generate_quiz_html(questions, user_name="Alex")
    assert html is not None
    # Verify name injected
    assert "Alex" in html
    # Verify question injected
    assert "Solve $y - 3 = 7$" in html
    # Verify custom explanation check injected
    assert "data-custom" in html
    # Verify MathJax support loaded
    assert "MathJax-script" in html

def test_ocr_fallback():
    """Tests OCR manager initialization and fallback finding."""
    binary = ocr.find_tesseract_binary()
    # If binary is not found, verify perform_ocr raises FileNotFoundError
    if not binary:
        with pytest.raises(FileNotFoundError):
            ocr.perform_ocr(None)
