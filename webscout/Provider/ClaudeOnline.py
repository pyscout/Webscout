from typing import Any, Dict, Generator, Optional, Union

from curl_cffi import CurlError
from curl_cffi.requests import Session

from webscout import exceptions
from webscout.AIbase import Provider
from webscout.AIutel import AwesomePrompts, Conversation, Optimizers
from webscout.litagent import LitAgent


class ClaudeOnline(Provider):
    """
    A class to interact with the Claude Online API (claude.online/chat).

    This provider implements the reverse-engineered API from claude.online,
    providing access to Claude AI through their web interface backend.
    """
    required_auth = False
    AVAILABLE_MODELS = ["claude-online"]

    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 2049,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        system_prompt: str = "You are a helpful assistant.",
        model: str = "claude-online"
    ):
        """
        Initializes the Claude Online API client.

        Args:
            is_conversation: Whether the provider is in conversation mode.
            max_tokens: Maximum number of tokens to sample.
            timeout: Timeout for API requests.
            intro: Introduction message for the conversation.
            filepath: Filepath for storing conversation history.
            update_file: Whether to update the conversation history file.
            proxies: Proxies for the API requests.
            history_offset: Offset for conversation history.
            act: Act for the conversation.
            system_prompt: The system prompt to define the assistant's role.
            model: Model to use (only "claude-online" supported).
        """
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        # API endpoints
        self.chat_url = "https://wewordle.org/gptapi/v1/web/turbo"
        self.limit_url = "https://wewordle.org/gptapi/v1/web/get_limit"

        # Initialize LitAgent for user agent generation
        self.agent = LitAgent()

        # Generate browser fingerprint
        self.fingerprint = self.agent.generate_fingerprint(browser="chrome")

        # Setup headers to mimic browser requests
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'Referer': 'https://claude.online/',
            'Origin': 'https://claude.online',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
        }

        # Initialize curl_cffi Session
        self.session = Session()
        self.session.headers.update(self.headers)
        self.session.proxies = proxies

        self.system_prompt = system_prompt
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = {}
        self.model = model

        self.__available_optimizers = (
            method
            for method in dir(Optimizers)
            if callable(getattr(Optimizers, method)) and not method.startswith("__")
        )

        Conversation.intro = (
            AwesomePrompts().get_act(
                act, raise_not_found=True, default=None, case_insensitive=True
            )
            if act
            else intro or Conversation.intro
        )

        self.conversation = Conversation(
            is_conversation, self.max_tokens_to_sample, filepath, update_file
        )
        self.conversation.history_offset = history_offset

    def _make_request(self, url: str, payload: Optional[Dict] = None, method: str = "POST") -> Dict:
        """
        Make a request to the API with error handling.

        Args:
            url: The URL to request
            payload: Request payload (for POST requests)
            method: HTTP method

        Returns:
            Parsed JSON response

        Raises:
            FailedToGenerateResponseError: If request fails
        """
        try:
            if method == "POST":
                response = self.session.post(
                    url,
                    json=payload,
                    timeout=self.timeout,
                    impersonate="chrome110"
                )
            else:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    impersonate="chrome110"
                )

            response.raise_for_status()

            # Check rate limit headers
            if 'ratelimit-remaining' in response.headers:
                remaining = int(response.headers['ratelimit-remaining'])
                if remaining <= 0:
                    reset_time = int(response.headers.get('ratelimit-reset', 60))
                    raise exceptions.FailedToGenerateResponseError(
                        f"Rate limit exceeded. Resets in {reset_time} seconds."
                    )

            return response.json()

        except CurlError as e:
            raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {str(e)}")
        except Exception as e:
            raise exceptions.FailedToGenerateResponseError(f"Request failed ({type(e).__name__}): {str(e)}")

    def get_remaining_limit(self) -> Dict[str, Union[int, float]]:
        """
        Get the current rate limit status.

        Returns:
            Dict containing limit information:
            - limit: Remaining requests
            - fullLimit: Unknown parameter (possibly daily limit)
        """
        try:
            response = self._make_request(self.limit_url, method="GET")
            return {
                "limit": response.get("limit", 0),
                "fullLimit": response.get("fullLimit", 0)
            }
        except Exception:
            # Return default values if request fails
            return {"limit": 0, "fullLimit": 0}

    def create_message(self, content: str, role: str = "user") -> Dict[str, str]:
        """
        Create a message dictionary.

        Args:
            content: Message content
            role: Message role (user/assistant)

        Returns:
            Message dictionary
        """
        return {
            "content": content,
            "role": role
        }

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator]:
        """
        Send a chat message and get response.

        Args:
            prompt: The message to send
            stream: Whether to stream the response (not supported by this API)
            raw: Whether to return raw response
            optimizer: Optimizer to use for the prompt
            conversationally: Whether to generate the prompt conversationally

        Returns:
            Dict containing response or Generator for streaming
        """
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise Exception(f"Optimizer is not one of {self.__available_optimizers}")

        # Prepare messages (only current message supported by this API)
        messages = [self.create_message(conversation_prompt, "user")]

        payload = {
            "messages": messages
        }

        def for_stream():
            # This API doesn't support streaming, so simulate it
            try:
                response = self._make_request(self.chat_url, payload)

                # Extract message content
                if "message" in response and "content" in response["message"]:
                    content = response["message"]["content"]

                    # Simulate streaming by yielding chunks
                    words = content.split()
                    current_chunk = ""
                    for word in words:
                        current_chunk += word + " "
                        if len(current_chunk) > 50:  # Yield chunks of ~50 characters
                            yield dict(text=current_chunk.strip())
                            current_chunk = ""
                    if current_chunk:
                        yield dict(text=current_chunk.strip())

                    self.last_response = {"text": content}
                    self.conversation.update_chat_history(prompt, content)
                else:
                    raise exceptions.FailedToGenerateResponseError("Unexpected response format")

            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"Chat request failed: {str(e)}")

        def for_non_stream():
            try:
                response = self._make_request(self.chat_url, payload)

                # Extract message content
                if "message" in response and "content" in response["message"]:
                    content = response["message"]["content"]
                    self.last_response = {"text": content}
                    self.conversation.update_chat_history(prompt, content)
                    return self.last_response if not raw else content
                else:
                    raise exceptions.FailedToGenerateResponseError("Unexpected response format")

            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"Chat request failed: {str(e)}")

        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[str, Generator[str, None, None]]:
        """
        Generate a response from Claude Online.

        Args:
            prompt: The prompt to send
            stream: Whether to stream the response
            optimizer: Optimizer to use
            conversationally: Whether to generate conversationally

        Returns:
            Response string or generator for streaming
        """
        def for_stream_chat():
            for response in self.ask(
                prompt, stream=True, raw=False,
                optimizer=optimizer, conversationally=conversationally
            ):
                yield self.get_message(response)

        def for_non_stream_chat():
            response_data = self.ask(
                prompt, stream=False, raw=False,
                optimizer=optimizer, conversationally=conversationally
            )
            return self.get_message(response_data)

        return for_stream_chat() if stream else for_non_stream_chat()

    def get_message(self, response: dict) -> str:
        """
        Extract message from response.

        Args:
            response: Response dictionary

        Returns:
            Message content
        """
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response["text"]


if __name__ == "__main__":
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)

    try:
        ai = ClaudeOnline(timeout=60)
        limits = ai.get_remaining_limit()
        print(f"Rate limits - Remaining: {limits['limit']}, Full limit: {limits['fullLimit']}")

        if limits['limit'] > 0:
            response = ai.chat("Say 'Hello World' in one word", stream=False)
            if response and len(response.strip()) > 0:
                status = "✓"
                clean_text = response.strip().encode('utf-8', errors='ignore').decode('utf-8')
                display_text = clean_text[:50] + "..." if len(clean_text) > 50 else clean_text
            else:
                status = "✗"
                display_text = "Empty response"
            print(f"{'claude-online':<50} {status:<10} {display_text}")
        else:
            print(f"{'claude-online':<50} {'✗':<10} Rate limit exceeded")

    except Exception as e:
        print(f"{'claude-online':<50} {'✗':<10} {str(e)}")
