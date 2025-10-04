import requests
import json
import time
import uuid
import urllib.parse
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
    def __init__(self, client: 'ChatGLM'):
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
        # Resolve model nickname to API format
        resolved_model = self._client._resolve_model(model)
        
        payload = {
            "stream": True,
            "model": resolved_model,
            "messages": messages,
            "params": {},
            "features": {
                "image_generation": False,
                "web_search": False,
                "auto_web_search": False,
                "preview_mode": True,
                "flags": [],
                "features": [
                    {"type": "mcp", "server": "vibe-coding", "status": "hidden"},
                    {"type": "mcp", "server": "ppt-maker", "status": "hidden"},
                    {"type": "mcp", "server": "image-search", "status": "hidden"},
                    {"type": "mcp", "server": "deep-research", "status": "hidden"},
                    {"type": "tool_selector", "server": "tool_selector", "status": "hidden"},
                    {"type": "mcp", "server": "advanced-search", "status": "hidden"}
                ],
                "enable_thinking": True
            },
            "actions": [],
            "tags": [],
            "chat_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4())
        }
        
        if temperature is not None:
            payload["params"]["temperature"] = temperature
        if top_p is not None:
            payload["params"]["top_p"] = top_p
        if max_tokens is not None:
            payload["params"]["max_tokens"] = max_tokens
        
        payload.update(kwargs)
        
        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())
        
        if stream:
            return self._create_stream(request_id, created_time, resolved_model, payload, timeout, proxies)
        else:
            return self._create_non_stream(request_id, created_time, resolved_model, payload, timeout, proxies)

    def _create_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any],
        timeout: Optional[int] = None, proxies: Optional[Dict[str, str]] = None
    ) -> Generator[ChatCompletionChunk, None, None]:
        try:
            api_key = self._client._get_api_key()
            api_url = self._client._build_api_url(payload["chat_id"])
            
            response = requests.post(
                api_url,
                headers={
                    **self._client.headers,
                    "Authorization": f"Bearer {api_key}",
                    "x-fe-version": "prod-fe-1.0.95",
                },
                json=payload,
                stream=True,
                timeout=timeout or self._client.timeout,
                proxies=proxies
            )
            response.raise_for_status()
            
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            full_content = ""
            thinking_content = ""
            in_thinking_phase = False
            
            for line in response.iter_lines(decode_unicode=True):
                if line and line.startswith("data: "):
                    json_str = line[6:]
                    if json_str == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(json_str)
                        
                        if data.get("type") != "chat:completion":
                            continue
                        
                        chunk_data = data.get("data", {})
                        phase = chunk_data.get("phase")
                        delta_content = chunk_data.get("delta_content", "")
                        usage_data = chunk_data.get("usage", {})
                        
                        if usage_data:
                            prompt_tokens = usage_data.get("prompt_tokens", prompt_tokens)
                            completion_tokens = usage_data.get("completion_tokens", completion_tokens)
                            total_tokens = usage_data.get("total_tokens", total_tokens)
                        
                        content_to_yield = None
                        finish_reason = None
                        
                        if phase == "thinking":
                            # Handle thinking phase - strip HTML tags if present
                            if delta_content:
                                if "</summary>\n>" in delta_content:
                                    delta_content = delta_content.split("</summary>\n>")[-1]
                                thinking_content += delta_content
                                # Optionally yield thinking content with a marker
                                # For OpenAI compatibility, we'll include it in the content
                                if not in_thinking_phase:
                                    content_to_yield = "<think>\n" + delta_content
                                    in_thinking_phase = True
                                else:
                                    content_to_yield = delta_content
                        
                        elif phase == "answer":
                            # Handle answer phase
                            if in_thinking_phase and delta_content:
                                # Close thinking and start answer
                                content_to_yield = "\n</think>\n\n" + delta_content
                                in_thinking_phase = False
                            elif delta_content:
                                content_to_yield = delta_content
                            
                            full_content += delta_content
                            completion_tokens += 1
                            total_tokens = prompt_tokens + completion_tokens
                        
                        elif phase == "done":
                            if in_thinking_phase:
                                content_to_yield = "\n</think>\n\n"
                                in_thinking_phase = False
                            finish_reason = "stop"
                        
                        if content_to_yield is not None or finish_reason:
                            delta = ChoiceDelta(
                                content=content_to_yield,
                                role="assistant" if content_to_yield else None,
                                tool_calls=None
                            )
                            choice = Choice(
                                index=0,
                                delta=delta,
                                finish_reason=finish_reason,
                                logprobs=None
                            )
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
                    
                    except json.JSONDecodeError:
                        continue
            
            # Final chunk with finish_reason="stop"
            if in_thinking_phase:
                # Close thinking if still open
                delta = ChoiceDelta(content="\n</think>\n\n", role=None, tool_calls=None)
                choice = Choice(index=0, delta=delta, finish_reason=None, logprobs=None)
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
            print(f"Error during ChatGLM stream request: {e}")
            raise IOError(f"ChatGLM request failed: {e}") from e

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any],
        timeout: Optional[int] = None, proxies: Optional[Dict[str, str]] = None
    ) -> ChatCompletion:
        try:
            # For non-stream, collect all chunks
            full_content = ""
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            
            for chunk in self._create_stream(request_id, created_time, model, payload, timeout, proxies):
                if chunk.choices and chunk.choices[0].delta.content:
                    full_content += chunk.choices[0].delta.content
                if hasattr(chunk, 'usage') and chunk.usage:
                    prompt_tokens = chunk.usage.get("prompt_tokens", prompt_tokens)
                    completion_tokens = chunk.usage.get("completion_tokens", completion_tokens)
                    total_tokens = chunk.usage.get("total_tokens", total_tokens)
            
            message = ChatCompletionMessage(
                role="assistant",
                content=full_content
            )
            choice = Choice(
                index=0,
                message=message,
                finish_reason="stop"
            )
            usage = CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )
            completion = ChatCompletion(
                id=request_id,
                choices=[choice],
                created=created_time,
                model=model,
                usage=usage,
            )
            return completion
        
        except Exception as e:
            print(f"Error during ChatGLM non-stream request: {e}")
            raise IOError(f"ChatGLM request failed: {e}") from e


