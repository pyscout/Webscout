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
    print("Warning: LitAgent not found. Some functionality may be limited.")

# --- Venice Client ---

class Completions(BaseCompletions):
    def __init__(self, client: 'Venice'):
        self._client = client

    def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = 2049,
        stream: bool = False,
        temperature: Optional[float] = 0.8,
        top_p: Optional[float] = 0.9,
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Creates a model response for the given chat conversation.
        Mimics openai.chat.completions.create
        """
        # Extract system message if present for systemPrompt parameter
        system_prompt = self._client.system_prompt
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
                break

        # Prepare the payload for Venice API
        payload = {
            "requestId": str(uuid.uuid4())[:7],
            "modelId": self._client.convert_model_name(model),
            "prompt": messages,
            "systemPrompt": system_prompt,
            "conversationType": "text",
            "temperature": temperature if temperature is not None else self._client.temperature,
            "webEnabled": True,
            "topP": top_p if top_p is not None else self._client.top_p,
            "includeVeniceSystemPrompt": False,
            "isCharacter": False,
            "clientProcessingTime": 2000
        }

        # Add optional parameters if provided
        if max_tokens is not None and max_tokens > 0:
            payload["max_tokens"] = max_tokens

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
                json=payload,
                stream=True,
                timeout=self._client.timeout
            )

            # Handle non-200 responses
            if response.status_code != 200:
                raise IOError(
                    f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                )

            # Track token usage across chunks
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0

            # Estimate prompt tokens based on message length
            prompt_tokens = 0
            for msg in payload.get("prompt", []):
                prompt_tokens += count_tokens(msg.get("content", ""))
            prompt_tokens += count_tokens(payload.get("systemPrompt", ""))

            for line in response.iter_lines():
                if not line:
                    continue

                try:
                    # Decode bytes to string
                    line_data = line.decode('utf-8').strip()
                    if '"kind":"content"' in line_data:
                        data = json.loads(line_data)
                        if 'content' in data:
                            content = data['content']

                            # Format the content (replace escaped newlines)
                            content = self._client.format_text(content)

                            # Update token counts
                            completion_tokens += 1
                            total_tokens = prompt_tokens + completion_tokens

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
                                finish_reason=None,
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

                            # Convert to dict for proper formatting
                            chunk_dict = chunk.to_dict()

                            # Add usage information to match OpenAI format
                            usage_dict = {
                                "prompt_tokens": prompt_tokens,
                                "completion_tokens": completion_tokens,
                                "total_tokens": total_tokens,
                                "estimated_cost": None
                            }

                            chunk_dict["usage"] = usage_dict

                            # Return the chunk object for internal processing
                            yield chunk
                except json.JSONDecodeError:
                    continue
                except UnicodeDecodeError:
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
            print(f"Error during Venice stream request: {e}")
            raise IOError(f"Venice request failed: {e}") from e

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any]
    ) -> ChatCompletion:
        try:
            # For non-streaming, we still use streaming internally to collect the full response
            response = self._client.session.post(
                self._client.api_endpoint,
                json=payload,
                stream=True,
                timeout=self._client.timeout
            )

            # Handle non-200 responses
            if response.status_code != 200:
                raise IOError(
                    f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                )

            # Collect the full response
            full_text = ""
            for line in response.iter_lines():
                if not line:
                    continue

                try:
                    # Decode bytes to string
                    line_data = line.decode('utf-8').strip()
                    if '"kind":"content"' in line_data:
                        data = json.loads(line_data)
                        if 'content' in data:
                            content = data['content']
                            full_text += content
                except json.JSONDecodeError:
                    continue
                except UnicodeDecodeError:
                    continue

            # Format the text (replace escaped newlines)
            full_text = self._client.format_text(full_text)

            # Estimate token counts
            prompt_tokens = 0
            for msg in payload.get("prompt", []):
                prompt_tokens += count_tokens(msg.get("content", ""))
            prompt_tokens += count_tokens(payload.get("systemPrompt", ""))
            completion_tokens = count_tokens(full_text)
            total_tokens = prompt_tokens + completion_tokens

            # Create the message object
            message = ChatCompletionMessage(
                role="assistant",
                content=full_text
            )

            # Create the choice object
            choice = Choice(
                index=0,
                message=message,
                finish_reason="stop"
            )

            # Create the usage object
            usage = CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
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
            print(f"Error during Venice non-stream request: {e}")
            raise IOError(f"Venice request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'Venice'):
        self.completions = Completions(client)

class Venice(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for Venice AI API.

    Usage:
        client = Venice()
        response = client.chat.completions.create(
            model="mistral-31-24b",
            messages=[{"role": "user", "content": "Hello!"}]
        )
    """

    AVAILABLE_MODELS = [
        "mistral-31-24b",
        "llama-3.2-3b-akash",
        "qwen2dot5-coder-32b",
        "deepseek-coder-v2-lite",
    ]

    # No model mapping needed as we use the model names directly

    def __init__(
        self,
        timeout: Optional[int] = None,
        browser: str = "chrome"
    ):
        """
        Initialize the Venice client.

        Args:
            timeout: Request timeout in seconds (None for no timeout)
            browser: Browser to emulate in user agent
        """
        self.timeout = timeout
        self.temperature = 0.8  # Default temperature
        self.top_p = 0.9  # Default top_p
        self.system_prompt = "You are a helpful AI assistant."  # Default system prompt
        self.api_endpoint = "https://venice.ai/api/inference/chat"
        self.session = requests.Session()

        # Initialize LitAgent for user agent generation
        agent = LitAgent()
        self.fingerprint = agent.generate_fingerprint(browser)

        # Headers for the request
        self.headers = {
            "User-Agent": self.fingerprint["user_agent"],
            "accept": self.fingerprint["accept"],
            "accept-language": self.fingerprint["accept_language"],
            "content-type": "application/json",
            "origin": "https://venice.ai",
            "referer": "https://venice.ai/chat/",
            "sec-ch-ua": self.fingerprint["sec_ch_ua"] or '"Google Chrome";v="133", "Chromium";v="133", "Not?A_Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": f'"{self.fingerprint["platform"]}"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin"
        }

        self.session.headers.update(self.headers)

        # Initialize the chat interface
        self.chat = Chat(self)

    def format_text(self, text: str) -> str:
        """
        Format text by replacing escaped newlines with actual newlines.

        Args:
            text: Text to format

        Returns:
            Formatted text
        """
        # Use a more comprehensive approach to handle all escape sequences
        try:
            # First handle double backslashes to avoid issues
            text = text.replace('\\\\', '\\')

            # Handle common escape sequences
            text = text.replace('\\n', '\n')
            text = text.replace('\\r', '\r')
            text = text.replace('\\t', '\t')
            text = text.replace('\\"', '"')
            text = text.replace("\\'", "'")

            # Handle any remaining escape sequences using JSON decoding
            # This is a fallback in case there are other escape sequences
            try:
                # Add quotes to make it a valid JSON string
                json_str = f'"{text}"'
                # Use json module to decode all escape sequences
                decoded = json.loads(json_str)
                return decoded
            except json.JSONDecodeError:
                # If JSON decoding fails, return the text with the replacements we've already done
                return text
        except Exception as e:
            # If any error occurs, return the original text
            print(f"Warning: Error formatting text: {e}")
            return text

    def convert_model_name(self, model: str) -> str:
        """
        Convert model names to ones supported by Venice.

        Args:
            model: Model name to convert

        Returns:
            Venice model name
        """
        # If the model is already a valid Venice model, return it
        if model in self.AVAILABLE_MODELS:
            return model

        # Default to the most capable model
        print(f"Warning: Unknown model '{model}'. Using 'mistral-31-24b' instead.")
        return "mistral-31-24b"

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()

    @classmethod
    def models(cls):
        """Return the list of available models for Venice."""
        return cls.AVAILABLE_MODELS
