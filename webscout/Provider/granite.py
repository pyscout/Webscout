from curl_cffi.requests import Session
from curl_cffi import CurlError
import json
from typing import Optional, Union, Any, Dict, Generator

from webscout.AIutel import Optimizers, Conversation, AwesomePrompts, sanitize_stream # Import sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent as Lit

class IBMGranite(Provider):
    """
    A class to interact with the IBM Granite API (accessed via d18n68ssusgr7r.cloudfront.net)
    using Lit agent for the user agent.
    """
    required_auth = False
    AVAILABLE_MODELS = ["granite-3-8b-instruct", "granite-3-2-8b-instruct", "granite-3-3-8b-instruct"]

    def __init__(
        self,
        api_key: str = None,
        is_conversation: bool = True,
        max_tokens: int = 600, # Note: max_tokens is not used by this API
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "granite-3-3-8b-instruct",
        system_prompt: str = "You are a helpful AI assistant.",
        thinking: bool = False,
    ):
        """Initializes the IBMGranite API client using Lit agent for the user agent."""
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        # Auto-generate API key if not provided or empty
        if not api_key:
            api_key = self.generate_api_key()

        # Initialize curl_cffi Session
        self.session = Session()
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.api_endpoint = "https://d18n68ssusgr7r.cloudfront.net/v1/chat/completions"
        self.stream_chunk_size = 64
        self.timeout = timeout
        self.last_response = {}
        self.model = model
        self.system_prompt = system_prompt
        self.thinking = thinking

        # Use Lit agent (keep if needed for other headers or logic)
        self.headers = {
            "authority": "d18n68ssusgr7r.cloudfront.net", # Keep authority
            "accept": "application/json,application/jsonl", # Keep accept
            "content-type": "application/json",
            "origin": "https://www.ibm.com", # Keep origin
            "referer": "https://www.ibm.com/", # Keep referer
            "User-Agent": Lit().random(),
        }
        self.headers["Authorization"] = f"Bearer {api_key}"
        
        # Update curl_cffi session headers and proxies
        self.session.headers.update(self.headers)
        self.session.proxies = proxies # Assign proxies directly

        self.__available_optimizers = (
            method for method in dir(Optimizers)
            if callable(getattr(Optimizers, method)) and not method.startswith("__")
        )

        Conversation.intro = (
            AwesomePrompts().get_act(
                act, raise_not_found=True, default=None, case_insensitive=True
            )
            if act
            else intro or Conversation.intro
        )
        self.conversation = Conversation(is_conversation, self.max_tokens_to_sample, filepath, update_file)
        self.conversation.history_offset = history_offset

    @staticmethod
    def _granite_extractor(chunk: Union[str, Dict[str, Any], list]) -> Optional[str]:
        """Extracts content from IBM Granite stream JSON lists [6, "text"] or [3, "text"]."""
        # Accept both [3, str] and [6, str] as content chunks
        if isinstance(chunk, list) and len(chunk) == 2 and isinstance(chunk[1], str):
            if chunk[0] in (3, 6):
                return chunk[1]
        return None

    @staticmethod
    def generate_api_key() -> str:
        """
        Auto-generate an API key (sessionId) by making a GET request to the Granite auth endpoint.
        Returns:
            str: The sessionId to be used as the API key.
        Raises:
            Exception: If the sessionId cannot be retrieved.
        """
        session = Session()
        headers = {
            "User-Agent": Lit().random(),
            "Origin": "https://www.ibm.com",
            "Referer": "https://d18n68ssusgr7r.cloudfront.net/",
            "Accept": "application/json,application/jsonl",
        }
        session.headers.update(headers)
        url = "https://d18n68ssusgr7r.cloudfront.net/v1/auth"
        resp = session.get(url, timeout=15, impersonate="chrome110")
        if resp.status_code != 200:
            raise Exception(f"Failed to get Granite API key: {resp.status_code} - {resp.text}")
        try:
            data = resp.json()
            session_id = data.get("sessionId")
            if not session_id:
                raise Exception(f"No sessionId in Granite auth response: {data}")
            return session_id
        except Exception as e:
            raise Exception(f"Failed to parse Granite auth response: {e}")

    def ask(
        self,
        prompt: str,
        stream: bool = False, # API supports streaming
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator[Any, None, None]]:
        """Chat with AI
        Args:
            prompt (str): Prompt to be sent.
            stream (bool, optional): Flag for streaming response. Defaults to False.
            raw (bool, optional): Stream back raw response as received. Defaults to False.
            optimizer (str, optional): Prompt optimizer name - `[code, shell_command]`. Defaults to None.
            conversationally (bool, optional): Chat conversationally when using optimizer. Defaults to False.
        Returns:
            Union[Dict, Generator[Dict, None, None]]: Response generated
        """
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise Exception(f"Optimizer is not one of {self.__available_optimizers}")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": conversation_prompt},
            ],
        }
        if self.thinking:
            payload["thinking"] = True

        def for_stream():
            streaming_text = ""
            try:
                response = self.session.post(
                    self.api_endpoint, 
                    json=payload, 
                    stream=True, 
                    timeout=self.timeout,
                    impersonate="chrome110"
                )
                response.raise_for_status()
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None),
                    intro_value=None,
                    to_json=True,
                    content_extractor=self._granite_extractor,
                    yield_raw_on_error=False,
                    raw=raw
                )
                for content_chunk in processed_stream:
                    if raw:
                        if content_chunk and isinstance(content_chunk, str):
                            streaming_text += content_chunk
                        yield content_chunk
                    else:
                        if content_chunk and isinstance(content_chunk, str):
                            streaming_text += content_chunk
                            resp = dict(text=content_chunk)
                            yield resp
                self.last_response = dict(text=streaming_text)
                self.conversation.update_chat_history(prompt, streaming_text)
            except CurlError as e:
                raise exceptions.ProviderConnectionError(f"Request failed (CurlError): {e}") from e
            except json.JSONDecodeError as e:
                raise exceptions.InvalidResponseError(f"Failed to decode JSON response: {e}") from e
            except Exception as e:
                err_text = getattr(e, 'response', None) and getattr(e.response, 'text', '')
                ex_type = exceptions.FailedToGenerateResponseError if not isinstance(e, exceptions.ProviderConnectionError) else type(e)
                raise ex_type(f"An unexpected error occurred ({type(e).__name__}): {e} - {err_text}") from e

        def for_non_stream():
            full_text = ""
            try:
                for chunk_data in for_stream():
                    if raw:
                        if isinstance(chunk_data, str):
                            full_text += chunk_data
                    else:
                        if isinstance(chunk_data, dict) and "text" in chunk_data:
                            full_text += chunk_data["text"]
            except Exception as e:
                if not full_text:
                    raise exceptions.FailedToGenerateResponseError(f"Failed to get non-stream response: {str(e)}") from e
            return full_text if raw else self.last_response

        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        raw: bool = False,
    ) -> Union[str, Generator[str, None, None]]:
        """Generate response as a string using chat method"""
        def for_stream_chat():
            gen = self.ask(
                prompt, stream=True, raw=raw,
                optimizer=optimizer, conversationally=conversationally
            )
            for response in gen:
                if raw:
                    yield response
                else:
                    yield self.get_message(response)
        def for_non_stream_chat():
            response_data = self.ask(
                prompt, stream=False, raw=raw,
                optimizer=optimizer, conversationally=conversationally
            )
            if raw:
                return response_data if isinstance(response_data, str) else str(response_data)
            return self.get_message(response_data)
        return for_stream_chat() if stream else for_non_stream_chat()

    def get_message(self, response: dict) -> str:
        """Retrieves message only from response"""
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response["text"]

if __name__ == "__main__":
    # Ensure curl_cffi is installed
    from rich import print
    # Example usage: Initialize without logging.
    ai = IBMGranite(
        thinking=True,
    )
    response = ai.chat("How many r in strawberry", stream=True, raw=False)
    for chunk in response:
        print(chunk, end="", flush=True)  # Print each chunk without newline
