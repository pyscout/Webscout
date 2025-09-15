from curl_cffi.requests import Session
from curl_cffi import CurlError
import json
from typing import Any, Dict, Optional, Generator, Union
from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream # Import sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent
class SonusAI(Provider):
    """
    A class to interact with the Sonus AI chat API.
    """
    required_auth = False
    AVAILABLE_MODELS = [
        "pro",
        "air",
        "mini"
    ]

    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 2049, # Note: max_tokens is not directly used by this API
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "pro"
    ):
        """Initializes the Sonus AI API client."""
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")
            
        self.url = "https://chat.sonus.ai/chat.php"
        
        # Headers for the request
        self.headers = {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://chat.sonus.ai',
            'Referer': 'https://chat.sonus.ai/',
            'User-Agent': LitAgent().random()
            # Add sec-ch-ua headers if needed for impersonation consistency
        }
        
        # Initialize curl_cffi Session
        self.session = Session()
        # Update curl_cffi session headers and proxies
        self.session.headers.update(self.headers)
        self.session.proxies = proxies # Assign proxies directly

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

    @staticmethod
    def _sonus_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        """Extracts content from Sonus stream JSON objects."""
        if isinstance(chunk, dict) and "content" in chunk:
            return chunk.get("content")
        return None

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        reasoning: bool = False,
    ) -> Union[Dict[str, Any], Generator]:
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise Exception(f"Optimizer is not one of {self.__available_optimizers}")

        # Prepare the multipart form data (curl_cffi handles tuples for files/data)
        # No need for explicit (None, ...) for simple fields when using `data=`
        form_data = {
            'message': conversation_prompt,
            'history': "", # Explicitly empty string if needed, or omit if None is acceptable
            'reasoning': str(reasoning).lower(),
            'model': self.model
        }
        # Note: curl_cffi's `files` parameter is for actual file uploads.
        # For simple key-value pairs like this, `data` is usually sufficient for multipart/form-data.
        # If the server strictly requires `files`, keep the original structure but it might not work as expected with curl_cffi without actual file objects.

        def for_stream():
            try:
                # Use curl_cffi session post with impersonate
                # Use `data` instead of `files` for simple key-value multipart
                response = self.session.post(
                    self.url, 
                    # headers are set on the session
                    data=form_data, # Use data for multipart form fields
                    stream=True, 
                    timeout=self.timeout,
                    impersonate="chrome110" # Use a common impersonation profile
                )
                if response.status_code != 200:
                    raise exceptions.FailedToGenerateResponseError(
                        f"Request failed with status code {response.status_code} - {response.text}"
                    )

                streaming_text = ""
                # Use sanitize_stream
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None), # Pass byte iterator
                    intro_value="data:",
                    to_json=True,     # Stream sends JSON
                    content_extractor=self._sonus_extractor, # Use the specific extractor
                    yield_raw_on_error=False # Skip non-JSON lines or lines where extractor fails
                )

                for content_chunk in processed_stream:
                    # content_chunk is the string extracted by _sonus_extractor
                    if content_chunk and isinstance(content_chunk, str):
                        streaming_text += content_chunk
                        yield dict(text=content_chunk) if not raw else content_chunk
                
                # Update history and last response after stream finishes
                self.last_response = {"text": streaming_text}
                self.conversation.update_chat_history(prompt, streaming_text)
                    
            except CurlError as e: # Catch CurlError
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {str(e)}") from e
            except Exception as e: # Catch other potential exceptions
                 raise exceptions.FailedToGenerateResponseError(f"An unexpected error occurred ({type(e).__name__}): {e}") from e

        def for_non_stream():
            try:
                 # Use curl_cffi session post with impersonate
                response = self.session.post(
                    self.url, 
                    # headers are set on the session
                    data=form_data, # Use data for multipart form fields
                    timeout=self.timeout,
                    impersonate="chrome110" # Use a common impersonation profile
                )
                if response.status_code != 200:
                    raise exceptions.FailedToGenerateResponseError(
                        f"Request failed with status code {response.status_code} - {response.text}"
                    )

                response_text_raw = response.text # Get raw text

                # Use sanitize_stream to process the non-streaming text
                processed_stream = sanitize_stream(
                    data=response_text_raw.splitlines(), # Split into lines
                    intro_value="data:",
                    to_json=True,
                    content_extractor=self._sonus_extractor,
                    yield_raw_on_error=False
                )

                # Aggregate the results
                full_response = ""
                for content in processed_stream:
                    if content and isinstance(content, str):
                        full_response += content

                self.last_response = {"text": full_response}
                self.conversation.update_chat_history(prompt, full_response)
                # Return dict or raw string
                return full_response if raw else {"text": full_response}
                
            except CurlError as e: # Catch CurlError
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {str(e)}") from e
            except Exception as e: # Catch other potential exceptions
                raise exceptions.FailedToGenerateResponseError(f"An unexpected error occurred ({type(e).__name__}): {e}") from e

        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        reasoning: bool = False,
        raw: bool = False,  # Added raw parameter
    ) -> Union[str, Generator[str, None, None]]:
        def for_stream_chat():
            for response in self.ask(
                prompt, stream=True, raw=raw, optimizer=optimizer, conversationally=conversationally, reasoning=reasoning
            ):
                if raw:
                    yield response
                else:
                    yield self.get_message(response)
        def for_non_stream_chat():
            response_data = self.ask(
                prompt, stream=False, raw=raw, optimizer=optimizer, conversationally=conversationally, reasoning=reasoning
            )
            if raw:
                return response_data if isinstance(response_data, str) else self.get_message(response_data)
            else:
                return self.get_message(response_data)
        return for_stream_chat() if stream else for_non_stream_chat()

    def get_message(self, response: dict) -> str:
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response["text"]

if __name__ == "__main__":
    # Ensure curl_cffi is installed
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)

    for model in SonusAI.AVAILABLE_MODELS:
        try:
            test_ai = SonusAI(model=model, timeout=60)
            response = test_ai.chat("Say 'Hello' in one word", stream=True)
            response_text = ""
            for chunk in response:
                response_text += chunk
            
            if response_text and len(response_text.strip()) > 0:
                status = "✓"
                # Clean and truncate response
                clean_text = response_text.strip().encode('utf-8', errors='ignore').decode('utf-8')
                display_text = clean_text[:50] + "..." if len(clean_text) > 50 else clean_text
            else:
                status = "✗"
                display_text = "Empty or invalid response"
            print(f"\r{model:<50} {status:<10} {display_text}")
        except Exception as e:
            print(f"\r{model:<50} {'✗':<10} {str(e)}")