import time
import uuid
import urllib.parse
from curl_cffi.requests import Session, RequestsError
from typing import List, Dict, Optional, Union, Generator, Any

# Import base classes and utility structures
from .base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from .utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage, count_tokens
)

# --- AI4Chat Client ---

class Completions(BaseCompletions):
    def __init__(self, client: 'AI4Chat'):
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
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Creates a model response for the given chat conversation.
        Mimics openai.chat.completions.create
        """
        # Use the format_prompt utility to format the conversation
        from .utils import format_prompt

        # Format the messages into a single string
        conversation_prompt = format_prompt(messages, add_special_tokens=True, include_system=True)

        # Set up request parameters
        country_param = kwargs.get("country", self._client.country)
        user_id_param = kwargs.get("user_id", self._client.user_id)

        # Generate request ID and timestamp
        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())

        # AI4Chat doesn't support streaming, so we'll simulate it if requested
        if stream:
            return self._create_stream(request_id, created_time, model, conversation_prompt, country_param, user_id_param)
        else:
            return self._create_non_stream(request_id, created_time, model, conversation_prompt, country_param, user_id_param)

    def _create_stream(
        self, request_id: str, created_time: int, model: str,
        conversation_prompt: str, country: str, user_id: str
    ) -> Generator[ChatCompletionChunk, None, None]:
        """Simulate streaming by breaking up the full response into fixed-size character chunks."""
        try:
            # Get the full response first
            full_response = self._get_ai4chat_response(conversation_prompt, country, user_id)

            # Track token usage
            prompt_tokens = count_tokens(conversation_prompt)
            completion_tokens = 0

            # Stream fixed-size character chunks (e.g., 48 chars)
            buffer = full_response
            chunk_size = 48
            while buffer:
                chunk_text = buffer[:chunk_size]
                buffer = buffer[chunk_size:]
                completion_tokens += count_tokens(chunk_text)

                if chunk_text.strip():
                    # Create the delta object
                    delta = ChoiceDelta(
                        content=chunk_text,
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

                    yield chunk

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

            yield chunk

        except RequestsError as e:
            print(f"Error during AI4Chat stream request: {e}")
            raise IOError(f"AI4Chat request failed: {e}") from e
        except Exception as e:
            print(f"Unexpected error during AI4Chat stream request: {e}")
            raise IOError(f"AI4Chat request failed: {e}") from e

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str,
        conversation_prompt: str, country: str, user_id: str
    ) -> ChatCompletion:
        """Get a complete response from AI4Chat."""
        try:
            # Get the full response
            full_response = self._get_ai4chat_response(conversation_prompt, country, user_id)

            # Estimate token counts
            prompt_tokens = count_tokens(conversation_prompt)
            completion_tokens = count_tokens(full_response)
            total_tokens = prompt_tokens + completion_tokens

            # Create the message object
            message = ChatCompletionMessage(
                role="assistant",
                content=full_response
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

        except RequestsError as e:
            print(f"Error during AI4Chat non-stream request: {e}")
            raise IOError(f"AI4Chat request failed: {e}") from e
        except Exception as e:
            print(f"Unexpected error during AI4Chat non-stream request: {e}")
            raise IOError(f"AI4Chat request failed: {e}") from e

    def _get_ai4chat_response(self, prompt: str, country: str, user_id: str) -> str:
        """Make the actual API request to AI4Chat."""
        # URL encode parameters
        encoded_text = urllib.parse.quote(prompt)
        encoded_country = urllib.parse.quote(country)
        encoded_user_id = urllib.parse.quote(user_id)

        # Construct the API URL
        url = f"{self._client.api_endpoint}?text={encoded_text}&country={encoded_country}&user_id={encoded_user_id}"

        # Make the request
        try:
            response = self._client.session.get(url, headers=self._client.headers, timeout=self._client.timeout)
            response.raise_for_status()
        except RequestsError as e:
            raise IOError(f"Failed to generate response: {e}")

        # Process the response text
        response_text = response.text

        # Remove surrounding quotes if present
        if response_text.startswith('"'):
            response_text = response_text[1:]
        if response_text.endswith('"'):
            response_text = response_text[:-1]

        # Replace escaped newlines
        response_text = response_text.replace('\\n', '\n').replace('\\n\\n', '\n\n')

        return response_text

class Chat(BaseChat):
    def __init__(self, client: 'AI4Chat'):
        self.completions = Completions(client)

class AI4Chat(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for AI4Chat API.

    Usage:
        client = AI4Chat()
        response = client.chat.completions.create(
            model="default",
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print(response.choices[0].message.content)
    """

    AVAILABLE_MODELS = ["default"]

    def __init__(
        self,
        timeout: int = 30,
        proxies: dict = {},
        system_prompt: str = "You are a helpful and informative AI assistant.",
        country: str = "Asia",
        user_id: str = "usersmjb2oaz7y"
    ):
        """
        Initialize the AI4Chat client.

        Args:
            timeout: Request timeout in seconds
            proxies: Optional proxy configuration
            system_prompt: System prompt to guide the AI's behavior
            country: Country parameter for API
            user_id: User ID for API
        """
        self.timeout = timeout
        self.proxies = proxies
        self.system_prompt = system_prompt
        self.country = country
        self.user_id = user_id

        # API endpoint
        self.api_endpoint = "https://yw85opafq6.execute-api.us-east-1.amazonaws.com/default/boss_mode_15aug"

        # Initialize session
        self.session = Session(timeout=timeout, proxies=proxies)

        # Set headers
        self.headers = {
            "Accept": "*/*",
            "Accept-Language": "id-ID,id;q=0.9",
            "Origin": "https://www.ai4chat.co",
            "Priority": "u=1, i",
            "Referer": "https://www.ai4chat.co/",
            "Sec-CH-UA": '"Chromium";v="131", "Not_A Brand";v="24", "Microsoft Edge Simulate";v="131", "Lemur";v="131"',
            "Sec-CH-UA-Mobile": "?1",
            "Sec-CH-UA-Platform": '"Android"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
        }

        # Update session headers
        self.session.headers.update(self.headers)

        # Initialize chat interface
        self.chat = Chat(self)

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()
