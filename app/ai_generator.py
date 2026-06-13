import os
import json
import re
import requests

def get_puter_token():
    """Retrieves Puter Auth Token from environment or Streamlit secrets."""
    token = os.environ.get("PUTER_TOKEN") or os.environ.get("PUTER_API_KEY")
    if not token:
        try:
            import streamlit as st
            token = st.secrets.get("PUTER_TOKEN") or st.secrets.get("PUTER_API_KEY")
        except Exception:
            pass
    return token

def call_ollama(prompt, model="llama3.2:latest"):
    """Queries local Ollama instance with format=json for guaranteed JSON output."""
    url = "http://localhost:11434/api/generate"
    
    # We specify format='json' to force llama3.2 to output valid JSON.
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.2
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=180)
        response.raise_for_status()
        resp_json = response.json()
        return resp_json["response"]
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            "Could not connect to Ollama. Please make sure the Ollama server is running locally "
            "(run 'ollama serve' in terminal) or select Online mode."
        )
    except Exception as e:
        raise RuntimeError(f"Ollama generation failed: {e}")

def call_puter(prompt, token, model="gpt-4o-mini"):
    """Queries Puter AI's OpenAI-compatible endpoint."""
    url = "https://api.puter.com/puterai/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system", 
                "content": (
                    "You are an expert mathematics teacher generating structured quizzes. "
                    "You must output only a valid raw JSON array containing exactly 10 multiple choice questions. "
                    "Do not wrap your output in markdown code blocks like ```json ... ```. Just return the raw JSON text."
                )
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=90)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"Puter AI generation failed: {e}")

