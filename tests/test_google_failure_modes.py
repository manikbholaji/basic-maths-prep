import pytest

from app.api_client import AIClient


class DummyResp:
    def __init__(self, code=200, text='ok', data=None):
        self.status_code = code
        self.text = text
        self._data = data or {}

    def json(self):
        return self._data


def test_google_404_model_not_found(monkeypatch):
    # Force a single candidate model and simulate 404 response
    monkeypatch.setattr(AIClient, '_google_candidate_models', lambda self, api_key, preferred=None: ['missing-model'])

    def fake_post(url, json=None, timeout=20):
        return DummyResp(404, text='{"error": {"message": "Requested entity was not found"}}', data={'error': {'message': 'Requested entity was not found'}})

    monkeypatch.setattr('app.api_client.requests.post', fake_post)
    client = AIClient(provider='Google', api_key='FAKE')
    out = client.send_message([{"role": "user", "content": "Tell me about exams"}])
    assert '404' in out or 'not found' in out.lower()
    assert 'Falling back to mock reply' in out


def test_google_transient_then_success(monkeypatch):
    # Two models: first returns 503, second returns success
    monkeypatch.setattr(AIClient, '_google_candidate_models', lambda self, api_key, preferred=None: ['m1', 'm2'])

    call_log = {'calls': []}

    def fake_post(url, json=None, timeout=20):
        call_log['calls'].append(url)
        if 'm1' in url:
            return DummyResp(503, text='server error', data={'error': 'server busy'})
        # m2 returns a normal candidate
        return DummyResp(200, data={'candidates': [{'content': {'parts': [{'text': 'Hello from model m2'}]}, 'finishReason': ''}]})

    monkeypatch.setattr('app.api_client.requests.post', fake_post)
    client = AIClient(provider='Google', api_key='FAKE')
    out = client.send_message([{"role": "user", "content": "Hi"}])
    assert 'Hello from model m2' in out


def test_google_truncated_and_continuation(monkeypatch):
    # Single model that returns truncated answer first, then continuation returns rest
    monkeypatch.setattr(AIClient, '_google_candidate_models', lambda self, api_key, preferred=None: ['m1'])

    def fake_post(url, json=None, timeout=20):
        # Detect continuation payload by searching for the "Continue the answer" prompt
        try:
            contents = json.get('contents') or []
            # Look for user part containing the continuation instruction
            for item in contents:
                parts = item.get('parts') or []
                for p in parts:
                    if isinstance(p.get('text'), str) and 'Continue the answer' in p.get('text'):
                        return DummyResp(200, data={'candidates': [{'content': {'parts': [{'text': 'and the rest of the answer.'}]}, 'finishReason': ''}]})
        except Exception:
            pass
        # First partial reply
        return DummyResp(200, data={'candidates': [{'content': {'parts': [{'text': 'Partial answer...'}]}, 'finishReason': 'MAX_TOKENS'}]})

    monkeypatch.setattr('app.api_client.requests.post', fake_post)
    client = AIClient(provider='Google', api_key='FAKE')
    out = client.send_message([{"role": "user", "content": "Explain topic X"}])
    assert 'Partial answer' in out
    assert 'and the rest of the answer' in out


def test_google_request_exception(monkeypatch):
    # Simulate a network exception during requests.post
    monkeypatch.setattr(AIClient, '_google_candidate_models', lambda self, api_key, preferred=None: ['m1'])

    def fake_post(url, json=None, timeout=20):
        raise RuntimeError('network failure')

    monkeypatch.setattr('app.api_client.requests.post', fake_post)
    client = AIClient(provider='Google', api_key='FAKE')
    out = client.send_message([{"role": "user", "content": "Will this fail?"}])
    assert 'Falling back to mock reply' in out
