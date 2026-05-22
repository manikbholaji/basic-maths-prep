"""Demo script to showcase a live chatbot interaction using `app.api_client.AIClient`.

This script chooses provider based on environment variables (OPENAI_API_KEY, GOOGLE_API_KEY, or DIALOGFLOW_ACCESS_TOKEN).
If none are present, it uses Mock mode.

It sends a short conversation and saves the assistant reply to `demos/sample_chat_output.txt`.
"""
import os
import json
from datetime import datetime

# Ensure imports from app package work when this script is run directly
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.api_client import AIClient


def _select_provider_from_env():
    if os.environ.get('OPENAI_API_KEY'):
        return 'OpenAI', os.environ.get('OPENAI_API_KEY')
    if os.environ.get('GOOGLE_API_KEY'):
        return 'Google', os.environ.get('GOOGLE_API_KEY')
    if os.environ.get('DIALOGFLOW_ACCESS_TOKEN') or os.environ.get('DIALOGFLOW_PROJECT_ID'):
        return 'Dialogflow', os.environ.get('DIALOGFLOW_ACCESS_TOKEN') or os.environ.get('DIALOGFLOW_PROJECT_ID')
    return 'Mock', None


def run_demo(save_path='demos/sample_chat_output.txt'):
    provider, api_key = _select_provider_from_env()
    client = AIClient(provider=provider, api_key=api_key)

    system = "You are an experienced academic advisor for Indian students. Be concise and helpful."
    user_message = (
        "I am a Class 11 student interested in computer programming and maths. "
        "I want guidance on choosing streams, early preparation, and long-term career paths. "
        "Give a short study plan and top 3 college suggestions in India, and suggest entrance exams to consider."
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_message},
    ]

    print(f"Using provider: {provider}")
    print("Sending demo message to AI client...")

    reply = client.send_message(messages)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    timestamp = datetime.utcnow().isoformat()
    out = {
        'timestamp': timestamp,
        'provider': provider,
        'user': user_message,
        'assistant': reply,
    }

    with open(save_path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=2))

    print(f"Demo saved to {save_path}")
    return out


if __name__ == '__main__':
    result = run_demo()
    print('\nAssistant reply:\n')
    print(result['assistant'])
