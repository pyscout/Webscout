from curl_cffi.requests import Session
from curl_cffi import CurlError
import json
import time
import uuid
import re
import urllib.parse
import os
import pickle
import tempfile
from typing import List, Dict, Optional, Union, Generator, Any

from webscout.Extra.tempmail import get_random_email
from webscout.litagent import LitAgent

# Import base classes and utilities from OPENAI provider stack
from webscout.Provider.OPENAI.base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from webscout.Provider.OPENAI.utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage
)

# Attempt to import LitAgent for browser fingerprinting
try:
    from webscout.litagent import LitAgent
except ImportError:  # pragma: no cover - LitAgent optional
    LitAgent = None


class Completions(BaseCompletions):
    """TwoAI chat completions compatible with OpenAI format."""

    def __init__(self, client: 'TwoAI'):
        self._client = client

    def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        max_tokens: Optional[int] = 2049,
        stream: bool = False,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        timeout: Optional[int] = None,
        proxies: Optional[Dict[str, str]] = None,
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """Create a chat completion using TwoAI."""
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p

        payload.update(kwargs)

        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())

        if stream:
            return self._create_stream(request_id, created_time, model, payload, timeout=timeout, proxies=proxies)
        return self._create_non_stream(request_id, created_time, model, payload, timeout=timeout, proxies=proxies)

    def _create_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any],
        timeout: Optional[int] = None, proxies: Optional[Dict[str, str]] = None
    ) -> Generator[ChatCompletionChunk, None, None]:
        original_proxies = self._client.session.proxies.copy()
        if proxies is not None:
            self._client.session.proxies = proxies
        else:
            self._client.session.proxies = {}
        try:
            response = self._client.session.post(
                self._client.base_url,
                headers=self._client.headers,
                json=payload,
                stream=True,
                timeout=timeout if timeout is not None else self._client.timeout,
                proxies=proxies or getattr(self._client, "proxies", None)
            )
            response.raise_for_status()

            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0

            for line in response.iter_lines():
                if not line:
                    continue
                decoded = line.decode("utf-8").strip()
                if not decoded.startswith("data: "):
                    continue
                json_str = decoded[6:]
                if json_str == "[DONE]":
                    break
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    continue

                choice_data = data.get("choices", [{}])[0]
                delta_data = choice_data.get("delta", {})
                finish_reason = choice_data.get("finish_reason")

                usage_data = data.get("usage", {})
                if usage_data:
                    prompt_tokens = usage_data.get("prompt_tokens", prompt_tokens)
                    completion_tokens = usage_data.get(
                        "completion_tokens", completion_tokens
                    )
                    total_tokens = usage_data.get("total_tokens", total_tokens)

                delta = ChoiceDelta(
                    content=delta_data.get("content"),
                    role=delta_data.get("role"),
                    tool_calls=delta_data.get("tool_calls"),
                )

                choice = Choice(
                    index=choice_data.get("index", 0),
                    delta=delta,
                    finish_reason=finish_reason,
                    logprobs=choice_data.get("logprobs"),
                )

                chunk = ChatCompletionChunk(
                    id=request_id,
                    choices=[choice],
                    created=created_time,
                    model=model,
                    system_fingerprint=data.get("system_fingerprint"),
                )

                yield chunk
        except Exception as e:
            raise IOError(f"TwoAI request failed: {e}") from e
        finally:
            self._client.session.proxies = original_proxies

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any],
        timeout: Optional[int] = None, proxies: Optional[Dict[str, str]] = None
    ) -> ChatCompletion:
        original_proxies = self._client.session.proxies.copy()
        if proxies is not None:
            self._client.session.proxies = proxies
        else:
            self._client.session.proxies = {}
        try:
            response = self._client.session.post(
                self._client.base_url,
                headers=self._client.headers,
                json=payload,
                timeout=timeout if timeout is not None else self._client.timeout,
                proxies=proxies or getattr(self._client, "proxies", None)
            )
            response.raise_for_status()
            data = response.json()

            choices_data = data.get("choices", [])
            usage_data = data.get("usage", {})

            choices = []
            for choice_d in choices_data:
                message_d = choice_d.get("message", {})
                message = ChatCompletionMessage(
                    role=message_d.get("role", "assistant"),
                    content=message_d.get("content", ""),
                    tool_calls=message_d.get("tool_calls"),
                )
                choice = Choice(
                    index=choice_d.get("index", 0),
                    message=message,
                    finish_reason=choice_d.get("finish_reason", "stop"),
                )
                choices.append(choice)

            usage = CompletionUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )

            completion = ChatCompletion(
                id=request_id,
                choices=choices,
                created=created_time,
                model=data.get("model", model),
                usage=usage,
            )
            return completion
        except Exception as e:
            raise IOError(f"TwoAI request failed: {e}") from e
        finally:
            self._client.session.proxies = original_proxies


