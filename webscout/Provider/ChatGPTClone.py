import time
import uuid
# import cloudscraper
from curl_cffi.requests import Session, RequestsError
import json
import re
from typing import Any, Dict, Optional, Generator, Union
from dataclasses import dataclass, asdict
from datetime import date

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream # Import sanitize_stream
from webscout.AIbase import Provider
from ..search import DuckDuckGoSearch
from .. import exceptions
# from webscout.litagent import LitAgent

class ChatGPTClone(Provider):
    """
    ChatGPTClone is a provider class for interacting with the ChatGPT Clone API.
    Supports streaming responses.
    """
    required_auth = False
    url = "https://chatgpt-clone-ten-nu.vercel.app"
    AVAILABLE_MODELS = ["gpt-4", "gpt-3.5-turbo"]
    SUPPORTED_IMPERSONATION = [
        "chrome110", "chrome116", "chrome119", "chrome120",
        "chrome99_android", "edge99", "edge101",
        "safari15_3", "safari15_6_1", "safari17_0", "safari17_2_1"
    ]
    
    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 2000,
        timeout: int = 60,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "gpt-4",
        temperature: float = 0.6,
        top_p: float = 0.7,
        impersonate: str = "chrome120",
        system_prompt: str = "You are a helpful assistant."
    ):
        """Initialize the ChatGPT Clone client using curl_cffi."""
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")
        if impersonate not in self.SUPPORTED_IMPERSONATION:
            raise ValueError(f"Invalid impersonate browser: {impersonate}. Choose from: {self.SUPPORTED_IMPERSONATION}")
            
        self.model = model
        self.impersonate = impersonate
        self.session = Session(impersonate=self.impersonate, proxies=proxies, timeout=timeout)
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = {}
        self.temperature = temperature
        self.top_p = top_p
        self.system_prompt = system_prompt

        self.headers = {
            "Content-Type": "application/json",
            "Origin": self.url,
            "Referer": f"{self.url}/",
            "DNT": "1",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "TE": "trailers"
        }
        self.session.headers.update(self.headers)

        self.__available_optimizers = (
            method
            for method in dir(Optimizers)
            if callable(getattr(Optimizers, method))
            and not method.startswith("__")
        )
        Conversation.intro = (
            AwesomePrompts().get_act(act, raise_not_found=True, default=None, case_insensitive=True)
            if act
            else intro or Conversation.intro
        )
        self.conversation = Conversation(
            is_conversation, self.max_tokens_to_sample, filepath, update_file
        )
        self.conversation.history_offset = history_offset

    def refresh_identity(self, impersonate: str = None):
        """Re-initializes the curl_cffi session with a new impersonation target."""
        impersonate = impersonate or self.impersonate
        if impersonate not in self.SUPPORTED_IMPERSONATION:
            raise ValueError(f"Invalid impersonate browser: {impersonate}. Choose from: {self.SUPPORTED_IMPERSONATION}")
        self.impersonate = impersonate
        self.session = Session(
            impersonate=self.impersonate,
            proxies=self.session.proxies,
            timeout=self.timeout
        )
        self.session.headers.update(self.headers)
        return self.impersonate

    @staticmethod
    def _chatgptclone_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        """Extracts content from the ChatGPTClone stream format '0:"..."'."""
        if isinstance(chunk, str):
            match = re.search(r'0:"((?:[^\\"]|\\.)*)"', chunk) # Use the existing regex
            if match:
                content = match.group(1)
                # Decode JSON string escapes and then unicode escapes
                decoded_content = json.loads(f'"{content}"').encode().decode('unicode_escape')
                return decoded_content
        return None
    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator]:
        """Send a message to the ChatGPT Clone API using curl_cffi"""
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
            "model": self.model
        }

        api_url = f"{self.url}/api/chat"

        def _make_request(attempt_refresh=True):
            try:
                response = self.session.post(api_url, json=payload, stream=True)
                response.raise_for_status()
                return response
            except RequestsError as e:
                if attempt_refresh and e.response and e.response.status_code in [403, 429]:
                    self.refresh_identity()
                    return _make_request(attempt_refresh=False)
                else:
                    err_msg = f"Request failed: {e}"
                    if e.response is not None:
                        err_msg = f"Failed to generate response - ({e.response.status_code}, {e.response.reason}) - {e.response.text}"
                    raise exceptions.FailedToGenerateResponseError(err_msg) from e
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"An unexpected error occurred: {e}") from e

        def for_stream():
            response = _make_request()
            streaming_text = "" # Initialize outside try block
            try:
                # Use sanitize_stream
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None), # Pass byte iterator
                    intro_value=None, # No simple prefix
                    to_json=False,    # Content is text after extraction
                    content_extractor=self._chatgptclone_extractor, # Use the specific extractor
                    yield_raw_on_error=True # Yield even if extractor fails (might get metadata lines)
                )

                for content_chunk in processed_stream:
                    # content_chunk is the string extracted by _chatgptclone_extractor
                    if content_chunk and isinstance(content_chunk, str):
                        streaming_text += content_chunk
                        yield content_chunk if raw else dict(text=content_chunk)

            except RequestsError as e:
                raise exceptions.FailedToGenerateResponseError(f"Stream interrupted by request error: {e}") from e
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"Error processing stream: {e}") from e
            finally:
                # Update history after stream finishes or fails
                self.last_response.update(dict(text=streaming_text))
                self.conversation.update_chat_history(prompt, streaming_text)
                response.close()

        def for_non_stream():
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
    ) -> Union[str, Generator[str, None, None]]:
        """Generate a response to a prompt"""
        def for_stream():
            for response in self.ask(
                prompt, True, optimizer=optimizer, conversationally=conversationally
            ):
                yield self.get_message(response)
        def for_non_stream():
            return self.get_message(
                self.ask(
                    prompt, False, optimizer=optimizer, conversationally=conversationally
                )
            )
        return for_stream() if stream else for_non_stream()

    def get_message(self, response: dict) -> str:
        """Extract message text from response"""
        assert isinstance(response, dict)
        if not isinstance(response, dict) or "text" not in response:
            return str(response)
        # Extractor handles formatting
        formatted_text = response.get("text", "")
        return formatted_text

if __name__ == "__main__":
    from rich import print
    ai = ChatGPTClone(timeout=120, impersonate="chrome120")
    response = ai.chat("write a poem about AI", stream=True)
    for chunk in response:
        print(chunk, end="", flush=True)