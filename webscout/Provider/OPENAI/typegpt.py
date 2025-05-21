import time
import uuid
import requests
import json
from typing import List, Dict, Optional, Union, Generator, Any

# Import base classes and utility structures
from .base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from .utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage, count_tokens
)

# Attempt to import LitAgent, fallback if not available
try:
    from webscout.litagent import LitAgent
except ImportError:
    print("Warning: LitAgent not found. Functionality may be limited.")

# --- TypeGPT Client ---

class Completions(BaseCompletions):
    def __init__(self, client: 'TypeGPT'):
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
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Creates a model response for the given chat conversation.
        Mimics openai.chat.completions.create
        """
        # Prepare the payload for TypeGPT API
        payload = {
            "messages": messages,
            "stream": stream,
            "model": self._client.convert_model_name(model),
            "temperature": temperature if temperature is not None else self._client.temperature,
            "top_p": top_p if top_p is not None else self._client.top_p,
            "presence_penalty": presence_penalty if presence_penalty is not None else self._client.presence_penalty,
            "frequency_penalty": frequency_penalty if frequency_penalty is not None else self._client.frequency_penalty,
            "max_tokens": max_tokens if max_tokens is not None else self._client.max_tokens,
        }

        # Add any additional parameters
        for key, value in kwargs.items():
            if key not in payload:
                payload[key] = value

        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())

        if stream:
            return self._create_stream(request_id, created_time, model, payload)
        else:
            return self._create_non_stream(request_id, created_time, model, payload)

    def _create_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any]
    ) -> Generator[ChatCompletionChunk, None, None]:
        try:
            response = self._client.session.post(
                self._client.api_endpoint,
                headers=self._client.headers,
                json=payload,
                stream=True,
                timeout=self._client.timeout
            )

            # Handle non-200 responses
            if not response.ok:
                raise IOError(
                    f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                )

            # Track token usage across chunks
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0

            # Estimate prompt tokens based on message length
            for msg in payload.get("messages", []):
                prompt_tokens += count_tokens(msg.get("content", ""))

            for line in response.iter_lines():
                if not line:
                    continue

                decoded_line = line.decode('utf-8').strip()

                if decoded_line.startswith("data: "):
                    json_str = decoded_line[6:]
                    if json_str == "[DONE]":
                        break

                    try:
                        data = json.loads(json_str)
                        choice_data = data.get('choices', [{}])[0]
                        delta_data = choice_data.get('delta', {})
                        finish_reason = choice_data.get('finish_reason')

                        # Update token counts if available
                        usage_data = data.get('usage', {})
                        if usage_data:
                            prompt_tokens = usage_data.get('prompt_tokens', prompt_tokens)
                            completion_tokens = usage_data.get('completion_tokens', completion_tokens)
                            total_tokens = usage_data.get('total_tokens', total_tokens)

                        # Create the delta object
                        delta = ChoiceDelta(
                            content=delta_data.get('content'),
                            role=delta_data.get('role'),
                            tool_calls=delta_data.get('tool_calls')
                        )

                        # Create the choice object
                        choice = Choice(
                            index=choice_data.get('index', 0),
                            delta=delta,
                            finish_reason=finish_reason,
                            logprobs=choice_data.get('logprobs')
                        )

                        # Create the chunk object
                        chunk = ChatCompletionChunk(
                            id=request_id,
                            choices=[choice],
                            created=created_time,
                            model=model,
                            system_fingerprint=data.get('system_fingerprint')
                        )

                        # Convert to dict for proper formatting
                        chunk_dict = chunk.to_dict()

                        # Add usage information to match OpenAI format
                        usage_dict = {
                            "prompt_tokens": prompt_tokens or 10,
                            "completion_tokens": completion_tokens or (len(delta_data.get('content', '')) if delta_data.get('content') else 0),
                            "total_tokens": total_tokens or (10 + (len(delta_data.get('content', '')) if delta_data.get('content') else 0)),
                            "estimated_cost": None
                        }

                        # Update completion_tokens and total_tokens as we receive more content
                        if delta_data.get('content'):
                            completion_tokens += 1
                            total_tokens = prompt_tokens + completion_tokens
                            usage_dict["completion_tokens"] = completion_tokens
                            usage_dict["total_tokens"] = total_tokens

                        chunk_dict["usage"] = usage_dict

                        # Return the chunk object for internal processing
                        yield chunk
                    except json.JSONDecodeError:
                        print(f"Warning: Could not decode JSON line: {json_str}")
                        continue

            # Final chunk with finish_reason="stop"
            delta = ChoiceDelta(
                content=None,
                role=None,
                tool_calls=None
            )

            choice = Choice(
                index=0,
                delta=delta,
                finish_reason="stop",
                logprobs=None
            )

            chunk = ChatCompletionChunk(
                id=request_id,
                choices=[choice],
                created=created_time,
                model=model,
                system_fingerprint=None
            )

            chunk_dict = chunk.to_dict()
            chunk_dict["usage"] = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "estimated_cost": None
            }

            yield chunk

        except Exception as e:
            print(f"Error during TypeGPT stream request: {e}")
            raise IOError(f"TypeGPT request failed: {e}") from e

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any]
    ) -> ChatCompletion:
        try:
            response = self._client.session.post(
                self._client.api_endpoint,
                headers=self._client.headers,
                json=payload,
                timeout=self._client.timeout
            )

            # Handle non-200 responses
            if not response.ok:
                raise IOError(
                    f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                )

            # Parse the response
            data = response.json()

            choices_data = data.get('choices', [])
            usage_data = data.get('usage', {})

            choices = []
            for choice_d in choices_data:
                message_d = choice_d.get('message', {})
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
            print(f"Error during TypeGPT non-stream request: {e}")
            raise IOError(f"TypeGPT request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'TypeGPT'):
        self.completions = Completions(client)

class TypeGPT(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for TypeGPT API.

    Usage:
        client = TypeGPT()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello!"}]
        )
    """

    AVAILABLE_MODELS = [
        # Working Models (based on testing)
        "gpt-4o-mini-2024-07-18",
        "chatgpt-4o-latest",
        "deepseek-r1",
        "deepseek-v3",
        "uncensored-r1",
        "Image-Generator",
    ]

    def __init__(
        self,
        timeout: Optional[int] = None,
        browser: str = "chrome"
    ):
        """
        Initialize the TypeGPT client.

        Args:
            timeout: Request timeout in seconds (None for no timeout)
            browser: Browser to emulate in user agent
        """
        self.timeout = timeout or 60  # Default to 30 seconds if None
        self.api_endpoint = "https://chat.typegpt.net/api/openai/v1/chat/completions"
        self.session = requests.Session()

        # Default parameters
        self.max_tokens = 4000
        self.temperature = 0.5
        self.presence_penalty = 0
        self.frequency_penalty = 0
        self.top_p = 1

        # Initialize LitAgent for user agent generation
        agent = LitAgent()
        self.fingerprint = agent.generate_fingerprint(browser)

        # Headers for the request
        self.headers = {
            "authority": "chat.typegpt.net",
            "accept": "application/json, text/event-stream",
            "accept-language": self.fingerprint["accept_language"],
            "content-type": "application/json",
            "origin": "https://chat.typegpt.net",
            "referer": "https://chat.typegpt.net/",
            "user-agent": self.fingerprint["user_agent"]
        }

        self.session.headers.update(self.headers)

        # Initialize the chat interface
        self.chat = Chat(self)

    def convert_model_name(self, model: str) -> str:
        """
        Convert model names to ones supported by TypeGPT.

        Args:
            model: Model name to convert

        Returns:
            TypeGPT model name
        """
        # If the model is already a valid TypeGPT model, return it
        if model in self.AVAILABLE_MODELS:
            return model

        # Default to chatgpt-4o-latest if model not found (this one works reliably)
        print(f"Warning: Unknown model '{model}'. Using 'chatgpt-4o-latest' instead.")
        return "chatgpt-4o-latest"

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()

    @classmethod
    def models(cls):
        """Return the list of available models for TypeGPT."""
        return cls.AVAILABLE_MODELS
