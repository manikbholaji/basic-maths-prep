import os
import json
import types
import pytest

from app.api_client import AIClient


class DummyResp:
    def __init__(self, code=200, text='ok', data=None):
        self.status_code = code
        self.text = text
        self._data = data or {}

    def json(self):
        return self._data


def test_google_health_check(monkeypatch):
    # Mock requests.get to simulate Google models endpoint
    def fake_get(url, timeout=5):
        assert 'generativelanguage.googleapis.com' in url
        return DummyResp(200, text='ok', data={'models': []})

    monkeypatch.setattr('app.api_client.requests.get', fake_get)
    client = AIClient(provider='Google', api_key='FAKE_KEY')
    res = client.health_check()
    assert isinstance(res, dict)
    assert res.get('ok') is True


def test_dialogflow_health_check(monkeypatch):
    # Mock requests.post to simulate Dialogflow detectIntent
    def fake_post(url, headers=None, json=None, timeout=5):
        assert 'dialogflow.googleapis.com' in url
        return DummyResp(200, text='ok', data={'queryResult': {'fulfillmentText': 'pong'}})

    monkeypatch.setenv('DIALOGFLOW_PROJECT_ID', 'demo-project')
    monkeypatch.setenv('DIALOGFLOW_ACCESS_TOKEN', 'FAKE_TOKEN')
    monkeypatch.setattr('app.api_client.requests.post', fake_post)
    client = AIClient(provider='Dialogflow')
    res = client.health_check()
    assert res.get('ok') is True


def test_openai_health_check_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = AIClient(provider='OpenAI', api_key=None)
    res = client.health_check()
    assert res.get('ok') is False
    assert res.get('reason') == 'no_api_key'
