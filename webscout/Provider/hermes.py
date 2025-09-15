from curl_cffi.requests import Session
from curl_cffi import CurlError
import json
from typing import Union, Any, Dict, Generator, Optional
from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation, sanitize_stream # Import sanitize_stream
from webscout.AIutel import AwesomePrompts
from webscout.AIbase import Provider
from webscout import exceptions
class NousHermes(Provider):
    """
    A class to interact with the Hermes API.
    """

    AVAILABLE_MODELS = ["Hermes-3-Llama-3.1-70B", "Hermes-3-Llama-3.1-8B"]
    required_auth = False
    def __init__(
        self,
        cookies_path: str,
        is_conversation: bool = True,
        max_tokens: int = 8000,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "Hermes-3-Llama-3.1-70B",
        system_prompt: str = "You are a helpful AI assistant.",
        temperature: float = 0.7,
        top_p: float = 0.9,
    ):
        """Initializes the Hermes API client."""
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(
                f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}"
            )

        self.session = Session()
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = {}
        self.model = model
        self.system_prompt = system_prompt
        self.api_endpoint = "https://hermes.nousresearch.com/api/chat"
        self.temperature = temperature
        self.top_p = top_p
        self.cookies_path = cookies_path
        self.cookies_dict = self._load_cookies()
        
        self.headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://hermes.nousresearch.com',
            'referer': 'https://hermes.nousresearch.com/',
        }

        self.__available_optimizers = (
            method
            for method in dir(Optimizers)
            if callable(getattr(Optimizers, method)) and not method.startswith("__")
        )
        self.session.headers.update(self.headers)
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
        # Update curl_cffi session headers and proxies
        self.session.proxies = proxies
        
        # Apply cookies to curl_cffi session
        if self.cookies_dict:
            for name, value in self.cookies_dict.items():
                self.session.cookies.set(name, value, domain="hermes.nousresearch.com")

    def _load_cookies(self) -> Optional[Dict[str, str]]:
        """Load cookies from a JSON file and return them as a dictionary."""
        try:
            with open(self.cookies_path, 'r') as f:
                cookies_data = json.load(f)
            # Convert list of cookie objects to a dictionary
            return {cookie['name']: cookie['value'] for cookie in cookies_data if 'name' in cookie and 'value' in cookie}
        except FileNotFoundError:
            print(f"Warning: Cookies file not found at {self.cookies_path}")
            return None
        except json.JSONDecodeError:
            print(f"Warning: Invalid JSON format in cookies file at {self.cookies_path}")
            return None
        except Exception as e:
            print(f"Warning: Error loading cookies: {e}")
            return None

    @staticmethod
    def _hermes_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        """Extracts content from Hermes stream JSON objects."""
        if isinstance(chunk, dict) and chunk.get('type') == 'llm_response':
            return chunk.get('content')
        return None


    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator[Any, None, None]]:
        """Chat with AI
        Args:
            prompt (str): Prompt to be send.
            stream (bool, optional): Flag for streaming response. Defaults to False.
            raw (bool, optional): Stream back raw response as received. Defaults to False.
            optimizer (str, optional): Prompt optimizer name - `[code, shell_command]`. Defaults to None.
            conversationally (bool, optional): Chat conversationally when using optimizer. Defaults to False.
        Returns:
           dict|AsyncGenerator : ai content
        ```json
        {
           "text" : "How may I assist you today?"
        }
        ```
        """
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

        payload = {
            "messages": [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": conversation_prompt}],
            "model": self.model,
            "max_tokens": self.max_tokens_to_sample,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }
        def for_stream():
            streaming_text = "" # Initialize outside try block
            try:
                response = self.session.post(
                    self.api_endpoint, 
                    json=payload, 
                    stream=True, 
                    timeout=self.timeout,
                    impersonate="chrome110" # Keep impersonate
                )
                response.raise_for_status()

                # Use sanitize_stream
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None), # Pass byte iterator
                    intro_value="data:",
                    to_json=True,     # Stream sends JSON
                    content_extractor=self._hermes_extractor, # Use the specific extractor
                    yield_raw_on_error=False # Skip non-JSON lines or lines where extractor fails
                )

                for content_chunk in processed_stream:
                    # content_chunk is the string extracted by _hermes_extractor
                    if content_chunk and isinstance(content_chunk, str):
                        streaming_text += content_chunk
                        resp = dict(text=content_chunk)
                        yield resp if not raw else content_chunk

                self.last_response = dict(text=streaming_text) # Use streaming_text
                self.conversation.update_chat_history(
                    prompt, streaming_text # Use streaming_text
                )

            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}") from e
            except Exception as e:
                err_text = getattr(e, 'response', None) and getattr(e.response, 'text', '')
                raise exceptions.FailedToGenerateResponseError(f"Failed to generate response ({type(e).__name__}): {e} - {err_text}") from e


        def for_non_stream():
            collected_text = ""
            try:
                for chunk_data in for_stream():
                    if isinstance(chunk_data, dict) and "text" in chunk_data:
                        collected_text += chunk_data["text"]
                    elif raw and isinstance(chunk_data, str):
                         collected_text += chunk_data
            except Exception as e:
                 if not collected_text:
                     raise exceptions.FailedToGenerateResponseError(f"Failed to get non-stream response: {str(e)}") from e

            return collected_text if raw else self.last_response


        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[str, Generator[str, None, None]]:
        """Generate response `str`
        Args:
            prompt (str): Prompt to be send.
            stream (bool, optional): Flag for streaming response. Defaults to False.
            optimizer (str, optional): Prompt optimizer name - `[code, shell_command]`. Defaults to None.
            conversationally (bool, optional): Chat conversationally when using optimizer. Defaults to False.
        Returns:
            str: Response generated
        """

        def for_stream_chat():
            gen = self.ask(
                prompt, stream=True, raw=False,
                optimizer=optimizer, conversationally=conversationally
            )
            for response_dict in gen:
                yield self.get_message(response_dict)

        def for_non_stream_chat():
            response_data = self.ask(
                prompt,
                stream=False,
                raw=False,
                optimizer=optimizer,
                conversationally=conversationally,
            )
            return self.get_message(response_data)

        return for_stream_chat() if stream else for_non_stream_chat()

    def get_message(self, response: dict) -> str:
        """Retrieves message only from response

        Args:
            response (dict): Response generated by `self.ask`

        Returns:
            str: Message extracted
        """
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response["text"]


if __name__ == "__main__":
    from rich import print
    ai = NousHermes(cookies_path="cookies.json")
    response = ai.chat(input(">>> "), stream=True)
    for chunk in response:
        print(chunk, end="", flush=True)