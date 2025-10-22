#!/usr/bin/env python3
from typing import List, Dict, Optional, Union, Generator, Any
import time
import json

# Import base classes and utility structures
from webscout.Provider.OPENAI.base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from webscout.Provider.OPENAI.utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage
)

# Import requests for HTTP requests (instead of curl_cffi)
import requests
import zstandard as zstd
import uuid

# Attempt to import LitAgent, fallback if not available
try:
    from webscout.litagent import LitAgent
except ImportError:
    class LitAgent:
        def generate_fingerprint(self, browser):
            return {"user_agent": "Mozilla/5.0"}

# --- Flowith OpenAI-Compatible Client ---

class Completions(BaseCompletions):
    def __init__(self, client: 'Flowith'):
        self.client = client

    def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = 2048,
        stream: bool = False,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        timeout: Optional[int] = None,
        proxies: Optional[Dict[str, str]] = None,
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Implements OpenAI-compatible chat/completions endpoint for Flowith.
        """
        url = "https://edge.flowith.net/ai/chat?mode=general"
        agent = LitAgent()
        fingerprint = agent.generate_fingerprint("chrome")
        headers = {
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9,en-IN;q=0.8",
            "content-type": "application/json",
            "origin": "https://flowith.io",
            "referer": "https://edge.flowith.net/",
            "user-agent": fingerprint["user_agent"],
            "dnt": "1",
            "sec-gpc": "1"
        }
        session = requests.Session()
        session.headers.update(headers)
        node_id = str(uuid.uuid4())
        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "nodeId": node_id
        }
        payload.update(kwargs)

        def for_stream():
            try:
                response = session.post(
                    url,
                    json=payload,
                    stream=True,
                    timeout=timeout or 30,
                    proxies=proxies
                )
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=4096):
                    if not chunk:
                        break
                    text = chunk.decode('utf-8', errors='replace')
                    delta = ChoiceDelta(content=text, role="assistant")
                    choice = Choice(index=0, delta=delta)
                    chunk_obj = ChatCompletionChunk(
                        id=request_id,
                        choices=[choice],
                        created=created_time,
                        model=model,
                        system_fingerprint=None
                    )
                    yield chunk_obj
            except Exception as e:
                raise RuntimeError(f"Flowith streaming request failed: {e}")

        def for_non_stream():
            try:
                response = session.post(
                    url,
                    json=payload,
                    timeout=timeout or 30,
                    proxies=proxies
                )
                response.raise_for_status()
                encoding = response.headers.get('Content-Encoding', '').lower()
                
                # Try to handle different compression formats
                if encoding == 'zstd':
                    try:
                        # First, check if the content is actually zstd compressed
                        if response.content.startswith(b'\x28\xb5\x2f\xfd'):  # zstd magic number
                            dctx = zstd.ZstdDecompressor()
                            text = dctx.decompress(response.content).decode('utf-8', errors='replace')
                        else:
                            text = response.content.decode('utf-8', errors='replace')
                    except Exception as zstd_error:
                        text = response.content.decode('utf-8', errors='replace')
                elif encoding in ['gzip', 'deflate', 'br']:
                    # Let requests handle other compression formats automatically
                    text = response.text
                else:
                    text = response.text
                
                # Flowith returns raw text, not JSON
                content = text.strip()
                message = ChatCompletionMessage(role="assistant", content=content)
                choice = Choice(index=0, message=message, finish_reason="stop")
                usage = CompletionUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
                completion = ChatCompletion(
                    id=request_id,
                    choices=[choice],
                    created=created_time,
                    model=model,
                    usage=usage
                )
                return completion
            except Exception as e:
                raise RuntimeError(f"Flowith request failed: {e}")

        return for_stream() if stream else for_non_stream()

class Chat(BaseChat):
    def __init__(self, client: 'Flowith'):
        self.completions = Completions(client)

class Flowith(OpenAICompatibleProvider):
    AVAILABLE_MODELS = [
        "gpt-5-nano", "gpt-5-mini", "glm-4.5", "gpt-oss-120b", "gpt-oss-20b", "kimi-k2",
        "gpt-4.1", "gpt-4.1-mini", "deepseek-chat", "deepseek-reasoner",
        "gemini-2.5-flash", "grok-3-mini", "claude-haiku-4.5"
    ]

    chat: Chat
    def __init__(self):
        self.chat = Chat(self)

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()

if __name__ == "__main__":
    # Example usage
    client = Flowith()
    messages = [{"role": "user", "content": "Hello, how are you?"}]
    response = client.chat.completions.create(
        model="gpt-oss-120b",
        messages=messages,
        stream=True
    )
    for chunk in response:
        print(chunk.choices[0].delta.content, end="", flush=True)
    print()