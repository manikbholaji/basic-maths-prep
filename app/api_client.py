import os
import importlib
import requests
import json

try:
    import openai
except Exception:
    openai = None

try:
    # New OpenAI client (v1+)
    from openai import OpenAI as OpenAIClientClass
except Exception:
    OpenAIClientClass = None


# Module-level cache for Google models to avoid repeated discovery network calls
_GOOGLE_DISCOVERY_CACHE = {}

class AIClient:
    """AI client wrapper supporting modern OpenAI Python client or a mock responder.

    Behavior:
      - If OpenAI v1+ client is available, uses `OpenAI()` and `client.chat.completions.create(...)`.
      - If that fails and the old `openai.ChatCompletion` exists, tries it (but may raise migration errors).
      - Otherwise falls back to a small rule-based mock reply for offline testing.

    Usage:
        client = AIClient(provider='OpenAI')
        reply = client.send_message(messages)
    """

    def __init__(self, provider="OpenAI", api_key=None, model="auto"):
        self.provider = provider.lower()
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") if self.provider == "openai" else (api_key or os.environ.get("GOOGLE_API_KEY"))
        self.model = self._normalize_model(self.provider, model)
        self.client = None

        if self.provider == "openai" and self.api_key:
            # Prefer new OpenAI client when available
            if OpenAIClientClass is not None:
                try:
                    self.client = OpenAIClientClass(api_key=self.api_key)
                except Exception:
                    self.client = None
            # If new client unavailable, try to set api key on legacy module
            if self.client is None and openai is not None:
                try:
                    openai.api_key = self.api_key
                except Exception:
                    pass

    def _normalize_model(self, provider, model):
        value = (model or "").strip()
        if value.lower() in ("", "auto", "default"):
            if provider == "openai":
                return "gpt-4o-mini"
            if provider == "google":
                return "gemini-1.5-flash"
            return "auto"
        # If model name looks like OpenAI but provider is Google, fix it
        if provider == "google" and value.startswith("gpt-"):
            return "gemini-1.5-flash"
        return value

    def send_message(self, messages):
        # New OpenAI client usage
        # capture last user text for helpful fallbacks
        text = messages[-1]["content"] if isinstance(messages, list) and messages else str(messages)

        # Google provider via REST API
        if self.provider.lower() == "google":
            api_key = self.api_key or os.environ.get("GOOGLE_API_KEY")
            return self._google_reply(messages, api_key)

        # Dialogflow provider via REST API
        if self.provider.lower() == "dialogflow":
            return self._dialogflow_reply(messages)

        if self.provider.lower() == "openai" and self.client is not None:
            try:
                resp = self.client.chat.completions.create(model=self.model, messages=messages)
                # Extract content safely
                try:
                    return resp.choices[0].message.content.strip()
                except Exception:
                    return str(resp)
            except Exception as e:
                msg = str(e)
                # Handle quota error explicitly
                if "insufficient_quota" in msg or "quota" in msg or "429" in msg:
                    return "[OpenAI error] Quota exceeded. Please check your OpenAI billing/plan. Falling back to mock reply:\n" + self._mock_reply(text)
                # Handle migration / deprecated ChatCompletion usage
                if "ChatCompletion" in msg and ("removed" in msg or "no longer supported" in msg or "APIRemovedInV1" in msg):
                    return "[OpenAI error] SDK migration issue: ChatCompletion is removed in the installed openai package. Either pin `openai==0.28` or migrate to the new API. Falling back to mock reply:\n" + self._mock_reply(text)
                # Try legacy module only if it looks safe
                try:
                    if openai is not None and hasattr(openai, "ChatCompletion"):
                        legacy = openai.ChatCompletion.create(model=self.model, messages=messages)
                        return legacy.choices[0].message.content.strip()
                except Exception:
                    pass
                return f"[OpenAI client error] {msg} | Falling back to mock reply:\n" + self._mock_reply(text)

        # Legacy openai module (may be present but deprecated)
        if self.provider.lower() == "openai" and openai is not None and self.api_key:
            try:
                resp = openai.ChatCompletion.create(model=self.model, messages=messages)
                return resp.choices[0].message.content.strip()
            except Exception as e:
                return f"[OpenAI error] {e}"

        # Mock reply for offline/dev mode
        text = messages[-1]["content"] if isinstance(messages, list) and messages else str(messages)
        return self._mock_reply(text)

    def _mock_reply(self, text):
        # Very small rule-based fallback for offline testing
        text = (text or "").lower()
        if any(keyword in text for keyword in ["stream", "humanities", "commerce", "medical", "non-medical"]):
            return (
                "For stream selection after Class 10, compare your strongest subjects, preferred learning style, and long-term goals. "
                "Humanities suits students who enjoy writing, history, civics, or psychology; Commerce fits business, economics, and accountancy; "
                "Medical suits biology-heavy paths; Non-medical suits maths, physics, and engineering interest. Share your marks and interests for a sharper recommendation."
            )
        if "class 10" in text or "board" in text or "class 11" in text or "class 12" in text:
            return (
                "For board exam prep, start with the official syllabus, split chapters into weekly targets, and revise textbook exercises first. "
                "If you tell me your class and board, I can make a sharper study plan."
            )
        if "course" in text or "subject" in text or "programming" in text:
            return "Focus on strong foundations first: mathematics, science, language, and one practical skill. Share your class and board for a tailored roadmap."
        if "career" in text or "job" in text or "internship" in text:
            return "Think about school performance, stream choice after Class 10, and skills that fit your strengths. I can suggest paths based on your goals."
        if "grading" in text or "grade" in text or "policy" in text or "attendance" in text:
            return "Check your board and school rules first. Attendance, internal assessment, and board exam prep all matter; I can explain the exact flow if you share your board."
        return f"[Academic advisor mode] I heard: '{text[:200]}'. Tell me your board, class, and goal, and I’ll guide you step by step."

    def _google_reply(self, messages, api_key):
        """Call Google's Generative Language API (Gemini) via REST.

        Falls back to mock reply on any error.
        """
        text = messages[-1]["content"] if isinstance(messages, list) and messages else str(messages)
        if not api_key:
            return "[Google error] No API key configured. Falling back to mock reply:\n" + self._mock_reply(text)

        model_candidates = self._google_candidate_models(api_key, self.model)
        if not model_candidates:
            return "[Google error] No Gemini model with generateContent support was found for this key. Falling back to mock reply:\n" + self._mock_reply(text)
        payload = {
            "systemInstruction": {
                "parts": [{"text": "You are a helpful academic advisor for students. Use the conversation context when answering follow-up questions."}]
            },
            "contents": self._google_build_contents(messages),
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048,
            },
        }

        last_error = None
        for model_name in model_candidates:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            try:
                resp = requests.post(url, json=payload, timeout=20)
                if resp.status_code == 200:
                    answer, finish_reason = self._google_extract_text_and_finish(resp.json())
                    if finish_reason == "MAX_TOKENS" and answer:
                        answer = self._google_continue_answer(api_key, model_name, payload, answer)
                    return answer

                try:
                    err = resp.json()
                except Exception:
                    err = resp.text

                last_error = f"[Google API error] {resp.status_code}: {err}"

                # Model missing or unsupported: try the next discovered model.
                if resp.status_code == 404 and self._google_is_model_not_found_error(err):
                    continue

                # High demand / transient failures: try next model instead of immediate mock fallback.
                # 500/503/429 are commonly transient for generative endpoints.
                if resp.status_code in (500, 503, 429):
                    continue

                # Other hard failures stop the loop; returning immediately keeps the real error visible.
                return last_error + " | Falling back to mock reply:\n" + self._mock_reply(text)
            except Exception as e:
                last_error = f"[Google request error] {e}"
                continue

        if last_error:
            return last_error + " | Falling back to mock reply:\n" + self._mock_reply(text)
        return "[Google error] No response from Google models. Falling back to mock reply:\n" + self._mock_reply(text)

    def _google_build_contents(self, messages):
        """Convert Streamlit chat history into Gemini contents.

        Gemini expects a sequence of user/model turns. We keep the full conversation
        so follow-up questions can resolve references like 'it', 'that', or 'them'.
        """
        contents = []
        if not isinstance(messages, list):
            return [{"role": "user", "parts": [{"text": str(messages)}]}]

        for message in messages:
            role = (message.get("role") or "user").lower()
            text = message.get("content", "")
            if role == "system":
                # System prompt is passed separately as systemInstruction.
                continue
            if role == "assistant":
                contents.append({"role": "model", "parts": [{"text": text}]})
            else:
                contents.append({"role": "user", "parts": [{"text": text}]})

        if not contents:
            contents.append({"role": "user", "parts": [{"text": ""}]})
        return contents

    def _google_extract_text(self, data):
        """Extract Gemini text from a successful generateContent response."""
        text, _ = self._google_extract_text_and_finish(data)
        return text

    def _google_extract_text_and_finish(self, data):
        """Extract Gemini text and finish reason from a successful response."""
        candidates = data.get("candidates") or []
        if candidates:
            candidate = candidates[0] or {}
            finish_reason = str(candidate.get("finishReason") or candidate.get("finish_reason") or "").upper()
            content = candidate.get("content") or {}
            parts = content.get("parts") or []
            if parts:
                first_part = parts[0] or {}
                if "text" in first_part:
                    return first_part.get("text", "").strip(), finish_reason
            return str(candidate), finish_reason
        return str(data), ""

    def _google_continue_answer(self, api_key, model_name, base_payload, partial_answer):
        """Ask Gemini to continue a truncated answer once."""
        continuation_contents = list(base_payload.get("contents") or [])
        continuation_contents.append({"role": "model", "parts": [{"text": partial_answer}]})
        continuation_contents.append({"role": "user", "parts": [{"text": "Continue the answer from exactly where you stopped. Do not repeat earlier text; continue seamlessly and complete the explanation."}]})

        continue_payload = {
            "systemInstruction": base_payload.get("systemInstruction"),
            "contents": continuation_contents,
            "generationConfig": base_payload.get("generationConfig") or {"temperature": 0.2, "maxOutputTokens": 2048},
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            resp = requests.post(url, json=continue_payload, timeout=20)
            if resp.status_code != 200:
                return partial_answer
            answer, _ = self._google_extract_text_and_finish(resp.json())
            if answer and answer != partial_answer:
                return partial_answer.rstrip() + "\n\n" + answer.lstrip()
            return partial_answer
        except Exception:
            return partial_answer

    def _google_candidate_models(self, api_key, preferred_model=None):
        """Resolve a Gemini model name that supports generateContent.

        If a preferred model is provided and valid, use it.
        Otherwise list models and pick the first supported one.
        """
        preferred = (preferred_model or self.model or "").strip()
        if preferred and preferred.lower() not in ("auto", "default"):
            normalized = preferred
            if normalized.startswith("models/"):
                normalized = normalized.split("models/", 1)[1]
            if normalized.lower().startswith("gpt-"):
                normalized = "gemini-1.5-flash"
            return [normalized]

        # Check global cache first to avoid discovery delay
        if api_key in _GOOGLE_DISCOVERY_CACHE:
            return _GOOGLE_DISCOVERY_CACHE[api_key]

        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                return []
            data = resp.json() or {}
            models = data.get("models") or []
            candidates = []
            for model in models:
                name = (model.get("name") or "").replace("models/", "")
                methods = model.get("supportedGenerationMethods") or []
                if "generateContent" in methods and self._google_model_supports_text(model):
                    candidates.append(name)

            if not candidates:
                return []

            # Prefer common Gemini chat models if present, otherwise first supported model.
            preference = [
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
                "gemini-2.5-pro",
                "gemini-2.0-pro",
                "gemini-1.5-pro",
                "gemini-pro",
            ]
            ordered = []
            for pref in preference:
                if pref in candidates:
                    ordered.append(pref)
            for candidate in candidates:
                if candidate not in ordered:
                    ordered.append(candidate)
            
            # Cache the result
            _GOOGLE_DISCOVERY_CACHE[api_key] = ordered
            return ordered
        except Exception:
            return []

    def _google_model_supports_text(self, model_info):
        """Return True if a Google model appears to support text generation.

        Some Gemini variants are audio-only (e.g. TTS preview models). Those must be excluded
        when the app is expecting a textual chat response.
        """
        if not isinstance(model_info, dict):
            return True

        name = (model_info.get("name") or "").lower()
        if "tts" in name or "audio" in name:
            return False

        modalities = model_info.get("responseModalities") or model_info.get("supportedResponseModalities") or []
        if modalities:
            normalized = {str(item).upper() for item in modalities}
            if "TEXT" not in normalized:
                return False

        return True

    def _google_is_model_not_found_error(self, err):
        msg = str(err).lower()
        return "not found" in msg or "not supported" in msg or "requested entity was not found" in msg

    def _dialogflow_reply(self, messages):
        """Call Dialogflow ES detectIntent via REST using a service-account access token.

        Supported secrets / env vars:
          - DIALOGFLOW_PROJECT_ID
          - DIALOGFLOW_SESSION_ID (optional)
          - DIALOGFLOW_ACCESS_TOKEN (optional direct bearer token)
          - GOOGLE_APPLICATION_CREDENTIALS (path to service account JSON)

        If credentials are missing or the call fails, falls back to the mock reply.
        """
        text = messages[-1]["content"] if isinstance(messages, list) and messages else str(messages)
        project_id = os.environ.get("DIALOGFLOW_PROJECT_ID")
        session_id = os.environ.get("DIALOGFLOW_SESSION_ID") or "shapers-session"
        access_token = os.environ.get("DIALOGFLOW_ACCESS_TOKEN")
        credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

        try:
            if not project_id:
                return "[Dialogflow error] DIALOGFLOW_PROJECT_ID is not configured. Falling back to mock reply:\n" + self._mock_reply(text)

            if not access_token and credentials_path:
                try:
                    from google.oauth2 import service_account
                    from google.auth.transport.requests import Request as GoogleAuthRequest

                    creds = service_account.Credentials.from_service_account_file(
                        credentials_path,
                        scopes=["https://www.googleapis.com/auth/cloud-platform"],
                    )
                    creds.refresh(GoogleAuthRequest())
                    access_token = creds.token
                except Exception as e:
                    return f"[Dialogflow error] Failed to load service account credentials: {e} | Falling back to mock reply:\n" + self._mock_reply(text)

            if not access_token:
                return "[Dialogflow error] No access token available. Set DIALOGFLOW_ACCESS_TOKEN or GOOGLE_APPLICATION_CREDENTIALS. Falling back to mock reply:\n" + self._mock_reply(text)

            url = f"https://dialogflow.googleapis.com/v2/projects/{project_id}/agent/sessions/{session_id}:detectIntent"
            payload = {
                "queryInput": {
                    "text": {
                        "text": text,
                        "languageCode": os.environ.get("DIALOGFLOW_LANGUAGE_CODE", "en")
                    }
                }
            }
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            if resp.status_code == 200:
                data = resp.json() or {}
                query_result = data.get("queryResult") or {}
                reply = query_result.get("fulfillmentText") or ""
                if reply:
                    return reply
                messages = query_result.get("responseMessages") or []
                for item in messages:
                    text_msg = item.get("text") or {}
                    texts = text_msg.get("text") or []
                    if texts:
                        return str(texts[0])
                return str(data)

            try:
                err = resp.json()
            except Exception:
                err = resp.text
            return f"[Dialogflow API error] {resp.status_code}: {err} | Falling back to mock reply:\n" + self._mock_reply(text)
        except Exception as e:
            return f"[Dialogflow request error] {e} | Falling back to mock reply:\n" + self._mock_reply(text)

    def health_check(self):
        """Quick provider health check. Returns dict {ok: bool, reason: str}.

        This method is lightweight and intended for diagnostics and tests. It will
        attempt a minimal API call appropriate for the configured provider.
        """
        prov = (self.provider or "").lower()
        try:
            if prov == "google":
                api_key = self.api_key or os.environ.get("GOOGLE_API_KEY")
                if not api_key:
                    return {"ok": False, "reason": "no_api_key"}
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                try:
                    resp = requests.get(url, timeout=6)
                    if resp.status_code == 200:
                        return {"ok": True}
                    return {"ok": False, "reason": f"http_{resp.status_code}", "detail": resp.text}
                except Exception as e:
                    return {"ok": False, "reason": "request_error", "detail": str(e)}

            if prov == "dialogflow":
                project = os.environ.get("DIALOGFLOW_PROJECT_ID")
                token = self.api_key or os.environ.get("DIALOGFLOW_ACCESS_TOKEN")
                if not project:
                    return {"ok": False, "reason": "no_project_id"}
                if not token:
                    return {"ok": False, "reason": "no_access_token"}
                url = f"https://dialogflow.googleapis.com/v2/projects/{project}/agent/sessions/_health:detectIntent"
                headers = {"Authorization": f"Bearer {token}"}
                try:
                    resp = requests.post(url, headers=headers, json={"queryInput": {"text": {"text": "ping", "languageCode": "en"}}}, timeout=6)
                    if resp.status_code == 200:
                        return {"ok": True}
                    return {"ok": False, "reason": f"http_{resp.status_code}", "detail": resp.text}
                except Exception as e:
                    return {"ok": False, "reason": "request_error", "detail": str(e)}

            if prov == "openai":
                if self.api_key or os.environ.get("OPENAI_API_KEY"):
                    return {"ok": True}
                return {"ok": False, "reason": "no_api_key"}

            # Mock or unknown provider
            if prov == "mock" or not prov:
                return {"ok": True, "reason": "mock"}

            return {"ok": False, "reason": "unsupported_provider"}
        except Exception as e:
            return {"ok": False, "reason": "exception", "detail": str(e)}