import time
import uuid
import requests
import json
from typing import List, Dict, Optional, Union, Generator, Any

# Import base classes and utility structures
from .base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from .utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage, ToolCall, ToolFunction, count_tokens
)

# Import LitAgent for browser fingerprinting
from webscout.litagent import LitAgent

# ANSI escape codes for formatting
BOLD = "\033[1m"
RED = "\033[91m"
RESET = "\033[0m"

class Completions(BaseCompletions):
    def __init__(self, client: 'TextPollinations'):
        self._client = client

    def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        stream: bool = False,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
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
            "model": model,
            "messages": messages,
            "stream": stream,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice

        payload.update(kwargs)

        request_id = str(uuid.uuid4())
        created_time = int(time.time())

        if stream:
            return self._create_streaming(request_id, created_time, model, payload, timeout, proxies)
        else:
            return self._create_non_streaming(request_id, created_time, model, payload, timeout, proxies)

    def _create_streaming(
        self,
        request_id: str,
        created_time: int,
        model: str,
        payload: Dict[str, Any],
        timeout: Optional[int] = None,
        proxies: Optional[Dict[str, str]] = None
    ) -> Generator[ChatCompletionChunk, None, None]:
        """Implementation for streaming chat completions."""
        try:

            # Make the streaming request
            response = self._client.session.post(
                self._client.api_endpoint,
                headers=self._client.headers,
                json=payload,
                stream=True,
                timeout=timeout or self._client.timeout,
                proxies=proxies or getattr(self._client, "proxies", None)
            )

            if not response.ok:
                raise IOError(f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}")

            # Process the streaming response
            full_response = ""

            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8').strip()
                    if line == "data: [DONE]":
                        break
                    if line.startswith('data: '):
                        try:
                            json_data = json.loads(line[6:])
                            if 'choices' in json_data and len(json_data['choices']) > 0:
                                choice = json_data['choices'][0]
                                if 'delta' in choice:
                                    delta_obj = ChoiceDelta()

                                    # Handle content in delta
                                    if 'content' in choice['delta']:
                                        content = choice['delta']['content']
                                        full_response += content
                                        delta_obj.content = content

                                    # Handle tool calls in delta
                                    if 'tool_calls' in choice['delta']:
                                        tool_calls = []
                                        for tool_call_data in choice['delta']['tool_calls']:
                                            if 'function' in tool_call_data:
                                                function = ToolFunction(
                                                    name=tool_call_data['function'].get('name', ''),
                                                    arguments=tool_call_data['function'].get('arguments', '')
                                                )
                                                tool_call = ToolCall(
                                                    id=tool_call_data.get('id', str(uuid.uuid4())),
                                                    type=tool_call_data.get('type', 'function'),
                                                    function=function
                                                )
                                                tool_calls.append(tool_call)

                                        if tool_calls:
                                            delta_obj.tool_calls = tool_calls

                                    # Create and yield a chunk
                                    choice_obj = Choice(index=0, delta=delta_obj, finish_reason=None)
                                    chunk = ChatCompletionChunk(
                                        id=request_id,
                                        choices=[choice_obj],
                                        created=created_time,
                                        model=model
                                    )

                                    yield chunk
                        except json.JSONDecodeError:
                            continue

            # Final chunk with finish_reason
            delta = ChoiceDelta(content=None)
            choice = Choice(index=0, delta=delta, finish_reason="stop")
            chunk = ChatCompletionChunk(
                id=request_id,
                choices=[choice],
                created=created_time,
                model=model
            )

            yield chunk

        except Exception as e:
            print(f"{RED}Error during TextPollinations streaming request: {e}{RESET}")
            raise IOError(f"TextPollinations streaming request failed: {e}") from e

    def _create_non_streaming(
        self,
        request_id: str,
        created_time: int,
        model: str,
        payload: Dict[str, Any],
        timeout: Optional[int] = None,
        proxies: Optional[Dict[str, str]] = None
    ) -> ChatCompletion:
        """Implementation for non-streaming chat completions."""
        try:

            # Make the non-streaming request
            response = self._client.session.post(
                self._client.api_endpoint,
                headers=self._client.headers,
                json=payload,
                timeout=timeout or self._client.timeout,
                proxies=proxies or getattr(self._client, "proxies", None)
            )

            if not response.ok:
                raise IOError(f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}")

            # Parse the response
            response_json = response.json()

            # Extract the content
            if 'choices' in response_json and len(response_json['choices']) > 0:
                choice_data = response_json['choices'][0]
                if 'message' in choice_data:
                    message_data = choice_data['message']

                    # Extract content
                    full_content = message_data.get('content', '')

                    # Create the completion message with potential tool calls
                    message = ChatCompletionMessage(role="assistant", content=full_content)

                    # Handle tool calls if present
                    if 'tool_calls' in message_data:
                        tool_calls = []
                        for tool_call_data in message_data['tool_calls']:
                            if 'function' in tool_call_data:
                                function = ToolFunction(
                                    name=tool_call_data['function'].get('name', ''),
                                    arguments=tool_call_data['function'].get('arguments', '')
                                )
                                tool_call = ToolCall(
                                    id=tool_call_data.get('id', str(uuid.uuid4())),
                                    type=tool_call_data.get('type', 'function'),
                                    function=function
                                )
                                tool_calls.append(tool_call)

                        if tool_calls:
                            message.tool_calls = tool_calls
                else:
                    # Fallback if no message is present
                    message = ChatCompletionMessage(role="assistant", content="")
            else:
                # Fallback if no choices are present
                message = ChatCompletionMessage(role="assistant", content="")

            # Create the choice
            choice = Choice(
                index=0,
                message=message,
                finish_reason="stop"
            )

            # Estimate token usage using count_tokens
            prompt_tokens = count_tokens([msg.get("content", "") for msg in payload.get("messages", [])])
            completion_tokens = count_tokens(full_content)
            usage = CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
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
            print(f"{RED}Error during TextPollinations non-stream request: {e}{RESET}")
            raise IOError(f"TextPollinations request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'TextPollinations'):
        self.completions = Completions(client)

class TextPollinations(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for TextPollinations API.

    Usage:
        client = TextPollinations()
        response = client.chat.completions.create(
            model="openai-large",
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print(response.choices[0].message.content)
    """

    AVAILABLE_MODELS = [
        "deepseek-reasoning",
        "gemini",
        "mistral",
        "nova-fast",
        "openai",
        "openai-audio",
        "openai-fast",
        "openai-reasoning",
        "qwen-coder",
        "roblox-rp",
        "bidara",
        "evil",
        "midijourney",
        "mirexa",
        "rtist",
        "unity",
    ]

    def __init__(
        self,
        timeout: int = 30,
        proxies: dict = {}
    ):
        """
        Initialize the TextPollinations client.

        Args:
            timeout: Request timeout in seconds
            proxies: Optional proxy configuration
        """
        self.timeout = timeout
        self.api_endpoint = "https://text.pollinations.ai/openai"
        self.proxies = proxies

        # Initialize session
        self.session = requests.Session()
        if proxies:
            self.session.proxies.update(proxies)

        # Initialize LitAgent for user agent generation
        agent = LitAgent()
        self.user_agent = agent.random()

        # Set headers
        self.headers = {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'User-Agent': self.user_agent,
            'Content-Type': 'application/json',
        }

        self.session.headers.update(self.headers)

        # Initialize chat interface
        self.chat = Chat(self)

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()
