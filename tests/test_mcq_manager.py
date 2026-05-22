import json
import zipfile
from pathlib import Path

from app import mcq_manager


def _make_sample_zip(path: Path):
    zpath = path / "sample_curriculum.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("Addition.tex", "% Addition chapter\nThis chapter covers addition and basic sums.")
        z.writestr("Fractions.tex", "% Fractions chapter\nThis chapter covers fractions and decimals.")
    return zpath


def test_build_kb_and_sample_and_evaluate(tmp_path):
    z = _make_sample_zip(tmp_path)
    out_json = tmp_path / "mcq_out.json"
    kb = mcq_manager.build_kb_from_zip(str(z), out_path=str(out_json), regenerate=True)
    assert "mcq_bank" in kb

    # sample diagnostic (ask for 5 but we only have 6 questions total)
    sampled = mcq_manager.sample_diagnostic("middle", num_questions=5, kb=kb)
    assert isinstance(sampled, list)

    # evaluate: mark all answers as 0 (which is the correct answer in our generator)
    responses = {q["id"]: 0 for q in sampled}
    result = mcq_manager.evaluate_responses(responses, kb=kb)
    assert result.get("total", 0) == len(sampled)
    assert result.get("wrong", 0) == 0