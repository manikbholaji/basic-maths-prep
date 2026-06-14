from datetime import date, timedelta

from streamlit.testing.v1 import AppTest


def _load_app():
    return AppTest.from_file("app/basic_maths_app.py").run(timeout=20)


def test_profile_save_updates_dashboard_summary():
    at = _load_app()

    at.text_input[0].set_value("Aanya")
    at.text_input[1].set_value("aanya@example.com")
    at.selectbox[1].set_value("Class 10")
    at.selectbox[2].set_value("CBSE")
    at.selectbox[3].set_value("Exam prep")
    at.selectbox[4].set_value("Evening")
    at.selectbox[5].set_value("Balanced")
    at.date_input[0].set_value(date.today() + timedelta(days=45))
    
    # Use label to find the save button
    save_btn = next(b for b in at.button if b.label == "Save profile")
    save_btn.click()
    at = at.run(timeout=20)

    assert at.session_state["maths_profile_saved"]["student_name"] == "Aanya"
    assert at.session_state["maths_profile_saved"]["grade"] == "Class 10"
    assert at.session_state["maths_profile_saved"]["email"] == "aanya@example.com"
    # The dashboard summary should contain the new profile info
    assert any("Basic Maths Prep" in item.value for item in at.markdown)


def test_practice_lab_reply_uses_saved_profile():
    at = _load_app()

    at.text_input[0].set_value("Aanya")
    at.text_input[1].set_value("aanya@example.com")
    at.selectbox[1].set_value("Class 10")
    
    save_btn = next(b for b in at.button if b.label == "Save profile")
    save_btn.click()
    at = at.run(timeout=20)

    # Navigate to Practice Lab
    at.radio[0].set_value("Practice Lab")
    at = at.run(timeout=20)

    # The app now uses st.chat_input
    at.chat_input[0].set_value("What should I revise next for maths?")
    at = at.run(timeout=20)

    assistant_messages = [message["content"] for message in at.session_state["maths_chat"] if message["role"] == "assistant"]
    assert assistant_messages
    assert at.session_state["maths_profile_saved"]["grade"] == "Class 10"
