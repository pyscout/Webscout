import time
import uuid
import requests
import re
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
    # Define a dummy LitAgent if webscout is not installed or accessible
    class LitAgent:
        def generate_fingerprint(self, browser: str = "chrome") -> Dict[str, Any]:
            # Return minimal default headers if LitAgent is unavailable
            print("Warning: LitAgent not found. Using default minimal headers.")
            return {
                "accept": "*/*",
                "accept_language": "en-US,en;q=0.9",
                "platform": "Windows",
                "sec_ch_ua": '"Not/A)Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
                "browser_type": browser,
            }

# --- WiseCat Client ---

class Completions(BaseCompletions):
    def __init__(self, client: 'WiseCat'):
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
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Creates a model response for the given chat conversation.
        Mimics openai.chat.completions.create
        """
        # Prepare the payload for WiseCat API
        payload = {
            "id": "ephemeral",
            "messages": messages,
            "selectedChatModel": self._client.convert_model_name(model)
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
                if line:
                    decoded_line = line.decode('utf-8').strip()

                    # WiseCat uses a different format, so we need to extract the content
                    match = re.search(r'0:"(.*?)"', decoded_line)
                    if match:
                        content = match.group(1)

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
            print(f"Error during WiseCat stream request: {e}")
            raise IOError(f"WiseCat request failed: {e}") from e

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any]
    ) -> ChatCompletion:
        try:
            # For non-streaming, we still use streaming internally to collect the full response
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

            # Collect the full response
            full_text = ""
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    match = re.search(r'0:"(.*?)"', line)
                    if match:
                        content = match.group(1)
                        full_text += content

            # Format the text (replace escaped newlines)
            full_text = self._client.format_text(full_text)

            # Estimate token counts
            prompt_tokens = 0
            for msg in payload.get("messages", []):
                prompt_tokens += count_tokens(msg.get("content", ""))

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
            print(f"Error during WiseCat non-stream request: {e}")
            raise IOError(f"WiseCat request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'WiseCat'):
        self.completions = Completions(client)

class WiseCat(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for WiseCat API.

    Usage:
        client = WiseCat()
        response = client.chat.completions.create(
            model="chat-model-large",
            messages=[{"role": "user", "content": "Hello!"}]
        )
    """

    _base_models = ["chat-model-small", "chat-model-large", "chat-model-reasoning"]
    # Create AVAILABLE_MODELS as a list with the format "WiseCat/model"
    AVAILABLE_MODELS = [f"WiseCat/{model}" for model in _base_models]
    # Create a mapping dictionary for internal use
    _model_mapping = {model: f"WiseCat/{model}" for model in _base_models}

    def __init__(
        self,
        timeout: Optional[int] = None,
        browser: str = "chrome"
    ):
        """
        Initialize the WiseCat client.

        Args:
            timeout: Request timeout in seconds (None for no timeout)
            browser: Browser to emulate in user agent
        """
        self.timeout = timeout
        self.api_endpoint = "https://wise-cat-groq.vercel.app/api/chat"
        self.session = requests.Session()

        # Initialize LitAgent for user agent generation
        agent = LitAgent()
        self.fingerprint = agent.generate_fingerprint(browser)

        # Use the fingerprint for headers
        self.headers = self.fingerprint

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
        Convert model names to ones supported by WiseCat. Accepts both 'WiseCat/model' and raw model names.
        """
        if model.startswith("WiseCat/"):
            model_raw = model.replace("WiseCat/", "", 1)
        else:
            model_raw = model
        if f"WiseCat/{model_raw}" in self.AVAILABLE_MODELS:
            return model_raw
        print(f"Warning: Unknown model '{model}'. Using 'chat-model-large' instead.")
        return "chat-model-large"

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return WiseCat.AVAILABLE_MODELS
        return _ModelList()
