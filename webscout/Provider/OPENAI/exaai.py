import time
import uuid
import requests
import json
import re
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
    pass

# --- ExaAI Client ---

# ANSI escape codes for formatting
BOLD = "\033[1m"
RED = "\033[91m"
RESET = "\033[0m"

class Completions(BaseCompletions):
    def __init__(self, client: 'ExaAI'):
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
        # Filter out system messages and warn the user if any are present
        filtered_messages = []
        has_system_message = False

        for msg in messages:
            if msg["role"] == "system":
                has_system_message = True
                continue  # Skip system messages
            filtered_messages.append(msg)

        if has_system_message:
            # Print warning in bold red
            print(f"{BOLD}{RED}Warning: ExaAI does not support system messages, they will be ignored.{RESET}")

        # If no messages left after filtering, raise an error
        if not filtered_messages:
            raise ValueError("At least one user message is required")

        # Generate a unique ID for the conversation
        conversation_id = uuid.uuid4().hex[:16]

        # Prepare the payload for ExaAI API
        payload = {
            "id": conversation_id,
            "messages": filtered_messages
        }

        # Add optional parameters if provided
        if max_tokens is not None and max_tokens > 0:
            payload["max_tokens"] = max_tokens

        if temperature is not None:
            payload["temperature"] = temperature

        if top_p is not None:
            payload["top_p"] = top_p

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

            for line in response.iter_lines(decode_unicode=True):
                if line:
                    match = re.search(r'0:"(.*?)"', line)
                    if match:
                        content = match.group(1)

                        # Format the content (replace escaped newlines)
                        content = self._client.format_text(content)

                        # Update token counts
                        completion_tokens += count_tokens(content)
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
            print(f"Error during ExaAI stream request: {e}")
            raise IOError(f"ExaAI request failed: {e}") from e

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
            print(f"Error during ExaAI non-stream request: {e}")
            raise IOError(f"ExaAI request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'ExaAI'):
        self.completions = Completions(client)

class ExaAI(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for ExaAI API.

    Usage:
        client = ExaAI()
        response = client.chat.completions.create(
            model="O3-Mini",
            messages=[{"role": "user", "content": "Hello!"}]
        )

    Note:
        ExaAI does not support system messages. Any system messages will be ignored.
    """

    AVAILABLE_MODELS = ["O3-Mini"]

    def __init__(
        self,
        timeout: Optional[int] = None,
        browser: str = "chrome"
    ):
        """
        Initialize the ExaAI client.

        Args:
            timeout: Request timeout in seconds (None for no timeout)
            browser: Browser to emulate in user agent
        """
        self.timeout = timeout
        self.api_endpoint = "https://o3minichat.exa.ai/api/chat"
        self.session = requests.Session()

        # Initialize LitAgent for user agent generation
        agent = LitAgent()
        self.fingerprint = agent.generate_fingerprint(browser)

        # Headers for the request
        self.headers = {
            "authority": "o3minichat.exa.ai",
            "accept": self.fingerprint["accept"],
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": self.fingerprint["accept_language"],
            "content-type": "application/json",
            "dnt": "1",
            "origin": "https://o3minichat.exa.ai",
            "priority": "u=1, i",
            "referer": "https://o3minichat.exa.ai/",
            "sec-ch-ua": self.fingerprint["sec_ch_ua"] or '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": f'"{self.fingerprint["platform"]}"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "sec-gpc": "1",
            "user-agent": self.fingerprint["user_agent"]
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
        Convert model names to ones supported by ExaAI.

        Args:
            model: Model name to convert (ignored as ExaAI only supports O3-Mini)

        Returns:
            ExaAI model name
        """
        # ExaAI only supports O3-Mini, regardless of the input model
        print(f"Note: ExaAI only supports O3-Mini model. Ignoring provided model '{model}'.")
        return "O3-Mini"
    
    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()