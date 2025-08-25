import time
import uuid
import requests
from typing import List, Dict, Optional, Union, Generator, Any

from webscout.litagent import LitAgent
from .base import BaseChat, BaseCompletions, OpenAICompatibleProvider
from .utils import (
    ChatCompletion,
    ChatCompletionChunk,
    Choice,
    ChatCompletionMessage,
    ChoiceDelta,
    CompletionUsage,
    format_prompt,
    count_tokens
)

# ANSI escape codes for formatting
BOLD = "\033[1m"
RED = "\033[91m"
RESET = "\033[0m"

class Completions(BaseCompletions):
    def __init__(self, client: 'HeckAI'):
        self._client = client

    def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,  # Not used by HeckAI but kept for compatibility
        stream: bool = False,
        temperature: Optional[float] = None,  # Not used by HeckAI but kept for compatibility
        top_p: Optional[float] = None,  # Not used by HeckAI but kept for compatibility
        timeout: Optional[int] = None,
        proxies: Optional[Dict[str, str]] = None,
        **kwargs: Any  # Not used by HeckAI but kept for compatibility
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Creates a model response for the given chat conversation.
        Mimics openai.chat.completions.create
        """
        # Format the messages using the format_prompt utility
        # This creates a conversation in the format: "User: message\nAssistant: response\nUser: message\nAssistant:"
        # HeckAI works better with a properly formatted conversation
        question = format_prompt(messages, add_special_tokens=True)

        # Prepare the payload for HeckAI API
        model = self._client.convert_model_name(model)
        payload = {
            "model": model,
            "question": question,
            "language": self._client.language,
            "sessionId": self._client.session_id,
            "previousQuestion": None,
            "previousAnswer": None,
            "imgUrls": [],
            "superSmartMode": False
        }

        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())

        if stream:
            return self._create_stream(request_id, created_time, model, payload, timeout, proxies)
        else:
            return self._create_non_stream(request_id, created_time, model, payload, timeout, proxies)

    def _create_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any], timeout: Optional[int] = None, proxies: Optional[Dict[str, str]] = None
    ) -> Generator[ChatCompletionChunk, None, None]:
        try:
            response = self._client.session.post(
                self._client.url,
                headers=self._client.headers,
                json=payload,
                stream=True,
                timeout=timeout or self._client.timeout,
                proxies=proxies or getattr(self._client, "proxies", None)
            )
            response.raise_for_status()

            streaming_text = []
            in_answer = False

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data: "):
                    data = line[6:]
                else:
                    continue
                if data == "[ANSWER_START]":
                    in_answer = True
                    continue
                if data == "[ANSWER_DONE]":
                    in_answer = False
                    continue
                if data.startswith("[") and data.endswith("]"):
                    continue
                if in_answer:
                    # Fix encoding issues (e.g., emoji) for each chunk
                    try:
                        data_fixed = data.encode('latin1').decode('utf-8')
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        data_fixed = data
                    streaming_text.append(data_fixed)
                    delta = ChoiceDelta(content=data_fixed)
                    choice = Choice(index=0, delta=delta, finish_reason=None)
                    chunk = ChatCompletionChunk(
                        id=request_id,
                        choices=[choice],
                        created=created_time,
                        model=model,
                    )
                    yield chunk
            # Final chunk with finish_reason
            delta = ChoiceDelta(content=None)
            choice = Choice(index=0, delta=delta, finish_reason="stop")
            chunk = ChatCompletionChunk(
                id=request_id,
                choices=[choice],
                created=created_time,
                model=model,
            )
            yield chunk
        except requests.exceptions.RequestException as e:
            print(f"{RED}Error during HeckAI stream request: {e}{RESET}")
            raise IOError(f"HeckAI request failed: {e}") from e

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any], timeout: Optional[int] = None, proxies: Optional[Dict[str, str]] = None
    ) -> ChatCompletion:
        try:
            answer_lines = []
            in_answer = False
            response = self._client.session.post(
                self._client.url,
                headers=self._client.headers,
                json=payload,
                stream=True,
                timeout=timeout or self._client.timeout,
                proxies=proxies or getattr(self._client, "proxies", None)
            )
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data: "):
                    data = line[6:]
                else:
                    continue
                if data == "[ANSWER_START]":
                    in_answer = True
                    continue
                if data == "[ANSWER_DONE]":
                    in_answer = False
                    continue
                if data.startswith("[") and data.endswith("]"):
                    continue
                if in_answer:
                    answer_lines.append(data)
            full_text = " ".join(x.strip() for x in answer_lines if x.strip())
            # Fix encoding issues (e.g., emoji)
            try:
                full_text = full_text.encode('latin1').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
            prompt_tokens = count_tokens(payload.get("question", ""))
            completion_tokens = count_tokens(full_text)
            total_tokens = prompt_tokens + completion_tokens
            usage = CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )
            message = ChatCompletionMessage(
                role="assistant",
                content=full_text)
            choice = Choice(
                index=0,
                message=message,
                finish_reason="stop"
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
            print(f"{RED}Error during HeckAI non-stream request: {e}{RESET}")
            raise IOError(f"HeckAI request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'HeckAI'):
        self.completions = Completions(client)

class HeckAI(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for HeckAI API.

    Usage:
        client = HeckAI()
        response = client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print(response.choices[0].message.content)
    """

    AVAILABLE_MODELS = [
        "google/gemini-2.5-flash-preview",
        "deepseek/deepseek-chat",
        "deepseek/deepseek-r1",
        "openai/gpt-4o-mini",
        "openai/gpt-4.1-mini",
        "x-ai/grok-3-mini-beta",
        "meta-llama/llama-4-scout",
        "openai/gpt-5-mini",
        "openai/gpt-5-nano"

    ]

    def __init__(
        self,
        timeout: int = 30,
        language: str = "English"
    ):
        """
        Initialize the HeckAI client.

        Args:
            timeout: Request timeout in seconds.
            language: Language for responses.
        """
        self.timeout = timeout
        self.language = language
        self.url = "https://api.heckai.weight-wave.com/api/ha/v1/chat"
        self.session_id = str(uuid.uuid4())

        # Use LitAgent for user-agent
        agent = LitAgent()
        self.headers = {
            'User-Agent': agent.random(),
            'Content-Type': 'application/json',
            'Origin': 'https://heck.ai',
            'Referer': 'https://heck.ai/',
            'Connection': 'keep-alive'
        }

        self.session = requests.Session()
        self.session.headers.update(self.headers)

        # Initialize the chat interface
        self.chat = Chat(self)

    def convert_model_name(self, model: str) -> str:
        """
        Ensure the model name is in the correct format.
        """
        if model in self.AVAILABLE_MODELS:
            return model

        # Try to find a matching model
        for available_model in self.AVAILABLE_MODELS:
            if model.lower() in available_model.lower():
                return available_model

        # Default to gemini if no match
        print(f"{BOLD}Warning: Model '{model}' not found, using default model 'google/gemini-2.0-flash-001'{RESET}")
        return "google/gemini-2.0-flash-001"

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()

# Simple test if run directly
if __name__ == "__main__":
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)

    for model in HeckAI.AVAILABLE_MODELS:
        try:
            client = HeckAI(timeout=60)
            # Test with a simple conversation to demonstrate format_prompt usage
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Say 'Hello' in one word"},
                ],
                stream=False
            )

            if response and response.choices and response.choices[0].message.content:
                status = "✓"
                # Truncate response if too long
                display_text = response.choices[0].message.content.strip()
                display_text = display_text[:50] + "..." if len(display_text) > 50 else display_text
            else:
                status = "✗"
                display_text = "Empty or invalid response"
            print(f"{model:<50} {status:<10} {display_text}")
        except Exception as e:
            print(f"{model:<50} {'✗':<10} {str(e)}")
