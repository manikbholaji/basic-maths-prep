from app import mcq_manager


def test_percent_distractors():
    q = {"question": "What is 25% of 200?", "choices": ["50"], "answer": 0}
    opts = mcq_manager._generate_distractors_for_question(q, n_opts=4)
    assert isinstance(opts, list)
    assert len(opts) == 4
    # expect percent style options (strings containing '%') or numeric alternatives
    assert any('%' in o or o.isdigit() for o in opts)


def test_mixed_fraction_distractors():
    q = {"question": "Convert 1 1/2 to an improper fraction", "choices": ["3/2"], "answer": 0}
    opts = mcq_manager._generate_distractors_for_question(q, n_opts=4)
    assert opts[0] == "3/2"
    assert len(opts) == 4


def test_algebraic_distractors():
    q = {"question": "Solve 2x + 3 = 11", "choices": ["4"], "answer": 0}
    opts = mcq_manager._generate_distractors_for_question(q, n_opts=4)
    assert opts[0] == "4"
    assert any(o != "4" for o in opts[1:])
