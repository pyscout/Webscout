from curl_cffi.requests import Session
from curl_cffi import CurlError
import json
from typing import Dict, Generator, Union

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent


class OpenGPT(Provider):
    """
    A class to interact with the Open-GPT API.
    """
    required_auth = False
    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 600, # Note: max_tokens is not used by this API
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        app_id: str = "clf3yg8730000ih08ndbdi2v4",
    ):
        """Initializes the OpenGPT API client.
        
        Args:
            is_conversation (bool, optional): Whether to maintain conversation history. Defaults to True.
            max_tokens (int, optional): Maximum number of tokens to generate. Defaults to 600.
            timeout (int, optional): Http request timeout. Defaults to 30.
            intro (str, optional): Conversation introductory prompt. Defaults to None.
            filepath (str, optional): Path to file containing conversation history. Defaults to None.
            update_file (bool, optional): Add new prompts and responses to the file. Defaults to True.
            proxies (dict, optional): Http request proxies. Defaults to {}.
            history_offset (int, optional): Limit conversation history to this number of last texts. Defaults to 10250.
            act (str, optional): Awesome prompt key or index. (Used as intro). Defaults to None.
            app_id (str, optional): The OpenGPT application ID. Defaults to "clf3yg8730000ih08ndbdi2v4".
        """
        # Initialize curl_cffi Session
        self.session = Session()
        self.agent = LitAgent() # Keep for potential future use or other headers
        
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = {}
        self.app_id = app_id
        
        # Set up headers (remove User-Agent if using impersonate)
        self.headers = {
            "Content-Type": "application/json",
            # "User-Agent": self.agent.random(), # Removed, handled by impersonate
            "Referer": f"https://open-gpt.app/id/app/{self.app_id}",
            # Add sec-ch-ua headers if needed for impersonation consistency
        }
        
        # Update curl_cffi session headers and proxies
        self.session.headers.update(self.headers)
        self.session.proxies = proxies # Assign proxies directly
        
        # Initialize optimizers
        self.__available_optimizers = (
            method
            for method in dir(Optimizers)
            if callable(getattr(Optimizers, method)) and not method.startswith("__")
        )
        
        # Setup conversation
        Conversation.intro = (
            AwesomePrompts().get_act(
                act, raise_not_found=True, default=None, case_insensitive=True
            ) if act else intro or Conversation.intro
        )
        
        self.conversation = Conversation(
            is_conversation, self.max_tokens_to_sample, filepath, update_file
        )
        self.conversation.history_offset = history_offset

    def ask(
        self,
        prompt: str,
        stream: bool = False, # Note: API does not support streaming natively
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict, Generator]:
        """
        Send a prompt to the OpenGPT API and get a response.
        
        Args:
            prompt: The user input/prompt for the API.
            stream: Whether to stream the response.
            raw: Whether to return the raw API response.
            optimizer: Optimizer to use on the prompt.
            conversationally: Whether to apply the optimizer on the full conversation prompt.
            
        Returns:
            A dictionary or generator with the response.
        """
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise Exception(f"Optimizer is not one of {self.__available_optimizers}")
                
        # Prepare the request body payload
        payload = {
            "userInput": conversation_prompt,
            "id": self.app_id,
            "userKey": ""  # Assuming userKey is meant to be empty as in the original code
        }

        def for_stream():
            try:
                response = self.session.post(
                    "https://open-gpt.app/api/generate",
                    data=json.dumps(payload),
                    timeout=self.timeout,
                    impersonate="chrome110"
                )
                response.raise_for_status()
                response_text = response.text
                buffer = ""
                chunk_size = 32
                for i in range(0, len(response_text), chunk_size):
                    out = response_text[i:i+chunk_size]
                    if out.strip():
                        if raw:
                            yield out
                        else:
                            yield {"text": out}
                self.last_response = {"text": response_text}
                self.conversation.update_chat_history(prompt, response_text)
            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}") from e
            except Exception as e:
                err_text = getattr(e, 'response', None) and getattr(e.response, 'text', '')
                raise exceptions.FailedToGenerateResponseError(f"An unexpected error occurred ({type(e).__name__}): {e} - {err_text}") from e

        def for_non_stream():
            try:
                response = self.session.post(
                    "https://open-gpt.app/api/generate",
                    data=json.dumps(payload),
                    timeout=self.timeout,
                    impersonate="chrome110"
                )
                response.raise_for_status()
                response_text = response.text
                self.last_response = {"text": response_text}
                self.conversation.update_chat_history(prompt, response_text)
                return {"raw": response_text} if raw else {"text": response_text}
            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}") from e
            except Exception as e:
                err_text = getattr(e, 'response', None) and getattr(e.response, 'text', '')
                raise exceptions.FailedToGenerateResponseError(f"An unexpected error occurred ({type(e).__name__}): {e} - {err_text}") from e

        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False, # Keep stream param for interface consistency
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[str, Generator[str, None, None]]:
        """
        Send a prompt to the OpenGPT API and get a text response.
        
        Args:
            prompt: The user input/prompt for the API.
            stream: Whether to stream the response (not supported).
            optimizer: Optimizer to use on the prompt.
            conversationally: Whether to apply the optimizer on the full conversation prompt.
            
        Returns:
            A string with the response text.
        """
        if stream:
            def stream_wrapper():
                for part in self.ask(
                    prompt,
                    stream=True,
                    raw=False,
                    optimizer=optimizer,
                    conversationally=conversationally
                ):
                    yield self.get_message(part) if isinstance(part, dict) else part
            return stream_wrapper()
        else:
            response_data = self.ask(
                prompt,
                stream=False,
                raw=False,
                optimizer=optimizer,
                conversationally=conversationally
            )
            return self.get_message(response_data)

    def get_message(self, response: dict) -> str:
        """
        Extract the message from the response dictionary.
        
        Args:
            response: Response dictionary from the ask method.
            
        Returns:
            The text response as a string.
        """
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response["text"]


if __name__ == "__main__":
    ai = OpenGPT()
    response = ai.chat("write me about humans in points", stream=True)
    for part in response:
        print(part, end="", flush=True)