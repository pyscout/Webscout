import re
import json
from typing import Union, Any, Dict, Generator, Optional
from curl_cffi import CurlError 
from curl_cffi.requests import Session

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream # Import sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent


class WiseCat(Provider):
    """
    A class to interact with the WiseCat API.
    """

    required_auth = False
    AVAILABLE_MODELS = [
        "chat-model-small",
        # "chat-model-large", # >>> NOT WORKING <<<
        "chat-model-reasoning",
    ]

    def __init__(self,
        is_conversation: bool = True,
        max_tokens: int = 600,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "chat-model-small",
        system_prompt: str = "You are a helpful AI assistant."
    ):
        """Initializes the WiseCat API client."""

        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        # Initialize curl_cffi Session
        self.session = Session()
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.api_endpoint = "https://wise-cat-groq.vercel.app/api/chat"
        # stream_chunk_size is not directly applicable to curl_cffi iter_lines
        # self.stream_chunk_size = 64 
        self.timeout = timeout
        self.last_response = {}
        self.model = model
        self.system_prompt = system_prompt
        self.litagent = LitAgent()
        # Generate headers using LitAgent, but apply them to the curl_cffi session
        self.headers = self.litagent.generate_fingerprint() 
        # Update curl_cffi session headers and proxies
        self.session.headers.update(self.headers)
        self.session.proxies = proxies

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
        """Chat with AI"""
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
            "id": "ephemeral",
            "messages": [
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": conversation_prompt,
                }
            ],
            "selectedChatModel": self.model
        }
        def for_stream():
            try:
                response = self.session.post(
                    self.api_endpoint, 
                    headers=self.headers, 
                    json=payload, 
                    stream=True, 
                    timeout=self.timeout,
                    impersonate="chrome120"
                )
                if not response.ok:
                    error_msg = f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                    raise exceptions.FailedToGenerateResponseError(error_msg)
                streaming_text = ""
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None),
                    intro_value=None,
                    to_json=False,
                    extract_regexes=[
                        r'0:"(.*?)"'  # Extract content from 0:"..." format
                    ],
                    skip_regexes=[
                        r'\(\d+\.?\d*s\)',  # Skip timing information like (0.3s), (1s), (0.5s)
                        r'\(\d+\.?\d*ms\)', # Skip millisecond timing like (300ms)
                    ],
                    raw=raw
                )
                for content_chunk in processed_stream:
                    if content_chunk and isinstance(content_chunk, str):
                        # Content is already extracted by sanitize_stream
                        # Handle unicode escaping and quote unescaping
                        extracted_content = content_chunk.encode().decode('unicode_escape')
                        extracted_content = extracted_content.replace('\\\\', '\\').replace('\\"', '"')
                        
                        if raw:
                            yield extracted_content
                        else:
                            streaming_text += extracted_content
                            yield dict(text=extracted_content)
                self.last_response.update(dict(text=streaming_text))
                self.conversation.update_chat_history(
                    prompt, self.get_message(self.last_response)
                )
            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}")
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"An unexpected error occurred ({type(e).__name__}): {e}")
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
        raw: bool = False,  # Added raw parameter
    ) -> str:
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
        """Retrieves message only from response"""
        assert isinstance(response, dict), "Response should be of dict data-type only"
        # Formatting (like unicode escapes) is handled by the extractor now.
        # Keep newline replacement if needed for display.
        return response.get("text", "").replace('\\n', '\n').replace('\\n\\n', '\n\n')

if __name__ == "__main__":
    # Ensure curl_cffi is installed
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)
    
    # Test all available models
    working = 0
    total = len(WiseCat.AVAILABLE_MODELS)
    
    for model in WiseCat.AVAILABLE_MODELS:
        try:
            test_ai = WiseCat(model=model, timeout=60)
            response = test_ai.chat("Say 'Hello' in one word", stream=True)
            response_text = ""
            for chunk in response:
                response_text += chunk
                print(f"\r{model:<50} {'Testing...':<10}", end="", flush=True)
            
            if response_text and len(response_text.strip()) > 0:
                status = "✓"
                # Truncate response if too long
                display_text = response_text.strip()[:50] + "..." if len(response_text.strip()) > 50 else response_text.strip()
            else:
                status = "✗"
                display_text = "Empty or invalid response"
            print(f"\r{model:<50} {status:<10} {display_text}")
        except Exception as e:
            print(f"\r{model:<50} {'✗':<10} {str(e)}")