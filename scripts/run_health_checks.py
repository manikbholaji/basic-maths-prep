import os
import json
from pathlib import Path
from app.api_client import AIClient


def check_provider(provider, api_key=None):
    client = AIClient(provider=provider, api_key=api_key)
    res = client.health_check()
    return res


def main():
    providers = [
        ("Google", os.environ.get("GOOGLE_API_KEY")),
        ("Dialogflow", os.environ.get("DIALOGFLOW_ACCESS_TOKEN")),
        ("OpenAI", os.environ.get("OPENAI_API_KEY")),
    ]

    results = {}
    for name, key in providers:
        try:
            results[name] = check_provider(name, api_key=key)
        except Exception as e:
            results[name] = {"ok": False, "reason": "exception", "detail": str(e)}

    # write results to a file for CI consumption
    out_path = Path.cwd() / "health_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2))

    # Exit code: 0 always for scheduled runs to avoid failing unrelated CI.


if __name__ == '__main__':
    main()