class Chat(BaseChat):
    def __init__(self, client: 'ChatGLM'):
        self.completions = Completions(client)


class ChatGLM(OpenAICompatibleProvider):
    """
    OpenAI-compatible provider for Z.AI Chat API (ChatGLM models).
    Supports GLM-4.5, GLM-4.6, and related models with thinking/reasoning capabilities.
    """
    
    AVAILABLE_MODELS = [
        "glm-4.6",           # GLM-4-6-API-V1 (latest, most advanced)
        "glm-4.5",           # 0727-360B-API
        "glm-4.5-Air",       # 0727-106B-API (lighter version)
        "glm-4.5V",          # glm-4.5v (vision-capable)
        "glm-4-32B",         # main_chat (32B parameter model)
        # API format names
        "GLM-4-6-API-V1",
        "0727-360B-API",
        "0727-106B-API",
        "glm-4.5v",
        "main_chat",
    ]
    
    # Model nickname mapping system
    MODEL_MAPPING = {
        "glm-4.6": "GLM-4-6-API-V1",
        "glm-4.5": "0727-360B-API",
        "glm-4.5-Air": "0727-106B-API",
        "glm-4.5V": "glm-4.5v",
        "glm-4-32B": "main_chat",
    }
    
    # Reverse mapping: API format to nickname
    GLM_TO_MODEL = {v: k for k, v in MODEL_MAPPING.items()}

    def __init__(self, browser: str = "chrome"):
        """
        Initialize ChatGLM OpenAI-compatible provider.
        
        Args:
            browser: Browser type for fingerprinting (chrome, firefox, safari, edge)
        """
        self.timeout = 30
        self.base_url = "https://chat.z.ai"
        self.api_endpoint = f"{self.base_url}/api/chat/completions"
        self.session = requests.Session()
        
        # Generate browser fingerprint
        try:
            agent = LitAgent()
            fingerprint = agent.generate_fingerprint(browser)
        except:
            # Fallback if LitAgent is not available
            fingerprint = {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "accept": "text/event-stream",
                "accept_language": "en-US,en;q=0.9",
                "platform": "Windows",
                "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
            }
        
        self.headers = {
            "Accept": "text/event-stream",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": fingerprint.get("accept_language", "en-US,en;q=0.9"),
            "Content-Type": "application/json",
            "App-Name": "chatglm",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Origin": self.base_url,
            "Pragma": "no-cache",
            "Referer": f"{self.base_url}/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-CH-UA": fingerprint.get("sec_ch_ua", '"Not_A Brand";v="8", "Chromium";v="120"'),
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": f'"{fingerprint.get("platform", "Windows")}"',
            "User-Agent": fingerprint.get("user_agent", "Mozilla/5.0"),
            "X-App-Platform": "pc",
            "X-App-Version": "0.0.1",
            "DNT": "1",
            "Sec-GPC": "1",
        }
        
        self.session.headers.update(self.headers)
        self.chat = Chat(self)
        
        # Cache for API credentials
        self.api_key = None
        self.user_id = None
        self.cookie = None

    def _resolve_model(self, model: str) -> str:
        """
        Resolve a model nickname or API name to the API format.
        
        Args:
            model: Model name or nickname
            
        Returns:
            API format model name
        """
        if model in self.GLM_TO_MODEL:
            return model
        if model in self.MODEL_MAPPING:
            return self.MODEL_MAPPING[model]
        # Fallback to direct API name if present
        if model in self.AVAILABLE_MODELS:
            return model
        raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

    def _get_api_key(self):
        """Get authentication token from Z.AI API"""
        if not self.api_key:
            try:
                response = self.session.get(f"{self.base_url}/api/v1/auths/")
                response.raise_for_status()
                self.api_key = response.json().get("token")
            except Exception as e:
                print(f"Error getting API key: {e}")
                # Generate a dummy token if auth fails
                self.api_key = str(uuid.uuid4())
        return self.api_key

    def _get_user_id(self):
        """Get user_id from the auth response"""
        if not self.user_id:
            try:
                response = self.session.get(f"{self.base_url}/api/v1/auths/")
                response.raise_for_status()
                data = response.json()
                self.user_id = data.get("id", str(uuid.uuid4()))
            except Exception as e:
                print(f"Error getting user ID: {e}")
                self.user_id = str(uuid.uuid4())
        return self.user_id

    def _get_cookie(self):
        """Get authentication cookie from the site"""
        if not self.cookie:
            try:
                response = self.session.get(f"{self.base_url}/")
                self.cookie = response.headers.get('Set-Cookie', '')
            except:
                self.cookie = ''
        return self.cookie

    def _build_api_url(self, chat_id: str = "local"):
        """Build the API URL with all required query parameters"""
        api_key = self._get_api_key()
        user_id = self._get_user_id()
        timestamp = str(int(time.time() * 1000))
        request_id = str(uuid.uuid4())
        user_agent = self.session.headers.get('User-Agent', 'Mozilla/5.0')
        
        params = {
            'timestamp': timestamp,
            'requestId': request_id,
            'user_id': user_id,
            'version': '0.0.1',
            'platform': 'web',
            'token': api_key,
            'user_agent': user_agent,
            'language': 'en-US',
            'languages': 'en-US,en',
            'timezone': 'UTC',
            'cookie_enabled': 'true',
            'screen_width': '1920',
            'screen_height': '1080',
            'screen_resolution': '1920x1080',
            'viewport_height': '1080',
            'viewport_width': '1920',
            'viewport_size': '1920x1080',
            'color_depth': '24',
            'pixel_ratio': '1',
            'current_url': f'https://chat.z.ai/c/{chat_id}',
            'pathname': f'/c/{chat_id}',
            'search': '',
            'hash': '',
            'host': 'chat.z.ai',
            'hostname': 'chat.z.ai',
            'protocol': 'https:',
            'referrer': '',
            'title': 'Z.ai Chat - Free AI powered by GLM-4.6',
            'timezone_offset': '0',
            'is_mobile': 'false',
            'is_touch': 'false',
            'max_touch_points': '0',
            'browser_name': 'Chrome',
            'os_name': 'Windows',
            'signature_timestamp': timestamp
        }
        
        query_string = urllib.parse.urlencode(params)
        return f"{self.api_endpoint}?{query_string}"

    @property
    def models(self):
        """Return available models"""
        class _ModelList:
            def list(inner_self):
                return ChatGLM.AVAILABLE_MODELS
        return _ModelList()


if __name__ == "__main__":
    # Example usage
    client = ChatGLM()
    
    print("Available models:", client.models.list())
    print("\nTesting GLM-4.6 (streaming)...")
    
    response = client.chat.completions.create(
        model="glm-4.6",
        messages=[{"role": "user", "content": "Explain quantum computing in simple terms."}],
        max_tokens=500,
        stream=True
    )
    
    print("\nStreaming response:")
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    
    print("\n\n" + "="*50)
    print("Testing GLM-4.5-Air (non-streaming)...")
    
    response = client.chat.completions.create(
        model="glm-4.5-Air",
        messages=[{"role": "user", "content": "What is the capital of France?"}],
        max_tokens=100,
        stream=False
    )
    
    print("\nNon-streaming response:")
    print(response.choices[0].message.content)
    print(f"\nUsage: {response.usage}")
