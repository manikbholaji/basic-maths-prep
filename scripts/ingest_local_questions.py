"""Ingest local study files from a folder and merge heuristic MCQs into mcq_kb.json.

Usage: run from repo root or use the full python path.
"""
from pathlib import Path
import json
import re
import sys
import os

ROOT = Path(r"H:\Other computers\My Computer (1)")

# Import helpers from app.mcq_manager
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import mcq_manager

KB_PATH = mcq_manager.KB_FILE

EXTS = {'.tex', '.md', '.txt', '.docx', '.pdf'}


def _make_domain_id(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or title


def generate_questions_for(title: str, brief: str):
    domain_id = _make_domain_id(title)
    questions = []
    q1 = {
        "id": f"{domain_id}-1",
        "question": f"Which best describes '{title}'?",
        "choices": [
            brief[:80],
            "A topic about number patterns and simple operations.",
            "A topic about English grammar and comprehension.",
            "A topic about computer programming basics.",
        ],
        "answer": 0,
        "explanation": brief,
    }
    questions.append(q1)
    q2 = {
        "id": f"{domain_id}-2",
        "question": f"True or False: {title} requires understanding of numeric computation or algebraic manipulation.",
        "choices": ["True", "False", "Sometimes", "None of these"],
        "answer": 0,
        "explanation": "Most maths topics require numeric or algebraic thinking; review the topic notes.",
    }
    questions.append(q2)
    q3 = {
        "id": f"{domain_id}-3",
        "question": f"Which skill is most related to {title}?",
        "choices": [
            "Problem solving & practice",
            "Poetry recitation",
            "Map reading",
            "Cooking recipes",
        ],
        "answer": 0,
        "explanation": "Mathematics topics connect to problem solving and numeric practice.",
    }
    questions.append(q3)
    return domain_id, title, questions


def ingest(root: Path):
    if not root.exists():
        print("Path does not exist:", root)
        return

    kb = mcq_manager.load_kb() or {"levels": mcq_manager.LEVELS, "mcq_bank": {}}
    added = 0
    scanned = 0

    for dirpath, dirnames, filenames in os.walk(root):
        for fname in filenames:
            p = Path(dirpath) / fname
            if p.suffix.lower() not in EXTS:
                continue
            scanned += 1
            try:
                if p.suffix.lower() == '.docx':
                    try:
                        from docx import Document

                        doc = Document(p)
                        raw = "\n".join([para.text for para in doc.paragraphs])
                    except Exception:
                        raw = ""
                elif p.suffix.lower() == '.pdf':
                    try:
                        from PyPDF2 import PdfReader

                        reader = PdfReader(str(p))
                        pages = []
                        for pg in reader.pages:
                            try:
                                text = pg.extract_text() or ""
                            except Exception:
                                text = ""
                            pages.append(text)
                        raw = "\n".join(pages)
                        # if extracted text is empty, try OCR using pdf2image + pytesseract
                        if not raw.strip():
                            try:
                                from pdf2image import convert_from_path
                                import pytesseract
                                imgs = convert_from_path(str(p), dpi=200)
                                ocr_texts = []
                                for im in imgs:
                                    try:
                                        t = pytesseract.image_to_string(im)
                                    except Exception:
                                        t = ""
                                    ocr_texts.append(t)
                                raw = "\n".join(ocr_texts)
                            except Exception:
                                # graceful fallback: keep raw as is
                                pass
                    except Exception:
                        raw = ""
                else:
                    raw = p.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                raw = ""
            title = mcq_manager._clean_title(str(p))
            level = mcq_manager._choose_level_from_name(str(p))
            brief = mcq_manager._extract_brief(raw)
            domain_id, title, questions = generate_questions_for(title, brief)

            level_node = kb.setdefault("mcq_bank", {}).setdefault(level, {})
            domains = level_node.setdefault("domains", {})
            if domain_id in domains:
                # append with new ids to avoid collision
                existing = domains[domain_id].get("questions", [])
                base = len(existing) + 1
                for idx, q in enumerate(questions, start=base):
                    q_new = dict(q)
                    q_new["id"] = f"{domain_id}-{idx}"
                    existing.append(q_new)
                    added += 1
                domains[domain_id]["questions"] = existing
            else:
                domains[domain_id] = {
                    "title": title,
                    "source_file": str(p),
                    "brief": brief,
                    "auto_generated": True,
                    "questions": questions,
                }
                added += len(questions)

    # persist KB
    try:
        KB_PATH.write_text(json.dumps(kb, indent=2, ensure_ascii=False), encoding='utf-8')
    except Exception as e:
        print("Failed to write KB:", e)

    print(f"Scanned files: {scanned}; Questions added: {added}")


if __name__ == '__main__':
    ingest(ROOT)
