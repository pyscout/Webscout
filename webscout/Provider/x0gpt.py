from typing import Generator, Optional, Union, Any, Dict
from uuid import uuid4
from curl_cffi import CurlError
from curl_cffi.requests import Session
import re

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream # Import sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent
# Import HTTPVersion enum
from curl_cffi.const import CurlHttpVersion

class X0GPT(Provider):
    """
    A class to interact with the x0-gpt.devwtf.in API.

    Attributes:
        system_prompt (str): The system prompt to define the assistant's role.

    Examples:
        >>> from webscout.Provider.x0gpt import X0GPT
        >>> ai = X0GPT()
        >>> response = ai.chat("What's the weather today?")
        >>> print(response)
        'The weather today is sunny with a high of 75°F.'
    """
    required_auth = False
    AVAILABLE_MODELS = ["UNKNOWN"]

    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 600,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        system_prompt: str = "You are a helpful assistant.",
        model: str = "UNKNOWN"
    ):
        """
        Initializes the X0GPT API with given parameters.

        Args:
            is_conversation (bool): Whether the provider is in conversation mode.
            max_tokens (int): Maximum number of tokens to sample.
            timeout (int): Timeout for API requests.
            intro (str): Introduction message for the conversation.
            filepath (str): Filepath for storing conversation history.
            update_file (bool): Whether to update the conversation history file.
            proxies (dict): Proxies for the API requests.
            history_offset (int): Offset for conversation history.
            act (str): Act for the conversation.
            system_prompt (str): The system prompt to define the assistant's role.

        Examples:
            >>> ai = X0GPT(system_prompt="You are a friendly assistant.")
            >>> print(ai.system_prompt)
            'You are a friendly assistant.'
        """
        # Initialize curl_cffi Session instead of requests.Session
        self.session = Session() 
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.api_endpoint = "https://x0-gpt.devwtf.in/api/stream/reply"
        self.timeout = timeout
        self.last_response = {}
        self.system_prompt = system_prompt

        # Initialize LitAgent for user agent generation
        self.agent = LitAgent()

        self.headers = {
            "authority": "x0-gpt.devwtf.in",
            "method": "POST",
            "path": "/api/stream/reply",
            "scheme": "https",
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd", # Keep zstd for now
            "accept-language": "en-US,en;q=0.9,en-IN;q=0.8",
            # "content-length": "114", # Let curl_cffi handle content-length
            "content-type": "application/json",
            "dnt": "1",
            "origin": "https://x0-gpt.devwtf.in",
            # "priority": "u=1, i", # Remove priority header
            "referer": "https://x0-gpt.devwtf.in/chat",
            "sec-ch-ua": '"Not)A;Brand";v="99", "Microsoft Edge";v="127", "Chromium";v="127"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "user-agent": self.agent.random()
        }

        self.__available_optimizers = (
            method
            for method in dir(Optimizers)
            if callable(getattr(Optimizers, method)) and not method.startswith("__")
        )
        # Update curl_cffi session headers and proxies
        self.session.headers.update(self.headers)
        self.session.proxies = proxies

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

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator]:
        """
        Sends a prompt to the x0-gpt.devwtf.in API and returns the response.

        Args:
            prompt (str): The prompt to send to the API.
            stream (bool): Whether to stream the response.
            raw (bool): Whether to return the raw response.
            optimizer (str): Optimizer to use for the prompt.
            conversationally (bool): Whether to generate the prompt conversationally.

        Returns:
            Dict[str, Any]: The API response.

        Examples:
            >>> ai = X0GPT()
            >>> response = ai.ask("Tell me a joke!")
            >>> print(response)
            {'text': 'Why did the scarecrow win an award? Because he was outstanding in his field!'}
        """
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise Exception(
                    f"Optimizer is not one of {self.__available_optimizers}"
                )

        payload = {
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": conversation_prompt}
            ],
            "chatId": uuid4().hex,
            "namespace": None
        }

        def for_stream():
            try:
                # Use curl_cffi session post with updated impersonate and http_version
                response = self.session.post(
                    self.api_endpoint,
                    headers=self.headers,
                    json=payload,
                    stream=True,
                    timeout=self.timeout,
                    impersonate="chrome120", # Try a different impersonation profile
                    http_version=CurlHttpVersion.V1_1 # Force HTTP/1.1
                )
                if not response.ok:
                    raise exceptions.FailedToGenerateResponseError(
                        f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                    )
                
                streaming_response = ""
                # Use sanitize_stream with regex-based extraction and filtering
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None), # Pass byte iterator
                    intro_value=None, # No simple prefix to remove here
                    to_json=False,    # Content is not JSON
                    # Use regex to extract content from x0gpt format '0:"..."'
                    extract_regexes=[r'0:"(.*?)"'],
                    # Skip empty chunks, connection status messages, and control characters
                    skip_regexes=[
                        r'^\s*$',                    # Empty lines
                        r'data:\s*\[DONE\]',         # Stream end markers
                        r'event:\s*',                # SSE event headers
                        r'^\d+:\s*$',                # Standalone numbers
                        r'^:\s*$',                   # Colon-only lines
                        r'^\s*[\x00-\x1f]+\s*$'     # Control characters
                    ],
                    raw=raw
                )

                for content_chunk in processed_stream:
                    # Always yield as string, even in raw mode
                    if isinstance(content_chunk, bytes):
                        content_chunk = content_chunk.decode('utf-8', errors='ignore')
                    
                    if raw:
                        yield content_chunk
                    else:
                        if content_chunk and isinstance(content_chunk, str):
                            # Handle unicode escapes and clean up the content
                            try:
                                # Decode unicode escapes like \u00e9
                                clean_content = content_chunk.encode().decode('unicode_escape')
                                # Handle escaped backslashes and quotes
                                clean_content = clean_content.replace('\\\\', '\\').replace('\\"', '"')
                                streaming_response += clean_content
                                yield dict(text=clean_content)
                            except (UnicodeDecodeError, UnicodeEncodeError):
                                # Fallback to original content if unicode processing fails
                                streaming_response += content_chunk
                                yield dict(text=content_chunk)

                self.last_response.update(dict(text=streaming_response))
                self.conversation.update_chat_history(
                    prompt, self.get_message(self.last_response)
                )
            except CurlError as e: # Catch CurlError
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}")
            except Exception as e: # Catch other potential exceptions
                # Include the original exception type in the message for clarity
                raise exceptions.FailedToGenerateResponseError(f"An unexpected error occurred ({type(e).__name__}): {e}")

        def for_non_stream():
            # This function implicitly uses the updated for_stream
            if stream:
                return for_stream()
            for _ in for_stream():
                pass
            return self.last_response

        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        raw: bool = False,  # Added raw parameter
    ) -> Union[str, Generator[str, None, None]]:
        """
        Generates a response from the X0GPT API.

        Args:
            prompt (str): The prompt to send to the API.
            stream (bool): Whether to stream the response.
            optimizer (str): Optimizer to use for the prompt.
            conversationally (bool): Whether to generate the prompt conversationally.
            raw (bool): Whether to return raw response chunks.

        Returns:
            str: The API response.

        Examples:
            >>> ai = X0GPT()
            >>> response = ai.chat("What's the weather today?")
            >>> print(response)
            'The weather today is sunny with a high of 75°F.'
        """

        def for_stream():
            for response in self.ask(
                prompt, True, raw=raw, optimizer=optimizer, conversationally=conversationally
            ):
                if raw:
                    yield response
                else:
                    yield self.get_message(response)

        def for_non_stream():
            result = self.ask(
                prompt,
                False,
                raw=raw,
                optimizer=optimizer,
                conversationally=conversationally,
            )
            if raw:
                return result
            else:
                return self.get_message(result)

        return for_stream() if stream else for_non_stream()

    def get_message(self, response: dict) -> str:
        """
        Extracts the message from the API response.

        Args:
            response (dict): The API response.

        Returns:
            str: The message content.

        Examples:
            >>> ai = X0GPT()
            >>> response = ai.ask("Tell me a joke!")
            >>> message = ai.get_message(response)
            >>> print(message)
            'Why did the scarecrow win an award? Because he was outstanding in his field!'
        """
        assert isinstance(response, dict), "Response should be of dict data-type only"
        # Ensure text exists before processing
        text = response.get("text", "")
        # Text is now cleaned by the regex-based sanitize_stream processing
        return text

if __name__ == "__main__":
    from rich import print
    ai = X0GPT(timeout=5000)
    response = ai.chat("write a poem about AI", stream=True, raw=False)
    for chunk in response:
        print(chunk, end="", flush=True)