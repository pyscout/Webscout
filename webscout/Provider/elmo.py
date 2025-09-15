from curl_cffi.requests import Session
from curl_cffi import CurlError
import json
from typing import Optional, Union, Any, Dict, Generator
from webscout import exceptions
from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation, sanitize_stream # Import sanitize_stream
from webscout.AIutel import AwesomePrompts
from webscout.AIbase import Provider
from webscout.litagent import LitAgent
import re # Import re for the extractor


class Elmo(Provider):
    """
    A class to interact with the Elmo.chat API.
    """
    required_auth = False
    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 600,  # Note: max_tokens is not used by this API
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        system_prompt: str = "You are a helpful AI assistant. Provide clear, concise, and well-structured information. Organize your responses into paragraphs for better readability.",
    ) -> None:
        """Instantiates Elmo

        Args:
            is_conversation (bool, optional): Flag for chatting conversationally. Defaults to True.
            max_tokens (int, optional): Maximum number of tokens to be generated upon completion. Defaults to 600.
            timeout (int, optional): Http request timeout. Defaults to 30.
            intro (str, optional): Conversation introductory prompt. Defaults to None.
            filepath (str, optional): Path to file containing conversation history. Defaults to None.
            update_file (bool, optional): Add new prompts and responses to the file. Defaults to True.
            proxies (dict, optional): Http request proxies. Defaults to {}.
            history_offset (int, optional): Limit conversation history to this number of last texts. Defaults to 10250.
            act (str|int, optional): Awesome prompt key or index. (Used as intro). Defaults to None.
            system_prompt (str, optional): System prompt for Elmo. Defaults to the provided string.
        """
        # Initialize curl_cffi Session
        self.session = Session()
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.api_endpoint = "https://www.elmo.chat/api/v1/prompt"
        self.stream_chunk_size = 64
        self.timeout = timeout
        self.last_response = {}
        self.system_prompt = system_prompt
        self.headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9,en-IN;q=0.8",
            "content-type": "text/plain;charset=UTF-8",
            "dnt": "1",
            "origin": "chrome-extension://ipnlcfhfdicbfbchfoihipknbaeenenm",
            "priority": "u=1, i",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
        }

        self.__available_optimizers = (
            method
            for method in dir(Optimizers)
            if callable(getattr(Optimizers, method)) and not method.startswith("__")
        )
        # Update curl_cffi session headers and proxies
        self.session.headers.update(self.headers)
        self.session.proxies = proxies  # Assign proxies directly

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

    @staticmethod
    def _elmo_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        """Extracts content from the Elmo stream format '0:"..."'."""
        if isinstance(chunk, str):
            match = re.search(r'0:"(.*?)"(?=,|$)', chunk) # Look for 0:"...", possibly followed by comma or end of string
            if match:
                # Decode potential unicode escapes like \u00e9 and handle escaped quotes/backslashes
                content = match.group(1).encode().decode('unicode_escape')
                return content.replace('\\\\', '\\').replace('\\"', '"')
        return None

    def ask(
        self,
        prompt: str,
        stream: bool = False,  # API supports streaming
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator[Any, None, None]]:  # Corrected return type hint
        """Chat with AI

        Args:
            prompt (str): Prompt to be send.
            stream (bool, optional): Flag for streaming response. Defaults to False.
            raw (bool, optional): Stream back raw response as received. Defaults to False.
            optimizer (str, optional): Prompt optimizer name - `[code, shell_command]`. Defaults to None.
            conversationally (bool, optional): Chat conversationally when using optimizer. Defaults to False.
        Returns:
           dict : {}
        ```json
        {
           "text" : "How may I assist you today?"
        }
        ```json
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
            "metadata": {
                "system": {"language": "en-US"},
                "website": {
                    "url": "chrome-extension://ipnlcfhfdicbfbchfoihipknbaeenenm/options.html",
                    "origin": "chrome-extension://ipnlcfhfdicbfbchfoihipknbaeenenm",
                    "title": "Elmo Chat - Your AI Web Copilot",
                    "xpathIndexLength": 0,
                    "favicons": [],
                    "language": "en",
                    "content": "",
                    "type": "html",
                    "selection": "",
                    "hash": "d41d8cd98f00b204e9800998ecf8427e",
                },
            },
            "regenerate": True,
            "conversation": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": conversation_prompt},
            ],
            "enableCache": False,
        }

        def for_stream():
            streaming_text = "" # Initialize outside try block
            try:
                # Use curl_cffi session post with impersonate
                # Note: The API expects 'text/plain' but we send JSON.
                # If this fails, try sending json.dumps(payload) as data with 'Content-Type': 'application/json'
                response = self.session.post(
                    self.api_endpoint,
                    # headers are set on the session, but content-type might need override if sending JSON
                    json=payload,  # Sending as JSON
                    stream=True,
                    timeout=self.timeout,
                    impersonate="chrome110"  # Use a common impersonation profile
                )
                response.raise_for_status()  # Check for HTTP errors

                # Use sanitize_stream
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None), # Pass byte iterator
                    intro_value=None, # No simple prefix
                    to_json=False,    # Content is text after extraction
                    content_extractor=self._elmo_extractor, # Use the specific extractor
                    yield_raw_on_error=True
                )

                for content_chunk in processed_stream:
                    if content_chunk and isinstance(content_chunk, str):
                        streaming_text += content_chunk
                        resp = dict(text=content_chunk)
                        yield resp if not raw else content_chunk

            except CurlError as e:  # Catch CurlError
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}") from e
            except Exception as e:  # Catch other potential exceptions (like HTTPError)
                err_text = getattr(e, 'response', None) and getattr(e.response, 'text', '')
                raise exceptions.FailedToGenerateResponseError(f"Failed to generate response ({type(e).__name__}): {e} - {err_text}") from e
            finally:
                # Update history after stream finishes
                self.last_response = dict(text=streaming_text)
                self.conversation.update_chat_history(
                    prompt, streaming_text
                )

        def for_non_stream():
            # Aggregate the stream using the updated for_stream logic
            collected_text = ""
            try:
                # Ensure raw=False so for_stream yields dicts
                for chunk_data in for_stream():
                    if isinstance(chunk_data, dict) and "text" in chunk_data:
                        collected_text += chunk_data["text"]
                    # Handle raw string case if raw=True was passed
                    elif raw and isinstance(chunk_data, str):
                         collected_text += chunk_data
            except Exception as e:
                 # If aggregation fails but some text was received, use it. Otherwise, re-raise.
                 if not collected_text:
                     raise exceptions.FailedToGenerateResponseError(f"Failed to get non-stream response: {str(e)}") from e

            # Update last_response and history *after* aggregation for non-stream
            self.last_response = {"text": collected_text}
            self.conversation.update_chat_history(prompt, collected_text)
            # Return the final aggregated response dict or raw string
            return collected_text if raw else self.last_response

        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[str, Generator[str, None, None]]:  # Corrected return type hint
        """Generate response `str`
        Args:
            prompt (str): Prompt to be send.
            stream (bool, optional): Flag for streaming response. Defaults to False.
            optimizer (str, optional): Prompt optimizer name - `[code, shell_command]`. Defaults to None.
            conversationally (bool, optional): Chat conversationally when using optimizer. Defaults to False.
        Returns:
            str: Response generated
        """

        def for_stream_chat():  # Renamed inner function
            # ask() yields dicts or strings when streaming
            gen = self.ask(
                prompt, stream=True, raw=False,  # Ensure ask yields dicts
                optimizer=optimizer, conversationally=conversationally
            )
            for response_dict in gen:
                yield self.get_message(response_dict)  # get_message expects dict

        def for_non_stream_chat():  # Renamed inner function
            # ask() returns dict or str when not streaming
            response_data = self.ask(
                prompt,
                stream=False,
                raw=False,  # Ensure ask returns dict
                optimizer=optimizer,
                conversationally=conversationally,
            )
            return self.get_message(response_data)  # get_message expects dict

        return for_stream_chat() if stream else for_non_stream_chat()  # Use renamed functions

    def get_message(self, response: dict) -> str:
        """Retrieves message only from response

        Args:
            response (dict): Response generated by `self.ask`

        Returns:
            str: Message extracted
        """
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response.get("text", "") # Use .get for safety


if __name__ == "__main__":
    # Ensure curl_cffi is installed
    from rich import print
    ai = Elmo()
    response = ai.chat("write a poem about AI", stream=True)
    for chunk in response:
        print(chunk, end="", flush=True)