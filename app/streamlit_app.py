import sys
from pathlib import Path
import os
from datetime import datetime
import streamlit as st

# Setup project pathing
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import db_manager as db
from app import ai_generator as ai
from app import ocr_manager as ocr
from app import template_manager as tm

# Initialize DB on startup
db.init_db()

# Page configuration
st.set_page_config(
    page_title="Math Quiz Studio",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Sleek CSS for Dark-Theme Glassmorphism
st.markdown("""
<style>
/* Import modern Outfit font */
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');

/* Apply font everywhere */
html, body, [class*="css"], .stText, .stMarkdown, p, h1, h2, h3, h4, h5, h6, span, label, input, button, select, textarea {
    font-family: 'Outfit', sans-serif !important;
}

/* Background gradient styling */
.stApp {
    background-color: #0A0D16 !important;
    background-image: 
        radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.06) 0%, transparent 45%), 
        radial-gradient(circle at 90% 80%, rgba(139, 92, 246, 0.06) 0%, transparent 45%) !important;
}

/* Glassmorphic card styling */
.glass-card {
    background: rgba(255, 255, 255, 0.02) !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
    border-radius: 16px !important;
    padding: 24px !important;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2) !important;
    margin-bottom: 20px !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
}

/* Text adjustments */
.header-text {
    background: linear-gradient(135deg, #60A5FA 0%, #C084FC 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 800;
    font-size: 2.8rem;
    margin-bottom: 0.5rem;
    text-align: center;
}

.subheader-text {
    color: #94A3B8;
    font-weight: 400;
    font-size: 1.1rem;
    text-align: center;
    margin-bottom: 2rem;
}

/* Button enhancements */
.stButton>button {
    background: linear-gradient(135deg, #3B82F6 0%, #8B5CF6 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.6rem 1.8rem !important;
    font-weight: 600 !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 15px rgba(59, 130, 246, 0.2) !important;
    width: auto !important;
}

.stButton>button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(139, 92, 246, 0.4) !important;
    border: none !important;
    color: white !important;
}

.stButton>button:active {
    transform: translateY(0px) !important;
}

/* Secondary/Logout button override */
.logout-btn button {
    background: transparent !important;
    color: #EF4444 !important;
    border: 1px solid #EF4444 !important;
    box-shadow: none !important;
}
.logout-btn button:hover {
    background: rgba(239, 68, 68, 0.1) !important;
    color: #EF4444 !important;
    box-shadow: none !important;
    transform: none !important;
}

/* History quiz card */
.history-card {
    background: rgba(255, 255, 255, 0.015);
    border: 1px solid rgba(255, 255, 255, 0.04);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
    transition: all 0.2s ease;
}
.history-card:hover {
    border-color: rgba(96, 165, 250, 0.3);
    background: rgba(255, 255, 255, 0.025);
}

/* Mobile responsive fixes */
@media (max-width: 768px) {
    .header-text {
        font-size: 2rem;
    }
    .stApp {
        padding: 10px !important;
    }
}
</style>
""", unsafe_allow_html=True)

# Initialize Session State Variables
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None
if "name" not in st.session_state:
    st.session_state.name = None
if "current_page" not in st.session_state:
    st.session_state.current_page = "login"
if "current_quiz" not in st.session_state:
    st.session_state.current_quiz = None
if "quiz_id" not in st.session_state:
    st.session_state.quiz_id = None
if "quiz_source" not in st.session_state:
    st.session_state.quiz_source = ""
if "ocr_result" not in st.session_state:
    st.session_state.ocr_result = ""

# Sidebar Settings & Configuration
with st.sidebar:
    st.markdown("<h2 style='text-align: center;'>📐 Configuration</h2>", unsafe_allow_html=True)
    
    if st.session_state.authenticated:
        st.markdown(f"**Hello, {st.session_state.name}!** 👋")
        st.markdown("---")
        
    # Database mode identification
    db_type = "Online MongoDB" if db.is_online_mode() else "Local SQLite"
    db_color = "#34D399" if db.is_online_mode() else "#60A5FA"
    st.markdown(
        f"**Database Status:** <span style='color: {db_color}; font-weight: bold;'>{db_type}</span>", 
        unsafe_allow_html=True
    )
    
    # AI Selection
    ai_mode = st.radio(
        "Select AI Engine",
        ["Local (Ollama)", "Online (Puter AI)"],
        index=0 if not db.is_online_mode() else 1,
        help="Ollama runs locally in your environment. Puter AI uses cloud credits."
    )
    
    use_online_ai = (ai_mode == "Online (Puter AI)")
    
    puter_token = ""
    if use_online_ai:
        token_placeholder = os.environ.get("PUTER_TOKEN", "")
        puter_token = st.text_input(
            "Puter Auth Token",
            value=token_placeholder,
            type="password",
            help="Enter your Puter Auth Token copied from puter.com account dashboard."
        )
        if puter_token:
            os.environ["PUTER_TOKEN"] = puter_token
            
    st.markdown("---")
    
    # Logout action
    if st.session_state.authenticated:
        st.markdown("<div class='logout-btn'>", unsafe_allow_html=True)
        if st.button("Log Out"):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.session_state.name = None
            st.session_state.current_page = "login"
            st.session_state.current_quiz = None
            st.session_state.quiz_id = None
            st.session_state.ocr_result = ""
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# ----------------- LOGIN / REGISTER ROUTING -----------------
if not st.session_state.authenticated:
    st.markdown("<h1 class='header-text'>Math Quiz Studio</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subheader-text'>Personalised maths quiz tailored intellectually for you</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        auth_tab1, auth_tab2 = st.tabs(["🔒 Sign In", "📝 Create Account"])
        
        with auth_tab1:
            login_username = st.text_input("Email / Username", key="login_usr").strip()
            login_password = st.text_input("Password", type="password", key="login_pwd")
            if st.button("Sign In", use_container_width=True):
                if not login_username or not login_password:
                    st.error("Please fill in all fields.")
                else:
                    user = db.authenticate_user(login_username, login_password)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.username = user["username"]
                        st.session_state.name = user["name"]
                        st.session_state.current_page = "dashboard"
                        st.success(f"Welcome back, {user['name']}!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials. Please try again.")
                        
        with auth_tab2:
            reg_name = st.text_input("Full Name", key="reg_name").strip()
            reg_username = st.text_input("Email / Username", key="reg_usr").strip()
            reg_password = st.text_input("Password", type="password", key="reg_pwd")
            if st.button("Create Account", use_container_width=True):
                if not reg_name or not reg_username or not reg_password:
                    st.error("Please fill in all fields.")
                else:
                    success = db.register_user(reg_username, reg_password, reg_name)
                    if success:
                        st.success("Account created successfully! Please sign in.")
                    else:
                        st.error("Username already exists. Please choose a different one.")
        st.markdown("</div>", unsafe_allow_html=True)

# ----------------- MAIN MAINBOARD -----------------
elif st.session_state.current_page == "dashboard":
    st.markdown(f"<h1 class='header-text'>Welcome, {st.session_state.name}!</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subheader-text'>Choose a mode below to tailor your personalized 10-MCQ mathematics quiz</p>", unsafe_allow_html=True)
    
    # Dashboard Grid Layout
    tab_mode1, tab_mode2 = st.tabs([
        "💡 Mode 1: Generate from Question", 
        "⚙️ Mode 2: Tailor from Parameters"
    ])
    
    # Mode 1: Quiz from Question
    with tab_mode1:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.write("### Provide a single mathematics question")
        st.write("We will extract/parse the question, intellectually vary values, ensure unique non-absurd answers, and cover all possible variations in a 10-MCQ quiz.")
        
        # OCR Section
        ocr_expander = st.expander("📷 Extract Question from Image/Camera (OCR)", expanded=False)
        with ocr_expander:
            ocr_col1, ocr_col2 = st.columns(2)
            with ocr_col1:
                uploaded_file = st.file_uploader("Upload question image", type=["png", "jpg", "jpeg"])
            with ocr_col2:
                camera_file = st.camera_input("Capture question image (mobile/tablet compatible)")
                
            active_image = uploaded_file or camera_file
            if active_image:
                if st.button("Run OCR Reader"):
                    with st.spinner("Extracting text via Tesseract OCR..."):
                        try:
                            extracted = ocr.perform_ocr(active_image)
                            if extracted:
                                st.session_state.ocr_result = extracted
                                st.success("Text successfully extracted! You can review it in the input area below.")
                            else:
                                st.warning("OCR complete, but no text could be recognized. Please type the question.")
                        except Exception as e:
                            st.error(f"OCR Reader failed: {e}")
                            
        # Text input area
        input_q = st.text_area(
            "Paste/Type Mathematical Question (LaTeX equations like $x^2$ supported)",
            value=st.session_state.ocr_result,
            height=150,
            placeholder="e.g., What is the area of an equilateral triangle with side length 6 cm?"
        )
        
        # Help link
        if st.session_state.ocr_result:
            if st.button("Clear OCR Input"):
                st.session_state.ocr_result = ""
                st.rerun()
                
        if st.button("Generate Question-Based Quiz"):
            if not input_q.strip():
                st.warning("Please enter a mathematical question.")
            else:
                with st.spinner("Generating 10 custom MCQs... This may take up to 2 minutes."):
                    try:
                        quiz_data = {"question_text": input_q}
                        questions = ai.generate_quiz(
                            use_online=use_online_ai,
                            mode=1,
                            data=quiz_data,
                            puter_token=puter_token
                        )
                        if len(questions) != 10:
                            # Re-verify/truncate/pad to keep it strictly 10
                            st.warning(f"AI returned {len(questions)} questions. Formatting quiz to exactly 10...")
                            questions = (questions + [{}] * 10)[:10]
                            
                        # Save quiz to DB
                        saved_id = db.save_quiz(
                            username=st.session_state.username,
                            quiz_type="question_based",
                            input_details=quiz_data,
                            questions=questions
                        )
                        
                        st.session_state.current_quiz = questions
                        st.session_state.quiz_id = saved_id
                        st.session_state.quiz_source = f"Based on: {input_q[:40]}..."
                        st.session_state.current_page = "quiz"
                        st.rerun()
                    except Exception as err:
                        st.error(f"Failed to generate quiz: {err}")
        st.markdown("</div>", unsafe_allow_html=True)
        
    # Mode 2: Tailor from parameters
    with tab_mode2:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.write("### Professionally tailor quiz from parameters")
        
        col_param1, col_param2 = st.columns(2)
        with col_param1:
            class_level = st.selectbox(
                "Class Level",
                ["Class 1", "Class 2", "Class 3", "Class 4", "Class 5", "Class 6", 
                 "Class 7", "Class 8", "Class 9", "Class 10", "Class 11", "Class 12"],
                index=9, # default Class 10
                help="Classes 8-12 will automatically tailor questions to the latest NCERT textbooks."
            )
            subject = st.text_input("Subject", value="Mathematics")
            topic = st.text_input("Topic / Chapter", placeholder="e.g., Trigonometry, Quadratic Equations, Fractions")
            
        with col_param2:
            difficulty = st.selectbox("Difficulty Level", ["Easy", "Moderate", "Difficult"], index=1)
            q_type = st.selectbox("Question Type", ["Conceptual", "Numerical"], index=1)
            
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Generate Parametric Quiz"):
            if not topic.strip():
                st.warning("Please specify a topic or chapter.")
            else:
                with st.spinner("Tailoring 10 MCQs based on parameters..."):
                    try:
                        quiz_data = {
                            "class_level": class_level,
                            "subject": subject,
                            "topic": topic,
                            "level": difficulty,
                            "type_style": q_type
                        }
                        questions = ai.generate_quiz(
                            use_online=use_online_ai,
                            mode=2,
                            data=quiz_data,
                            puter_token=puter_token
                        )
                        if len(questions) != 10:
                            questions = (questions + [{}] * 10)[:10]
                            
                        # Save quiz to DB
                        saved_id = db.save_quiz(
                            username=st.session_state.username,
                            quiz_type="parameter_based",
                            input_details=quiz_data,
                            questions=questions
                        )
                        
                        st.session_state.current_quiz = questions
                        st.session_state.quiz_id = saved_id
                        st.session_state.quiz_source = f"{class_level} • {topic} ({difficulty} - {q_type})"
                        st.session_state.current_page = "quiz"
                        st.rerun()
                    except Exception as err:
                        st.error(f"Failed to tailor quiz: {err}")
        st.markdown("</div>", unsafe_allow_html=True)

    # ----------------- QUIZ HISTORY -----------------
    st.markdown("<h2 style='margin-top: 2rem;'>📚 Your Quiz History</h2>", unsafe_allow_html=True)
    history = db.get_user_quizzes(st.session_state.username)
    
    if not history:
        st.info("You haven't generated any quizzes yet. Generate your first quiz above!")
    else:
        for item in history:
            quiz_type_str = "Question-Based" if item["quiz_type"] == "question_based" else "Parametric"
            
            if item["quiz_type"] == "question_based":
                source_detail = item["input_details"].get("question_text", "")
                title_str = f"📝 Quiz: {source_detail[:60]}..."
            else:
                p = item["input_details"]
                title_str = f"⚙️ {p.get('class_level', '')} Math: {p.get('topic', '')}"
                source_detail = f"Level: {p.get('level')}, Type: {p.get('type_style')}"
                
            created_dt = item.get("created_at", "")
            try:
                # Format timestamp
                dt_obj = datetime.fromisoformat(created_dt)
                formatted_date = dt_obj.strftime("%b %d, %Y - %I:%M %p")
            except Exception:
                formatted_date = created_dt
                
            # Render history item card
            hist_col1, hist_col2 = st.columns([5, 1])
            with hist_col1:
                st.markdown(f"""
                <div class="history-card">
                    <strong style="font-size: 1.1rem; color: #60A5FA;">{title_str}</strong><br>
                    <span style="color: #94A3B8; font-size: 0.9rem;">{source_detail}</span><br>
                    <span style="color: #64748B; font-size: 0.8rem;">Generated: {formatted_date} • {quiz_type_str}</span>
                </div>
                """, unsafe_allow_html=True)
            with hist_col2:
                # Vertically spacing button a bit
                st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                if st.button("Practice Again", key=f"redo_{item['quiz_id']}"):
                    st.session_state.current_quiz = item["questions"]
                    st.session_state.quiz_id = item["quiz_id"]
                    st.session_state.quiz_source = title_str
                    st.session_state.current_page = "quiz"
                    st.rerun()

# ----------------- QUIZ RUNNER VIEW -----------------
elif st.session_state.current_page == "quiz":
    st.markdown(f"<h1 class='header-text'>Active Quiz</h1>", unsafe_allow_html=True)
    st.markdown(f"<p class='subheader-text'>{st.session_state.quiz_source}</p>", unsafe_allow_html=True)
    
    # Generate interactive HTML template with current quiz questions
    try:
        quiz_html = tm.generate_quiz_html(st.session_state.current_quiz, user_name=st.session_state.name)
        
        # Display the HTML strictly matching Quiz.html template in an iframe
        st.components.v1.html(quiz_html, height=800, scrolling=True)
    except Exception as e:
        st.error(f"Could not load quiz template: {e}")
        
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⬅️ Back to Dashboard", key="back_to_dashboard_btn"):
        st.session_state.current_page = "dashboard"
        st.session_state.current_quiz = None
        st.session_state.quiz_id = None
        st.session_state.quiz_source = ""
        st.rerun()
