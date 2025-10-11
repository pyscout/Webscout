import requests
import json
import time
import uuid
import collections
from typing import List, Dict, Optional, Union, Generator, Any

from webscout.Provider.OPENAI.base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from webscout.Provider.OPENAI.utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage
)

try:
    from webscout.litagent import LitAgent
except ImportError:
    pass

class Completions(BaseCompletions):
    def __init__(self, client: 'DeepInfra'):
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
            print(f"Error during DeepInfra stream request: {e}")
            raise IOError(f"DeepInfra request failed: {e}") from e

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
            print(f"Error during DeepInfra non-stream request: {e}")
            raise IOError(f"DeepInfra request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'DeepInfra'):
        self.completions = Completions(client)

class DeepInfra(OpenAICompatibleProvider):
    AVAILABLE_MODELS = [
        "moonshotai/Kimi-K2-Instruct",
        "Qwen/Qwen3-Next-80B-A3B-Instruct",
        "Qwen/Qwen3-Next-80B-A3B-Thinking",
        "moonshotai/Kimi-K2-Instruct-0905",
        "Qwen/Qwen3-Coder-30B-A3B-Instruct",
        "deepseek-ai/DeepSeek-R1-0528-Turbo",
        "Qwen/Qwen3-235B-A22B-Thinking-2507",
        "deepseek-ai/DeepSeek-V3.1-Terminus",
        "deepseek-ai/DeepSeek-V3.2-Exp",
        "Qwen/Qwen3-Coder-480B-A35B-Instruct",
        "Qwen/Qwen3-Coder-480B-A35B-Instruct-Turbo",
        "Qwen/Qwen3-235B-A22B-Instruct-2507",
        "Qwen/Qwen3-235B-A22B",
        "Qwen/Qwen3-30B-A3B",
        "Qwen/Qwen3-32B",
        "Qwen/Qwen3-14B",
        "deepseek-ai/DeepSeek-V3-0324-Turbo",
        "deepseek-ai/DeepSeek-Prover-V2-671B",
        "meta-llama/Llama-4-Maverick-17B-128E-Instruct-Turbo",
        "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
        "meta-llama/Llama-4-Scout-17B-16E-Instruct",
        "deepseek-ai/DeepSeek-R1-0528",
        "deepseek-ai/DeepSeek-V3-0324",
        "mistralai/Mistral-Small-3.1-24B-Instruct-2503",
        "microsoft/phi-4-reasoning-plus",
        "Qwen/QwQ-32B",
        "google/gemma-3-27b-it",
        "google/gemma-3-12b-it",
        "google/gemma-3-4b-it",
        "microsoft/Phi-4-multimodal-instruct",
        "deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
        "deepseek-ai/DeepSeek-V3",
        "deepseek-ai/DeepSeek-V3.1",
        "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "meta-llama/Llama-3.3-70B-Instruct",
        "microsoft/phi-4",
        "Gryphe/MythoMax-L2-13b",
        "NousResearch/Hermes-3-Llama-3.1-405B",
        "NousResearch/Hermes-3-Llama-3.1-70B",
        "NovaSky-AI/Sky-T1-32B-Preview",
        "Qwen/Qwen2.5-72B-Instruct",
        "Qwen/Qwen2.5-7B-Instruct",
        "Qwen/Qwen2.5-Coder-32B-Instruct",
        "Sao10K/L3-8B-Lunaris-v1-Turbo",
        "Sao10K/L3.1-70B-Euryale-v2.2",
        "Sao10K/L3.3-70B-Euryale-v2.3",
        "deepseek-ai/DeepSeek-R1",
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        "deepseek-ai/DeepSeek-R1-Turbo",
        "google/gemini-2.0-flash-001",
        "meta-llama/Llama-3.2-11B-Vision-Instruct",
        "meta-llama/Llama-3.2-1B-Instruct",
        "meta-llama/Llama-3.2-3B-Instruct",
        "meta-llama/Llama-3.2-90B-Vision-Instruct",
        "meta-llama/Meta-Llama-3-70B-Instruct",
        "meta-llama/Meta-Llama-3-8B-Instruct",
        "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "meta-llama/Meta-Llama-3.1-8B-Instruct",
        "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "microsoft/WizardLM-2-8x22B",
        "mistralai/Devstral-Small-2505",
        "mistralai/Devstral-Small-2507",
        "mistralai/Mistral-7B-Instruct-v0.3",
        "mistralai/Mistral-Nemo-Instruct-2407",
        "mistralai/Mistral-Small-24B-Instruct-2501",
        "mistralai/Mistral-Small-3.2-24B-Instruct-2506",
        "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "nvidia/Llama-3.1-Nemotron-70B-Instruct",
        "zai-org/GLM-4.5-Air",
        "zai-org/GLM-4.5",
        "zai-org/GLM-4.5V",
        "zai-org/GLM-4.6",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "allenai/olmOCR-7B-0725-FP8",
    ]

    def __init__(self, browser: str = "chrome", api_key: str = None):
        self.timeout = None
        self.base_url = "https://api.deepinfra.com/v1/openai/chat/completions"
        self.session = requests.Session()
        agent = LitAgent()
        fingerprint = agent.generate_fingerprint(browser)
        self.headers = {
            "Accept": fingerprint["accept"],
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": fingerprint["accept_language"],
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Origin": "https://deepinfra.com",
            "Pragma": "no-cache",
            "Referer": "https://deepinfra.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "X-Deepinfra-Source": "web-embed",
            "Sec-CH-UA": fingerprint["sec_ch_ua"] or '"Not)A;Brand";v="99", "Microsoft Edge";v="127", "Chromium";v="127"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": f'"{fingerprint["platform"]}"',
            "User-Agent": fingerprint["user_agent"],
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
    client = DeepInfra()
    response = client.chat.completions.create(
        model="deepseek-ai/DeepSeek-R1-0528",
        messages=[{"role": "user", "content": "Hello, how are you?"}],
        max_tokens=10000,
        stream=False
    )
    print(response.choices[0].message.content)