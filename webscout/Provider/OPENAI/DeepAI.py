"""
DeepAI Chat Provider for webscout

This provider implements the DeepAI chat API discovered through reverse engineering.
The API uses a POST endpoint with multipart/form-data containing chat history and parameters.

API Details:
- Endpoint: https://api.deepai.org/hacking_is_a_serious_crime
- Method: POST
- Authentication: api-key header (trial key provided)
- Content-Type: multipart/form-data
- Response: Plain text AI response

Features:
- Streaming and non-streaming support
- Conversation history management
- Error handling and retries
- Configurable model and chat style
"""

from typing import List, Dict, Optional, Union, Generator, Any

# Import requests for HTTP requests
import requests

# Standard library imports
import json
import time
import uuid

# Import base classes and utility structures
from .base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from .utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage
)

# Attempt to import LitAgent, fallback if not available
try:
    from webscout.litagent import LitAgent
except ImportError:
    LitAgent = None

# --- DeepAI Client ---

class Completions(BaseCompletions):
    def __init__(self, client: 'DeepAI'):
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
        tools: Optional[List[Union[Dict[str, Any], Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        timeout: Optional[int] = None,
        proxies: Optional[Dict[str, str]] = None,
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Creates a model response for the given chat conversation.
        Mimics openai.chat.completions.create
        """
        payload = {
            "chat_style": self._client.chat_style,
            "chatHistory": json.dumps(messages),
            "model": model,
            "hacker_is_stinky": "very_stinky",
            "enabled_tools": json.dumps(self._client.enabled_tools)
        }

        # Add optional parameters if provided
        if max_tokens is not None and max_tokens > 0:
            payload["max_tokens"] = max_tokens

        if temperature is not None:
            payload["temperature"] = temperature

        if top_p is not None:
            payload["top_p"] = top_p

        # Add any additional parameters
        payload.update(kwargs)

        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())

        if stream:
            return self._create_stream(request_id, created_time, model, payload)
        else:
            return self._create_non_stream(request_id, created_time, model, payload)

    def _create_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any]
    ) -> Generator[ChatCompletionChunk, None, None]:
        # DeepAI doesn't actually support streaming, but we'll implement it for compatibility
        # For now, just yield the non-stream response as a single chunk
        try:
            response = self._client.session.post(
                "https://api.deepai.org/hacking_is_a_serious_crime",
                data=payload,
                timeout=self._client.timeout,
                impersonate="chrome110"  # Use impersonate for better compatibility
            )

            if response.status_code != 200:
                raise IOError(f"DeepAI request failed with status code {response.status_code}: {response.text}")

            # Get response text
            content = response.text.strip()

            # Create the delta object
            delta = ChoiceDelta(
                content=content,
                role="assistant",
                tool_calls=None
            )

            # Create the choice object
            choice = Choice(
                index=0,
                delta=delta,
                finish_reason="stop",
                logprobs=None
            )

            # Create the chunk object
            chunk = ChatCompletionChunk(
                id=request_id,
                choices=[choice],
                created=created_time,
                model=model,
                system_fingerprint=None
            )

            # Set usage directly on the chunk object (estimated)
            chunk.usage = {
                "prompt_tokens": len(json.dumps(payload.get("chatHistory", []))),
                "completion_tokens": len(content),
                "total_tokens": len(json.dumps(payload.get("chatHistory", []))) + len(content),
                "estimated_cost": None
            }

            yield chunk

        except Exception as e:
            print(f"Error during DeepAI stream request: {e}")
            raise IOError(f"DeepAI request failed: {e}") from e

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any]
    ) -> ChatCompletion:
        try:
            response = self._client.session.post(
                "https://api.deepai.org/hacking_is_a_serious_crime",
                data=payload,
                timeout=self._client.timeout,
                impersonate="chrome110"  # Use impersonate for better compatibility
            )

            if response.status_code != 200:
                raise IOError(f"DeepAI request failed with status code {response.status_code}: {response.text}")

            # Get response text
            content = response.text.strip()

            # Create the message object
            message = ChatCompletionMessage(
                role="assistant",
                content=content
            )

            # Create the choice object
            choice = Choice(
                index=0,
                message=message,
                finish_reason="stop"
            )

            # Create the usage object (estimated)
            usage = CompletionUsage(
                prompt_tokens=len(json.dumps(payload.get("chatHistory", []))),
                completion_tokens=len(content),
                total_tokens=len(json.dumps(payload.get("chatHistory", []))) + len(content)
            )

            # Create the completion object
            completion = ChatCompletion(
                id=request_id,
                choices=[choice],
                created=created_time,
                model=model,
                usage=usage,
            )
            return completion

        except Exception as e:
            print(f"Error during DeepAI non-stream request: {e}")
            raise IOError(f"DeepAI request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'DeepAI'):
        self.completions = Completions(client)

class DeepAI(OpenAICompatibleProvider):
    AVAILABLE_MODELS = [
        "standard", 
        "genius", 
        "online",
        "supergenius",
        "onlinegenius",
        "deepseek-v3.2",
        "gemini-2.5-flash-lite",
        "qwen3-30b-a3b",
        "gpt-5-nano",
        "gpt-oss-120b",
        "gpt-5-chat-latest",
        "claude-opus-4-1",
        "llama-4-scout",
        "claude-4.5-sonnet",
        "deepseek-v3.1-terminus",
        "llama-3.3-70b-instruct",
        "grok-4",
        "claude-sonnet-4",
        "qwen3-coder",
        "gpt-5",
        "kimi-k2-0905",
        "claude-opus-4",
        "gpt-5-mini",
        "gemini-2.5-pro",
        "grok-code-fast-1",
        "gpt-4.1",

    ]

    def __init__(
        self,
        api_key: str = "tryit-53926507126-2c8a2543c7b5638ca6b92b6e53ef2d2b",
        timeout: Optional[int] = 30,
        browser: str = "chrome",
        model: str = "standard",
        chat_style: str = "chat",
        enabled_tools: Optional[List[str]] = None,
        **kwargs
    ):
        self.timeout = timeout
        self.api_key = api_key
        self.model = model
        self.chat_style = chat_style
        self.enabled_tools = enabled_tools or ["image_generator"]

        # Initialize requests Session
        self.session = requests.Session()
        
        # Set up headers with API key
        self.headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "api-key": self.api_key,
            "Accept": "text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        
        # Update session headers
        self.session.headers.update(self.headers)        # Initialize chat interface
        self.chat = Chat(self)

    @classmethod
    def get_models(cls, api_key: str = None):
        """Fetch available models from DeepAI API.

        Args:
            api_key (str, optional): DeepAI API key. If not provided, returns default models.

        Returns:
            list: List of available model IDs
        """
        return cls.AVAILABLE_MODELS

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()

if __name__ == "__main__":
    client = DeepAI()
    response = client.chat.completions.create(
        model="standard",
        messages=[{"role": "user", "content": "Hello!"}],
        stream=False
    )
    print(response.choices[0].message.content)