def clean_and_parse_json(text):
    """Robustly extracts and parses a JSON array of MCQs from LLM output."""
    text_stripped = text.strip()
    
    # Attempt direct parse
    try:
        return json.loads(text_stripped)
    except Exception:
        pass
        
    # Try finding JSON block inside ```json ... ``` or just [ ... ]
    match = re.search(r'\[\s*\{.*\}\s*\]', text_stripped, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
            
    # Try cleaning markdown code markers
    clean_text = text_stripped
    if clean_text.startswith("```"):
        clean_text = re.sub(r'^```(json)?', '', clean_text)
        clean_text = re.sub(r'```$', '', clean_text)
        clean_text = clean_text.strip()
        
    try:
        return json.loads(clean_text)
    except Exception as e:
        raise ValueError(
            f"Failed to parse generated questions as a JSON list. Raw output began with:\n{text[:200]}\nError: {e}"
        )

def build_mode1_prompt(question_text: str) -> str:
    """Builds prompt for generating 10 MCQs based on a single input question."""
    ncert_instruction = ""
    # Look for class level indicators in the input question text (heuristic)
    class_match = re.search(r'\b(class|grade)\s*(8|9|10|11|12)\b', question_text, re.IGNORECASE)
    if class_match:
        cls = class_match.group(2)
        ncert_instruction = (
            f"This question relates to Class {cls}. You MUST tailor the MCQs keeping in mind the latest NCERT "
            f"textbook edition guidelines, chapter scopes, terminology, and patterns for Class {cls} maths."
        )
    else:
        # Standard warning to respect NCERT if class 8-12 math concepts are detected
        ncert_instruction = (
            "If the question deals with concepts taught in Class 8 till 12, "
            "ensure it strictly adheres to the latest NCERT syllabus, level of difficulty, and chapter scope."
        )

    prompt = f"""
You are an expert mathematics educator.
Given the following math question:
---
{question_text}
---

Create a quiz consisting of exactly 10 multiple-choice questions (MCQs).
Guidelines for the quiz:
1. Change the values and parameters intellectually to create 10 new, distinct, and unique questions based on the core mathematical concept of the provided question.
2. Ensure options contain exactly one correct answer and three plausible, unique, and non-absurd distractors. Avoid obviously wrong or garbage values.
3. Cover all possible kinds of variations, difficulty levels, and sub-types that can be asked on this mathematical concept.
4. {ncert_instruction}
5. All text, questions, and options containing math equations must use LaTeX enclosed in '$' for inline math (e.g. $x^2 + 2x + 1 = 0$) or '$$' for block equations.
6. Provide a detailed, step-by-step mathematical explanation for the correct option of each question.

You MUST respond with a valid JSON array of exactly 10 question objects. Do not write any normal text, intro, or markdown formatting outside the JSON array.
The JSON format must strictly match:
[
  {{
    "question": "Question text here. Use LaTeX $...$ for equations.",
    "options": [
      {{"text": "Option A text", "correct": false}},
      {{"text": "Option B text", "correct": true}},
      {{"text": "Option C text", "correct": false}},
      {{"text": "Option D text", "correct": false}}
    ],
    "explanation": "Detailed step-by-step mathematical solution here."
  }},
  ... (exactly 10 objects)
]
"""
    return prompt

def build_mode2_prompt(class_level: str, subject: str, topic: str, level: str, type_style: str) -> str:
    """Builds prompt for generating 10 MCQs based on parameters."""
    
    # Check if class is in 8-12 range
    class_num_match = re.search(r'\b(8|9|10|11|12)\b', class_level)
    ncert_instruction = ""
    if class_num_match:
        cls = class_num_match.group(1)
        ncert_instruction = (
            f"Since the target level is Class {cls}, you MUST keep in mind the latest NCERT textbook edition "
            f"for Class {cls} {subject}. Tailor each MCQ strictly in accordance with its curriculum scope, "
            f"terminology, theorems, and exercise standards."
        )
    
    prompt = f"""
You are an expert mathematics educator.
Professionally tailor a quiz of exactly 10 multiple-choice questions (MCQs) using these parameters:
- Class Level: {class_level}
- Subject: {subject}
- Topic/Chapter: {topic}
- Difficulty Level: {level} (Easy, Moderate, or Difficult)
- Question Type: {type_style} (Conceptual or Numerical)

Guidelines for the quiz:
1. Ensure the difficulty aligns perfectly with '{level}' for a {class_level} student, and matches the style '{type_style}' (Conceptual: testing definitions, properties, and theory; Numerical: testing calculations, problem solving, and formulas).
2. Ensure each MCQ has exactly one correct answer and three plausible, unique, and non-absurd distractors.
3. {ncert_instruction}
4. Cover a comprehensive range of subtopics within '{topic}' to provide thorough practice.
5. All text, questions, and options containing math equations must use LaTeX enclosed in '$' for inline math (e.g. $a^2 + b^2 = c^2$) or '$$' for block equations.
6. Provide a detailed, step-by-step explanation showing how to arrive at the correct answer.

You MUST respond with a valid JSON array of exactly 10 question objects. Do not write any normal text, intro, or markdown formatting outside the JSON array.
The JSON format must strictly match:
[
  {{
    "question": "Question text here. Use LaTeX $...$ for equations.",
    "options": [
      {{"text": "Option A text", "correct": false}},
      {{"text": "Option B text", "correct": true}},
      {{"text": "Option C text", "correct": false}},
      {{"text": "Option D text", "correct": false}}
    ],
    "explanation": "Detailed step-by-step explanation of the solution."
  }},
  ... (exactly 10 objects)
]
"""
    return prompt

def get_mock_questions(mode: int, data: dict) -> list:
    """Returns 10 mock math questions with LaTeX for fast E2E testing and screenshot capture."""
    topic_name = data.get("topic", "Mathematics") if mode == 2 else "Core Math"
    cls_level = data.get("class_level", "Class 10") if mode == 2 else "Class 10"
    questions = []
    
    # Generate 10 simple but realistic math questions
    for i in range(10):
        val1 = (i + 1) * 2
        val2 = (i + 1) * 3
        ans = val1 + val2
        dist1 = ans - 2
        dist2 = ans + 2
        dist3 = ans * 2
        
        questions.append({
            "question": f"In {cls_level} {topic_name} practice, what is the value of ${val1} + {val2}$?",
            "options": [
                {"text": f"${dist1}$", "correct": False},
                {"text": f"${ans}$", "correct": True},
                {"text": f"${dist2}$", "correct": False},
                {"text": f"${dist3}$", "correct": False}
            ],
            "explanation": f"We simply calculate the sum of the two terms: ${val1} + {val2} = {ans}$. Therefore, the correct answer is ${ans}$."
        })
    return questions

def generate_quiz(use_online: bool, mode: int, data: dict, puter_token: str = None) -> list:
    """Generates a list of 10 MCQs based on the mode and inputs.
    
    Args:
        use_online: If True, uses Puter AI; else Ollama.
        mode: 1 for question-based, 2 for parameter-based.
        data: Inputs dict.
        puter_token: Token for Puter AI if use_online is True.
        
    Returns:
        List of 10 parsed question dicts.
    """
    # Fast mock toggle for E2E automation and screenshot scripts
    if os.environ.get("MOCK_AI") == "true":
        return get_mock_questions(mode, data)

    if mode == 1:
        prompt = build_mode1_prompt(data["question_text"])
    elif mode == 2:
        prompt = build_mode2_prompt(
            class_level=data["class_level"],
            subject=data["subject"],
            topic=data["topic"],
            level=data["level"],
            type_style=data["type_style"]
        )
    else:
        raise ValueError("Invalid quiz generation mode.")
        
    if use_online:
        if not puter_token:
            puter_token = get_puter_token()
        if not puter_token:
            raise ValueError(
                "Puter Auth Token is missing. Please enter your Puter Auth Token or switch to Local mode."
            )
        response_text = call_puter(prompt, puter_token)
    else:
        response_text = call_ollama(prompt)
        
    return clean_and_parse_json(response_text)
