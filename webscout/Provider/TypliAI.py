import re
import json
import random
import string
from typing import Optional, Union, Any, Dict, Generator
from curl_cffi import CurlError
from curl_cffi.requests import Session
# from curl_cffi.const import CurlHttpVersion # Not strictly needed if using default
from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent


def generate_random_id(length=16):
    """Generates a random alphanumeric string."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for i in range(length))

class TypliAI(Provider):
    """
    A class to interact with the Typli.ai API.

    Attributes:
        system_prompt (str): The system prompt to define the assistant's role.

    Examples:
        >>> from lol import TypliAI
        >>> ai = TypliAI()
        >>> response = ai.chat("What's the weather today?")
        >>> print(response)
        'I don't have access to real-time weather information...'
    """
    required_auth = False
    AVAILABLE_MODELS = ["gpt-4o-mini"]

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
        model: str = "gpt-4o-mini"
    ):
        """
        Initializes the TypliAI API with given parameters.

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
            model (str): The model to use for generation.
        """
        # Initialize curl_cffi Session instead of requests.Session
        self.session = Session()
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.api_endpoint = "https://typli.ai/api/generators/chat"
        self.timeout = timeout
        self.last_response = {}
        self.system_prompt = system_prompt
        self.model = model

        # Initialize LitAgent for user agent generation if available

        self.agent = LitAgent()
        # user_agent = self.agent.random() # Let impersonate handle the user-agent
        self.headers = {
            'accept': '*/*', # Changed from '/' in example, but '*' is safer
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://typli.ai',
            'referer': 'https://typli.ai/free-no-sign-up-chatgpt',
            # Let impersonate handle sec-ch-ua headers
            # 'sec-ch-ua': '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            # 'sec-ch-ua-mobile': '?0',
            # 'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'dnt': '1',
            # 'user-agent': user_agent, # Let impersonate handle this
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
    ) -> Union[Dict[str, Any], Generator[Dict[str, Any], None, None]]:
        """
        Sends a prompt to the Typli.ai API and returns the response.

        Args:
            prompt (str): The prompt to send to the API.
            stream (bool): Whether to stream the response.
            raw (bool): Whether to return the raw response.
            optimizer (str): Optimizer to use for the prompt.
            conversationally (bool): Whether to generate the prompt conversationally.

        Returns:
            Union[Dict[str, Any], Generator[Dict[str, Any], None, None]]: The API response.
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
            "id": generate_random_id(),
            "messages": [
                { # Add the system role message
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": conversation_prompt,
                    "parts": [
                        {
                            "type": "text",
                            "text": conversation_prompt
                        }
                    ]
                }
            ],
            "slug": "free-no-sign-up-chatgpt"
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
                    impersonate="chrome120",  # Switch to a more common profile
                    # http_version=CurlHttpVersion.V1_1 # Usually not needed
                )
                if not response.ok:
                    error_msg = f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                    raise exceptions.FailedToGenerateResponseError(error_msg)

                streaming_response = ""
                # Use sanitize_stream with extract_regexes
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None), # Pass byte iterator
                    intro_value=None, # No simple prefix like 'data:'
                    to_json=False,    # Content is extracted as string, not JSON object per line
                    extract_regexes=[r'0:"(.*?)"'], # Extract content from '0:"..."' format
                    skip_regexes=[
                        r'^f:\{.*\}$',  # Skip metadata lines starting with f:{
                        r'^e:\{.*\}$',  # Skip metadata lines starting with e:{
                        r'^d:\{.*\}$',  # Skip metadata lines starting with d:{
                        r'^8:\[.*\]$',  # Skip metadata lines starting with 8:[
                        r'^2:\[.*\]$',  # Skip metadata lines starting with 2:[
                        r'^\s*$'        # Skip empty lines
                    ],
                    raw=raw  # Pass the raw parameter to sanitize_stream
                )

                for content_chunk in processed_stream:
                    if content_chunk and isinstance(content_chunk, str): # Extractor returns string
                        streaming_response += content_chunk
                        yield content_chunk if raw else dict(text=content_chunk)

                self.last_response.update(dict(text=streaming_response))

                self.conversation.update_chat_history(
                    prompt, self.get_message(self.last_response)
                )

            except CurlError as e:  # Catch CurlError
                error_msg = f"Request failed (CurlError): {e}"
                raise exceptions.FailedToGenerateResponseError(error_msg)

            except Exception as e:  # Catch other potential exceptions
                # Include the original exception type in the message for clarity
                error_msg = f"An unexpected error occurred ({type(e).__name__}): {e}"
                raise exceptions.FailedToGenerateResponseError(error_msg)


        def for_non_stream():
            # This function implicitly uses the updated for_stream
            for _ in for_stream():
                pass
            return self.last_response

        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[str, Generator[str, None, None]]:
        """
        Generates a response from the Typli.ai API.

        Args:
            prompt (str): The prompt to send to the API.
            stream (bool): Whether to stream the response.
            raw (bool): Whether to return the raw response.
            optimizer (str): Optimizer to use for the prompt.
            conversationally (bool): Whether to generate the prompt conversationally.

        Returns:
            Union[str, Generator[str, None, None]]: The API response.
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
        """
        assert isinstance(response, dict), "Response should be of dict data-type only"
        # Ensure text exists before processing
        return response.get("text", "").replace('\\n', '\n').replace('\\n\\n', '\n\n')



if __name__ == "__main__":
    from rich import print
    try:
        ai = TypliAI(timeout=60)
        response = ai.chat("Write a short poem about AI", stream=True, raw=False)
        for chunk in response:
            print(chunk, end="", flush=True)
    except Exception as e:
        print(f"An error occurred: {e}")