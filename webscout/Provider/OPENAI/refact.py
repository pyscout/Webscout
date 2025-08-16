from regex import R
import requests
import json
import time
import uuid
from typing import List, Dict, Optional, Union, Generator, Any

from webscout.Provider.Deepinfra import DeepInfra
from webscout.Provider.OPENAI.base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from webscout.Provider.OPENAI.utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage
)
try:
    from .generate_api_key import generate_full_api_key
except ImportError:
    # Fallback: define the function inline if import fails
    import random
    import string
    
    def generate_api_key_suffix(length: int = 4) -> str:
        """Generate a random API key suffix like 'C1Z5'"""
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    def generate_full_api_key(prefix: str = "EU1CW20nX5oau42xBSgm") -> str:
        """Generate a full API key with a random suffix"""
        suffix = generate_api_key_suffix(4)
        return prefix + suffix

try:
    from webscout.litagent import LitAgent
except ImportError:
    pass

class Completions(BaseCompletions):
    def __init__(self, client: 'Refact'):
        self._client = client

    def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = 2049,
        stream: bool = False,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        timeout: Optional[int] = None,
        proxies: Optional[Dict[str, str]] = None,
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
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
            return self._create_stream(request_id, created_time, model, payload, timeout, proxies)
        else:
            return self._create_non_stream(request_id, created_time, model, payload, timeout, proxies)

    def _create_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any],
        timeout: Optional[int] = None, proxies: Optional[Dict[str, str]] = None
    ) -> Generator[ChatCompletionChunk, None, None]:
        try:
            response = self._client.session.post(
                self._client.base_url,
                headers=self._client.headers,
                json=payload,
                stream=True,
                timeout=timeout or self._client.timeout,
                proxies=proxies
            )
            response.raise_for_status()
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    if line.startswith("data: "):
                        json_str = line[6:]
                        if json_str == "[DONE]":
                            break
                        try:
                            data = json.loads(json_str)
                            choice_data = data.get('choices', [{}])[0]
                            delta_data = choice_data.get('delta', {})
                            finish_reason = choice_data.get('finish_reason')
                            usage_data = data.get('usage', {})
                            if usage_data:
                                prompt_tokens = usage_data.get('prompt_tokens', prompt_tokens)
                                completion_tokens = usage_data.get('completion_tokens', completion_tokens)
                                total_tokens = usage_data.get('total_tokens', total_tokens)
                            if delta_data.get('content'):
                                completion_tokens += 1
                                total_tokens = prompt_tokens + completion_tokens
                            delta = ChoiceDelta(
                                content=delta_data.get('content'),
                                role=delta_data.get('role'),
                                tool_calls=delta_data.get('tool_calls')
                            )
                            choice = Choice(
                                index=choice_data.get('index', 0),
                                delta=delta,
                                finish_reason=finish_reason,
                                logprobs=choice_data.get('logprobs')
                            )
                            chunk = ChatCompletionChunk(
                                id=request_id,
                                choices=[choice],
                                created=created_time,
                                model=model,
                                system_fingerprint=data.get('system_fingerprint')
                            )
                            chunk.usage = {
                                "prompt_tokens": prompt_tokens,
                                "completion_tokens": completion_tokens,
                                "total_tokens": total_tokens,
                                "estimated_cost": None
                            }
                            yield chunk
                        except json.JSONDecodeError:
                            continue
            # Final chunk with finish_reason="stop"
            delta = ChoiceDelta(content=None, role=None, tool_calls=None)
            choice = Choice(index=0, delta=delta, finish_reason="stop", logprobs=None)
            chunk = ChatCompletionChunk(
                id=request_id,
                choices=[choice],
                created=created_time,
                model=model,
                system_fingerprint=None
            )
            chunk.usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "estimated_cost": None
            }
            yield chunk
        except Exception as e:
            print(f"Error during Refact stream request: {e}")
            raise IOError(f"Refact request failed: {e}") from e

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any],
        timeout: Optional[int] = None, proxies: Optional[Dict[str, str]] = None
    ) -> ChatCompletion:
        try:
            response = self._client.session.post(
                self._client.base_url,
                headers=self._client.headers,
                json=payload,
                timeout=timeout or self._client.timeout,
                proxies=proxies
            )
            response.raise_for_status()
            data = response.json()
            choices_data = data.get('choices', [])
            usage_data = data.get('usage', {})
            choices = []
            for choice_d in choices_data:
                message_d = choice_d.get('message')
                if not message_d and 'delta' in choice_d:
                    delta = choice_d['delta']
                    message_d = {
                        'role': delta.get('role', 'assistant'),
                        'content': delta.get('content', '')
                    }
                if not message_d:
                    message_d = {'role': 'assistant', 'content': ''}
                message = ChatCompletionMessage(
                    role=message_d.get('role', 'assistant'),
                    content=message_d.get('content', '')
                )
                choice = Choice(
                    index=choice_d.get('index', 0),
                    message=message,
                    finish_reason=choice_d.get('finish_reason', 'stop')
                )
                choices.append(choice)
            usage = CompletionUsage(
                prompt_tokens=usage_data.get('prompt_tokens', 0),
                completion_tokens=usage_data.get('completion_tokens', 0),
                total_tokens=usage_data.get('total_tokens', 0)
            )
            completion = ChatCompletion(
                id=request_id,
                choices=choices,
                created=created_time,
                model=data.get('model', model),
                usage=usage,
            )
            return completion
        except Exception as e:
            print(f"Error during Refact non-stream request: {e}")
            raise IOError(f"Refact request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'Refact'):
        self.completions = Completions(client)

class Refact(OpenAICompatibleProvider):
    AVAILABLE_MODELS = [
        "gpt-4o",
        "gpt-4o-mini",
        "o4-mini",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        "claude-sonnet-4",
        "claude-opus-4",
        "claude-opus-4.1",
        "gemini-2.5-pro",
        "gemini-2.5-pro-preview"
    ]
    
    def __init__(self, api_key: str = None, browser: str = "chrome"):
        # Mirror DeepInfra constructor signature but use the lightweight headers from lol.py
        self.timeout = None
        self.base_url = "https://inference.smallcloud.ai/v1/chat/completions"
        self.session = requests.Session()

        # Use minimal headers consistent with lol.py
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "refact-lsp 0.10.19",
        }

        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
        else:
            self.headers["Authorization"] = f"Bearer {generate_full_api_key()}"

        # Try to initialize LitAgent for compatibility, but do not alter headers (keep lol.py style)
        try:
            _ = LitAgent()
        except Exception:
            pass

        self.session.headers.update(self.headers)
        self.chat = Chat(self)
    
    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()

if __name__ == "__main__":
    client = Refact()
    response = client.chat.completions.create(
        model="claude-opus-4.1",
        messages=[{"role": "user", "content": "Hello, how are you?"}],
        max_tokens=10000,
        stream=True
    )
    for chunk in response:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end='', flush=True)