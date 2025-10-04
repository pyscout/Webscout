import json
import time
import uuid
from typing import List, Dict, Optional, Union, Generator, Any

from webscout.Provider.OPENAI.base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from webscout.Provider.OPENAI.utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage
)

try:
    from curl_cffi.requests import Session
    from curl_cffi import CurlError
except ImportError:
    Session = None
    CurlError = Exception

try:
    from webscout.litagent import LitAgent
except ImportError:
    LitAgent = None

class Completions(BaseCompletions):
    def __init__(self, client: 'GMI'):
        self._client = client

    def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = 4096,
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
        
        # Add additional parameters
        if "top_k" not in payload:
            payload["top_k"] = 1
        if "frequency_penalty" not in payload:
            payload["frequency_penalty"] = 0
        if "presence_penalty" not in payload:
            payload["presence_penalty"] = 0
        
        # Extract system prompt from messages
        system_prompt = "You are a helpful assistant."
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", system_prompt)
                break
        payload["system_prompt"] = system_prompt
        
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
                data=json.dumps(payload),
                stream=True,
                timeout=timeout or self._client.timeout,
                impersonate="chrome110"
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
            print(f"Error during GMI stream request: {e}")
            raise IOError(f"GMI request failed: {e}") from e

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any],
        timeout: Optional[int] = None, proxies: Optional[Dict[str, str]] = None
    ) -> ChatCompletion:
        try:
            payload["stream"] = False
            response = self._client.session.post(
                self._client.base_url,
                headers=self._client.headers,
                data=json.dumps(payload),
                timeout=timeout or self._client.timeout,
                impersonate="chrome110"
            )
            response.raise_for_status()
            
            response_text = response.text
            
            # Try parsing as JSON
            try:
                data = json.loads(response_text)
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage_data = data.get('usage', {})
            except json.JSONDecodeError:
                # If not JSON, treat as plain text
                content = response_text
                usage_data = {}
            
            choices_data = data.get('choices', []) if isinstance(data, dict) else []
            choices = []
            
            if choices_data:
                for choice_d in choices_data:
                    message_d = choice_d.get('message')
                    if not message_d and 'delta' in choice_d:
                        delta = choice_d['delta']
                        message_d = {
                            'role': delta.get('role', 'assistant'),
                            'content': delta.get('content', '')
                        }
                    if not message_d:
                        message_d = {'role': 'assistant', 'content': content}
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
            else:
                # Create a default choice
                message = ChatCompletionMessage(
                    role='assistant',
                    content=content
                )
                choice = Choice(
                    index=0,
                    message=message,
                    finish_reason='stop'
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
                model=data.get('model', model) if isinstance(data, dict) else model,
                usage=usage,
            )
            return completion
        except Exception as e:
            print(f"Error during GMI non-stream request: {e}")
            raise IOError(f"GMI request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'GMI'):
        self.completions = Completions(client)

class GMI(OpenAICompatibleProvider):
    AVAILABLE_MODELS = [
        "Qwen/Qwen3-Next-80B-A3B-Instruct",
        "Qwen/Qwen3-Next-80B-A3B-Thinking",
        "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        "Qwen/Qwen3-30B-A3B",
        "deepseek-ai/DeepSeek-V3.1-Terminus",
        "deepseek-ai/DeepSeek-V3.1",
        "deepseek-ai/DeepSeek-V3.2-Exp",
        "Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8",
        "zai-org/GLM-4.5-Air-FP8",
        "zai-org/GLM-4.5-FP8",
        "zai-org/GLM-4.6"
    ]

    def __init__(self, browser: str = "chrome", api_key: str = None, **kwargs):
        self.timeout = 30
        self.base_url = "https://console.gmicloud.ai/chat"
        
        if Session is None:
            raise ImportError("curl_cffi is required for GMI. Install it with: pip install curl-cffi")
        
        self.session = Session()
        
        # Initialize LitAgent for fingerprinting
        if LitAgent:
            agent = LitAgent()
            fingerprint = agent.generate_fingerprint(browser)
        else:
            fingerprint = {
                "accept": "application/json, text/plain, */*",
                "accept_language": "en-US,en;q=0.9",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "sec_ch_ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
                "platform": "Windows"
            }
        
        self.headers = {
            "Accept": fingerprint.get("accept", "application/json, text/plain, */*"),
            "Accept-Language": fingerprint.get("accept_language", "en-US,en;q=0.9"),
            "User-Agent": fingerprint.get("user_agent", ""),
            "Content-Type": "application/json",
            "Origin": "https://console.gmicloud.ai",
            "sec-ch-ua": fingerprint.get("sec_ch_ua", '"Chromium";v="140", "Not=A?Brand";v="24"'),
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": f'"{fingerprint.get("platform", "Windows")}"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }
        
        if api_key is not None:
            self.headers["Authorization"] = f"Bearer {api_key}"
        
        self.session.headers.update(self.headers)
        self.chat = Chat(self)
    
    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()

if __name__ == "__main__":
    client = GMI()
    response = client.chat.completions.create(
        model="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        messages=[{"role": "user", "content": "Hello, how are you?"}],
        max_tokens=1000,
        stream=False
    )
    print(response.choices[0].message.content)