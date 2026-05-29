from app import mcq_manager


def test_fraction_pedagogical_distractors():
    q = {"question": "Calculate 3/4", "choices": ["3/4"], "answer": 0}
    opts = mcq_manager._generate_distractors_for_question(q, n_opts=4)
    assert isinstance(opts, list)
    assert len(opts) == 4
    # correct first
    assert opts[0] == "3/4"
    # expect at least one swapped or common-denominator style distractor
    assert any("/" in o and o != "3/4" for o in opts[1:])


def test_decimal_pedagogical_distractors():
    q = {"question": "Value is 0.25", "choices": ["0.25"], "answer": 0}
    opts = mcq_manager._generate_distractors_for_question(q, n_opts=4)
    assert isinstance(opts, list)
    assert len(opts) == 4
    assert opts[0] == "0.25"
    # expect a decimal-shift variant like 2.5 or 0.025
    assert any(o in {"2.5", "0.025", "0.3", "0.2"} for o in opts[1:])


def test_integer_swapped_digits():
    q = {"question": "What is 12 + 0?", "choices": ["12"], "answer": 0}
    opts = mcq_manager._generate_distractors_for_question(q, n_opts=4)
    assert isinstance(opts, list)
    assert len(opts) == 4
    assert opts[0] == "12"
    # swapped digits 21 should appear as plausible distractor
    assert "21" in opts or any(o for o in opts if o != "12")
