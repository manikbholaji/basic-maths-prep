from streamlit.testing.v1 import AppTest


def _load_app():
    return AppTest.from_file("app/basic_maths_app.py").run(timeout=20)


def test_appointments_page_exposes_auto_schedule_action():
    at = _load_app()

    at.radio[0].set_value("Appointments")
    at = at.run(timeout=20)

    assert any(button.label == "Auto-schedule next slot" for button in at.button)
    assert any(selectbox.label == "Session focus" for selectbox in at.selectbox)
