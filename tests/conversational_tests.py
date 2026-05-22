from app.api_client import AIClient


def run_sample_tests():
    client = AIClient(provider="Mock")
    samples = [
        {"role": "user", "content": "Which courses should I take to learn programming?"},
        {"role": "user", "content": "How does the grading policy work?"},
    ]
    for s in samples:
        resp = client.send_message([{"role":"system","content":"You are a helpful academic advisor."}, s])
        print("Q:", s["content"])
        print("A:", resp)
        assert resp and len(resp) > 0

if __name__ == "__main__":
    run_sample_tests()
