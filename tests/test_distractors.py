from app import mcq_manager


def test_fraction_distractors():
    q = {"question": "What is 1/2 + 1/3?", "choices": ["5/6", "1/2", "2/3", "3/4"], "answer": 0}
    opts = mcq_manager._generate_distractors_for_question(q, n_opts=4)
    assert isinstance(opts, list)
    assert len(opts) == 4
    assert opts[0] == "5/6"


def test_decimal_distractors():
    q = {"question": "Value is 0.25", "choices": ["0.25", "0.5", "0.025", "1"], "answer": 0}
    opts = mcq_manager._generate_distractors_for_question(q, n_opts=4)
    assert isinstance(opts, list)
    assert len(opts) == 4
    assert opts[0] == "0.25"


def test_integer_distractors():
    q = {"question": "What is 3 + 4?", "choices": ["7", "6", "8", "5"], "answer": 0}
    opts = mcq_manager._generate_distractors_for_question(q, n_opts=4)
    assert isinstance(opts, list)
    assert len(opts) == 4
    assert opts[0] == "7"


def test_non_numeric_fallback():
    q = {"question": "Name the shape", "answer": "Circle"}
    opts = mcq_manager._generate_distractors_for_question(q, n_opts=4)
    assert isinstance(opts, list)
    assert len(opts) == 4
    assert opts[0] == "Circle"


def test_generate_variant_question_uses_distractors():
    q = {"id": "q1", "question": "What is 2+2?", "choices": ["4"], "answer": 0}
    v = mcq_manager.generate_variant_question(q, variant_index=1)
    assert isinstance(v, dict)
    assert "choices" in v
    assert len(v["choices"]) == 4
    assert v["answer"] == 0
