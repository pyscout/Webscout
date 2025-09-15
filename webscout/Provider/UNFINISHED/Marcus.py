from curl_cffi.requests import Session
from curl_cffi import CurlError
import json
from typing import Union, Any, Dict, Optional, Generator

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream # Import sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions

class Marcus(Provider):
    """
    This class provides methods for interacting with the AskMarcus API.
    Improved to match webscout provider standards.
    """

    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 2048, # Note: max_tokens is not used by this API
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None
    ):
        """Initializes the Marcus API."""
        # Initialize curl_cffi Session
        self.session = Session()
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.api_endpoint = "https://www.askmarcus.app/api/response"
        self.timeout = timeout
        self.last_response = {}
        
        self.headers = {
            'content-type': 'application/json',
            'accept': '*/*',
            'origin': 'https://www.askmarcus.app',
            'referer': 'https://www.askmarcus.app/chat',
        }
        
        # Update curl_cffi session headers and proxies
        self.session.headers.update(self.headers)
        self.session.proxies = proxies # Assign proxies directly

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

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator[Any, None, None]]:
        """Sends a prompt to the AskMarcus API and returns the response."""
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise exceptions.FailedToGenerateResponseError(
                    f"Optimizer is not one of {self.__available_optimizers}"
                )

        data = {"message": conversation_prompt}

        def for_stream():
            streaming_text = "" # Initialize outside try block
            try:
                # Use curl_cffi session post with impersonate
                response = self.session.post(
                    self.api_endpoint,
                    # headers are set on the session
                    json=data,
                    stream=True,
                    timeout=self.timeout,
                    # proxies are set on the session
                    impersonate="chrome110" # Use a common impersonation profile
                )
                response.raise_for_status() # Check for HTTP errors
                
                # Use sanitize_stream to decode bytes and yield text chunks
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None), # Pass byte iterator
                    intro_value=None, # No prefix
                    to_json=False,    # It's plain text
                    yield_raw_on_error=True
                )

                for content_chunk in processed_stream:
                    if content_chunk and isinstance(content_chunk, str):
                        streaming_text += content_chunk # Aggregate text
                        yield {"text": content_chunk} if not raw else content_chunk
                # Update history after stream finishes
                self.last_response = {"text": streaming_text} # Store aggregated text
                self.conversation.update_chat_history(
                    prompt, streaming_text
                )

            except CurlError as e: # Catch CurlError
                raise exceptions.ProviderConnectionError(f"Error connecting to Marcus (CurlError): {str(e)}") from e
            except Exception as e: # Catch other potential exceptions (like HTTPError)
                err_text = getattr(e, 'response', None) and getattr(e.response, 'text', '')
                raise exceptions.ProviderConnectionError(f"Error connecting to Marcus ({type(e).__name__}): {str(e)} - {err_text}") from e

        def for_non_stream():
            try:
                # Use curl_cffi session post with impersonate
                response = self.session.post(
                    self.api_endpoint,
                    # headers are set on the session
                    json=data,
                    timeout=self.timeout,
                    # proxies are set on the session
                    impersonate="chrome110" # Use a common impersonation profile
                )
                response.raise_for_status() # Check for HTTP errors
                
                response_text_raw = response.text # Get raw text

                # Process the text using sanitize_stream (even though it's not streaming)
                processed_stream = sanitize_stream(
                    data=response_text_raw,
                    intro_value=None, # No prefix
                    to_json=False     # It's plain text
                )
                # Aggregate the single result
                full_response = "".join(list(processed_stream))

                self.last_response = {"text": full_response}
                self.conversation.update_chat_history(prompt, full_response)
                # Return dict or raw string
                return full_response if raw else self.last_response

            except CurlError as e: # Catch CurlError
                 raise exceptions.ProviderConnectionError(f"Error connecting to Marcus (CurlError): {str(e)}") from e
            except Exception as e: # Catch other potential exceptions (like HTTPError)
                err_text = getattr(e, 'response', None) and getattr(e.response, 'text', '')
                raise exceptions.ProviderConnectionError(f"Error connecting to Marcus ({type(e).__name__}): {str(e)} - {err_text}") from e


        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[str, Generator[str, None, None]]:
        """Generates a response from the AskMarcus API."""
        response_data = self.ask(
            prompt, stream=False, raw=False, # Always get the full response
            optimizer=optimizer, conversationally=conversationally
        )
        if stream:
            def stream_wrapper():
                yield self.get_message(response_data)
            return stream_wrapper()
        else:
            return self.get_message(response_data)

    def get_message(self, response: Dict[str, Any]) -> str:
        """Extracts the message from the API response."""
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response.get("text", "")

if __name__ == "__main__":
    # Ensure curl_cffi is installed
    from rich import print
    ai = Marcus()
    response = ai.chat("hi", stream=True)
    for chunk in response:
        print(chunk, end="", flush=True)
