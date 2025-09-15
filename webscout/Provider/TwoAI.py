from curl_cffi.requests import Session
from curl_cffi import CurlError
import json
import base64
from typing import Any, Dict, Optional, Generator, Union
import re  # Import re for parsing SSE

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent


class TwoAI(Provider):
    """
    A class to interact with the Two AI API (v2) with LitAgent user-agent.
    SUTRA is a family of large multi-lingual language models (LMLMs) developed by TWO AI.
    SUTRA's dual-transformer extends the power of both MoE and Dense AI language model architectures,
    delivering cost-efficient multilingual capabilities for over 50+ languages.

    API keys must be provided directly by the user.
    """

    required_auth = True
    AVAILABLE_MODELS = [
        "sutra-v2",  # Multilingual AI model for instruction execution and conversational intelligence
        "sutra-r0",  # Advanced reasoning model for complex problem-solving and deep contextual understanding
    ]

    def __init__(
        self,
        api_key: str,
        is_conversation: bool = True,
        max_tokens: int = 1024,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "sutra-v2",  # Default model
        temperature: float = 0.6,
        system_message: str = "You are a helpful assistant."
    ):
        """
        Initializes the TwoAI API client.

        Args:
            api_key: TwoAI API key (required).
            is_conversation: Whether to maintain conversation history.
            max_tokens: Maximum number of tokens to generate.
            timeout: Request timeout in seconds.
            intro: Introduction text for the conversation.
            filepath: Path to save conversation history.
            update_file: Whether to update the conversation history file.
            proxies: Proxy configuration for requests.
            history_offset: Maximum history length in characters.
            act: Persona for the conversation.
            model: Model to use. Must be one of AVAILABLE_MODELS.
            temperature: Temperature for generation (0.0 to 1.0).
            system_message: System message to use for the conversation.
        """
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        if not api_key:
            raise exceptions.AuthenticationError("TwoAI API key is required.")

        self.url = "https://chatsutra-server.account-2b0.workers.dev/v2/chat/completions"  # Correct API endpoint
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9,en-IN;q=0.8',
            'Content-Type': 'application/json',
            'Origin': 'https://chat.two.ai',
            'Referer': 'https://chatsutra-server.account-2b0.workers.dev/',
            'Sec-Ch-Ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Gpc': '1',
            'Dnt': '1',
            'X-Session-Token': api_key  # Using session token instead of Bearer auth
        }

        # Initialize curl_cffi Session
        self.session = Session()
        self.session.headers.update(self.headers)
        self.session.proxies = proxies

        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = {}
        self.model = model
        self.temperature = temperature
        self.system_message = system_message
        self.api_key = api_key

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

    @staticmethod
    def _twoai_extractor(chunk_json: Dict[str, Any]) -> Optional[str]:
        """Extracts content from TwoAI v2 stream JSON objects."""
        if not isinstance(chunk_json, dict) or "choices" not in chunk_json or not chunk_json["choices"]:
            return None

        delta = chunk_json["choices"][0].get("delta")
        if not isinstance(delta, dict):
            return None

        content = delta.get("content")
        return content if isinstance(content, str) else None

    def encode_image(self, image_path: str) -> str:
        """
        Encode an image file to base64 string.

        Args:
            image_path: Path to the image file

        Returns:
            Base64 encoded string of the image
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def ask(
        self,
        prompt: str,
        stream: bool = True,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        online_search: bool = True,
        image_path: str = None,
    ) -> Union[Dict[str, Any], Generator]:
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(conversation_prompt if conversationally else prompt)
            else:
                raise Exception(f"Optimizer is not one of {self.__available_optimizers}")

        # Prepare messages with image if provided
        if image_path:
            # Create a message with image content
            image_content = {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{self.encode_image(image_path)}"
                }
            }
            user_message = {
                "role": "user",
                "content": [
                    {"type": "text", "text": conversation_prompt},
                    image_content
                ]
            }
        else:
            # Text-only message
            user_message = {"role": "user", "content": conversation_prompt}

        # Prepare the payload
        payload = {
            "messages": [
                *([{"role": "system", "content": self.system_message}] if self.system_message else []),
                user_message
            ],
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens_to_sample,
            "extra_body": {
                "online_search": online_search,
            }
        }

        def for_stream():
            streaming_text = "" # Initialize outside try block
            try:
                response = self.session.post(
                    self.url,
                    json=payload,
                    stream=True,
                    timeout=self.timeout
                )

                if response.status_code != 200:
                    error_detail = response.text
                    try:
                        error_json = response.json()
                        error_detail = error_json.get("error", {}).get("message", error_detail)
                    except json.JSONDecodeError:
                        pass
                    raise exceptions.FailedToGenerateResponseError(
                        f"Request failed with status code {response.status_code} - {error_detail}"
                    )

                # Use sanitize_stream to process the SSE stream
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None),
                    intro_value="data:",
                    to_json=True,
                    skip_markers=["[DONE]"],
                    content_extractor=self._twoai_extractor,
                    yield_raw_on_error=False
                )

                for content_chunk in processed_stream:
                    if content_chunk and isinstance(content_chunk, str):
                        streaming_text += content_chunk
                        resp = dict(text=content_chunk)
                        yield resp if not raw else content_chunk

                # If stream completes successfully, update history
                self.last_response = {"text": streaming_text}
                self.conversation.update_chat_history(prompt, streaming_text)

            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}") from e
            except exceptions.FailedToGenerateResponseError:
                raise # Re-raise specific exception
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"An unexpected error occurred during streaming ({type(e).__name__}): {e}") from e
            finally:
                # Ensure history is updated even if stream ends abruptly but text was received
                if streaming_text and not self.last_response: # Check if last_response wasn't set in the try block
                    self.last_response = {"text": streaming_text}
                    self.conversation.update_chat_history(prompt, streaming_text)


        def for_non_stream():
            # Non-stream still uses the stream internally and aggregates
            streaming_text = ""
            # We need to consume the generator from for_stream()
            gen = for_stream()
            try:
                for chunk_data in gen:
                    if isinstance(chunk_data, dict) and "text" in chunk_data:
                        streaming_text += chunk_data["text"]
                    elif isinstance(chunk_data, str): # Handle raw=True case
                        streaming_text += chunk_data
            except exceptions.FailedToGenerateResponseError:
                 # If the underlying stream fails, re-raise the error
                 raise
            # self.last_response and history are updated within for_stream's try/finally
            return self.last_response # Return the final aggregated dict

        # The API uses SSE streaming for all requests, so we always use streaming
        return for_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = True,
        optimizer: str = None,
        conversationally: bool = False,
        online_search: bool = True,
        image_path: str = None,
    ) -> str:
        # The API uses SSE streaming for all requests, so we always aggregate
        aggregated_text = ""
        gen = self.ask(
            prompt,
            stream=True,
            raw=False, # Ensure ask yields dicts
            optimizer=optimizer,
            conversationally=conversationally,
            online_search=online_search,
            image_path=image_path,
        )
        for response_dict in gen:
            if isinstance(response_dict, dict) and "text" in response_dict:
                aggregated_text += response_dict["text"]
            elif isinstance(response_dict, str):
                aggregated_text += response_dict
        
        return aggregated_text

    def get_message(self, response: dict) -> str:
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response.get("text", "") # Use .get for safety


if __name__ == "__main__":
    from rich import print
    ai = TwoAI(api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJzanl2OHJtZGxDZDFnQ2hQdGxzZHdxUlVteXkyIiwic291cmNlIjoiRmlyZWJhc2UiLCJpYXQiOjE3NTc4NTEyMzYsImV4cCI6MTc1Nzg1MjEzNn0.ilTYrHRdN3_cme6VW3knWWfbypY_n_gsUe9DeDhEwrM", model="sutra-v2", temperature=0.7)
    response = ai.chat("Write a poem about AI in the style of Shakespeare.")
    for chunk in response:
        print(chunk, end="", flush=True)