class Chat(BaseChat):
    def __init__(self, client: 'TwoAI'):
        self.completions = Completions(client)


class TwoAI(OpenAICompatibleProvider):
    """OpenAI-compatible client for the TwoAI API."""

    AVAILABLE_MODELS = ["sutra-v2", "sutra-r0"]
    
    # Class-level cache for API keys
    _api_key_cache = None
    _cache_file = os.path.join(tempfile.gettempdir(), "webscout_twoai_openai_cache.pkl")

    @classmethod
    def _load_cached_api_key(cls) -> Optional[str]:
        """Load cached API key from file."""
        try:
            if os.path.exists(cls._cache_file):
                with open(cls._cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                    # Check if cache is not too old (24 hours)
                    if time.time() - cache_data.get('timestamp', 0) < 86400:
                        return cache_data.get('api_key')
        except Exception:
            # If cache is corrupted or unreadable, ignore and regenerate
            pass
        return None

    @classmethod
    def _save_cached_api_key(cls, api_key: str):
        """Save API key to cache file."""
        try:
            cache_data = {
                'api_key': api_key,
                'timestamp': time.time()
            }
            with open(cls._cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
        except Exception:
            # If caching fails, continue without caching
            pass

    @classmethod
    def _validate_api_key(cls, api_key: str) -> bool:
        """Validate if an API key is still working."""
        try:
            session = Session()
            headers = {
                'User-Agent': LitAgent().random(),
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}',
            }
            
            # Test with a simple request
            test_payload = {
                "messages": [{"role": "user", "content": "test"}],
                "model": "sutra-v2",
                "max_tokens": 1,
                "stream": False
            }
            
            response = session.post(
                "https://api.two.ai/v2/chat/completions",
                headers=headers,
                json=test_payload,
                timeout=10,
                impersonate="chrome120"
            )
            
            # If we get a 200 or 400 (bad request but auth worked), key is valid
            # If we get 401/403, key is invalid
            return response.status_code not in [401, 403]
        except Exception:
            # If validation fails, assume key is invalid
            return False

    @classmethod
    def get_cached_api_key(cls) -> str:
        """Get a cached API key or generate a new one if needed."""
        # First check class-level cache
        if cls._api_key_cache:
            if cls._validate_api_key(cls._api_key_cache):
                return cls._api_key_cache
            else:
                cls._api_key_cache = None

        # Then check file cache
        cached_key = cls._load_cached_api_key()
        if cached_key and cls._validate_api_key(cached_key):
            cls._api_key_cache = cached_key
            return cached_key

        # Generate new key if no valid cached key
        new_key = cls.generate_api_key()
        cls._api_key_cache = new_key
        cls._save_cached_api_key(new_key)
        return new_key

    @staticmethod
    def generate_api_key() -> str:
        """
        Generate a new Two AI API key using a temporary email.
        """
        email, provider = get_random_email("tempmailio")
        loops_url = "https://app.loops.so/api/newsletter-form/cm7i4o92h057auy1o74cxbhxo"

        session = Session()
        session.headers.update({
            'User-Agent': LitAgent().random(),
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://www.two.ai',
            'Referer': 'https://app.loops.so/',
        })

        form_data = {
            'email': email,
            'userGroup': 'Via Framer',
            'mailingLists': 'cm8ay9cic00x70kjv0bd34k66'
        }

        encoded_data = urllib.parse.urlencode(form_data)
        response = session.post(loops_url, data=encoded_data, impersonate="chrome120")

        if response.status_code != 200:
            raise RuntimeError(f"Failed to register for Two AI: {response.status_code} - {response.text}")

        max_attempts = 15
        attempt = 0
        api_key = None
        wait_time = 2

        while attempt < max_attempts and not api_key:
            messages = provider.get_messages()
            for message in messages:
                subject = message.get('subject', '')
                sender = ''
                if 'from' in message:
                    if isinstance(message['from'], dict):
                        sender = message['from'].get('address', '')
                    else:
                        sender = str(message['from'])
                elif 'sender' in message:
                    if isinstance(message['sender'], dict):
                        sender = message['sender'].get('address', '')
                    else:
                        sender = str(message['sender'])
                subject_match = any(keyword in subject.lower() for keyword in
                                    ['welcome', 'confirm', 'verify', 'api', 'key', 'sutra', 'two.ai', 'loops'])
                sender_match = any(keyword in sender.lower() for keyword in
                                   ['two.ai', 'sutra', 'loops.so', 'loops', 'no-reply', 'noreply'])
                is_confirmation = subject_match or sender_match

                content = None
                if 'body' in message:
                    content = message['body']
                elif 'content' in message and 'text' in message['content']:
                    content = message['content']['text']
                elif 'html' in message:
                    content = message['html']
                elif 'text' in message:
                    content = message['text']
                if not content:
                    continue

                # Robust API key extraction with multiple regex patterns
                patterns = [
                    r'sutra_[A-Za-z0-9]{60,70}',
                    r'sutra_[A-Za-z0-9]{30,}',
                    r'sutra_\S+',
                ]
                api_key_match = None
                for pat in patterns:
                    api_key_match = re.search(pat, content)
                    if api_key_match:
                        break
                # Also try to extract from labeled section
                if not api_key_match:
                    key_section_match = re.search(r'🔑 SUTRA API Key\s*([^\s]+)', content)
                    if key_section_match:
                        api_key_match = re.search(r'sutra_[A-Za-z0-9]+', key_section_match.group(1))
                if api_key_match:
                    api_key = api_key_match.group(0)
                    break
            if not api_key:
                attempt += 1
                time.sleep(wait_time)
        if not api_key:
            raise RuntimeError("Failed to get API key from confirmation email")
        return api_key

    def __init__(self, browser: str = "chrome", proxies: Optional[Dict[str, str]] = None):
        super().__init__(proxies=proxies)
        api_key = self.get_cached_api_key()
        self.timeout = 30
        self.base_url = "https://api.two.ai/v2/chat/completions"
        self.api_key = api_key

        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        if LitAgent is not None:
            try:
                agent = LitAgent()
                fingerprint = agent.generate_fingerprint(browser)
                headers.update({
                    "Accept": fingerprint["accept"],
                    "Accept-Encoding": "gzip, deflate, br, zstd",
                    "Accept-Language": fingerprint["accept_language"],
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Origin": "https://chat.two.ai",
                    "Pragma": "no-cache",
                    "Referer": "https://chat.two.ai/",
                    "Sec-Fetch-Dest": "empty",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Site": "same-site",
                    "Sec-CH-UA": fingerprint["sec_ch_ua"] or '"Not)A;Brand";v="99", "Microsoft Edge";v="127", "Chromium";v="127"',
                    "Sec-CH-UA-Mobile": "?0",
                    "Sec-CH-UA-Platform": f'"{fingerprint["platform"]}"',
                    "User-Agent": fingerprint["user_agent"],
                })
            except Exception:
                # Fallback minimal headers if fingerprinting fails
                headers.update({
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept-Language": "en-US,en;q=0.9",
                    "User-Agent": "Mozilla/5.0",
                })
        else:
            headers.update({
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-US,en;q=0.9",
                "User-Agent": "Mozilla/5.0",
            })

        self.headers = headers
        self.session.headers.update(headers)
        self.chat = Chat(self)

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()

if __name__ == "__main__":
    from rich import print
    two_ai = TwoAI()
    resp = two_ai.chat.completions.create(
        model="sutra-v2",
        messages=[{"role": "user", "content": "Hello, how are you?"}],
        stream=True
    )
    for chunk in resp:
        print(chunk, end="")