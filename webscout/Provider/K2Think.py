import json
import os
from typing import Any, Dict, Optional, Generator, Union, List

from curl_cffi.requests import Session
from curl_cffi import CurlError

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent
from webscout.sanitize import sanitize_stream

class K2Think(Provider):
    """
    A class to interact with the K2Think AI API.
    """
    required_auth = False
    AVAILABLE_MODELS = [
        "MBZUAI-IFM/K2-Think",

    ]

    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 600,
        temperature: float = 1,
        presence_penalty: int = 0,
        frequency_penalty: int = 0,
        top_p: float = 1,
        model: str = "MBZUAI-IFM/K2-Think",
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        base_url: str = "https://www.k2think.ai/api/guest/chat/completions",
        system_prompt: str = "You are a helpful assistant.",
        browser: str = "chrome"
    ):
        """Initializes the K2Think AI client."""
        self.url = base_url

        # Initialize LitAgent
        self.agent = LitAgent()
        self.fingerprint = self.agent.generate_fingerprint(browser)

        # Use the fingerprint for headers
        self.headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": self.fingerprint["accept_language"],
            "Content-Type": "application/json",
            "User-Agent": self.fingerprint.get("user_agent", ""),
            "Origin": "https://www.k2think.ai",
            "Referer": "https://www.k2think.ai/guest",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Ch-Ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Priority": "u=1, i"
        }

        # Initialize curl_cffi Session
        self.session = Session()
        # Update curl_cffi session headers and proxies
        self.session.headers.update(self.headers)
        self.session.proxies = proxies  # Assign proxies directly

        self.system_prompt = system_prompt
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = {}
        self.model = model
        self.temperature = temperature
        self.presence_penalty = presence_penalty
        self.frequency_penalty = frequency_penalty
        self.top_p = top_p

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

    def refresh_identity(self, browser: str = None):
        """
        Refreshes the browser identity fingerprint.

        Args:
            browser: Specific browser to use for the new fingerprint
        """
        browser = browser or self.fingerprint.get("browser_type", "chrome")
        self.fingerprint = self.agent.generate_fingerprint(browser)

        # Update headers with new fingerprint (only relevant ones)
        self.headers.update({
            "Accept-Language": self.fingerprint["accept_language"],
            "User-Agent": self.fingerprint.get("user_agent", ""),
        })

        # Update session headers
        self.session.headers.update(self.headers)

        return self.fingerprint

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator]:
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise exceptions.FailedToGenerateResponseError(f"Optimizer is not one of {self.__available_optimizers}")

        # Payload construction
        payload = {
            "stream": stream,
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": conversation_prompt}
            ],
            "params": {}
        }

        def for_stream():
            try:
                # Use curl_cffi session post with impersonate
                response = self.session.post(
                    self.url,
                    data=json.dumps(payload),
                    stream=True,
                    timeout=self.timeout,
                    impersonate="chrome110"
                )
                response.raise_for_status()

                # Extract content using the specified patterns - prioritize answer only
                extract_regexes = [
                    r'<answer>([\s\S]*?)<\/answer>',  # Extract answer content only
                ]
                
                skip_regexes = [
                    r'^\s*$',  # Skip empty lines
                    r'data:\s*\[DONE\]',  # Skip done markers  
                    r'data:\s*$',  # Skip empty data lines
                    r'^\s*\{\s*\}\s*$',  # Skip empty JSON objects
                    r'<details type="reasoning"[^>]*>.*?<\/details>',  # Skip reasoning sections entirely
                ]

                streaming_text = ""
                
                # Use sanitize_stream to process the response
                stream_chunks = sanitize_stream(
                    response.iter_content(chunk_size=None),
                    intro_value="data:",
                    to_json=False,  # Don't parse as JSON, use regex extraction
                    skip_regexes=skip_regexes,
                    extract_regexes=extract_regexes,
                    encoding='utf-8',
                    yield_raw_on_error=False
                )
                
                for content_chunk in stream_chunks:
                    if content_chunk and isinstance(content_chunk, str):
                        content_cleaned = content_chunk.strip()
                        if content_cleaned:
                            streaming_text += content_cleaned
                            yield {"text": content_cleaned}

            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {str(e)}") from e
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed ({type(e).__name__}): {str(e)}") from e
            finally:
                # Update history after stream finishes or fails
                if streaming_text:
                    self.last_response = {"text": streaming_text}
                    self.conversation.update_chat_history(prompt, streaming_text)

        def for_non_stream():
            try:
                # For non-streaming, we still need to handle the stream format
                response = self.session.post(
                    self.url,
                    data=json.dumps(payload),
                    stream=True,
                    timeout=self.timeout,
                    impersonate="chrome110"
                )
                response.raise_for_status()

                # Extract content using the specified patterns
                extract_regexes = [
                    r'<answer>([\s\S]*?)<\/answer>',  # Extract answer content
                    r'<details type="reasoning"[^>]*>.*?<summary>.*?<\/summary>([\s\S]*?)<\/details>',  # Extract reasoning content
                ]
                
                skip_regexes = [
                    r'^\s*$',  # Skip empty lines
                    r'data:\s*\[DONE\]',  # Skip done markers  
                    r'data:\s*$',  # Skip empty data lines
                    r'^\s*\{\s*\}\s*$',  # Skip empty JSON objects
                ]

                streaming_text = ""

                # Use sanitize_stream to process the response
                stream_chunks = sanitize_stream(
                    response.iter_content(chunk_size=None),
                    intro_value="data:",
                    to_json=False,  # Don't parse as JSON, use regex extraction
                    skip_regexes=skip_regexes,
                    extract_regexes=extract_regexes,
                    encoding='utf-8',
                    yield_raw_on_error=False
                )
                
                for content_chunk in stream_chunks:
                    if content_chunk and isinstance(content_chunk, str):
                        content_cleaned = content_chunk.strip()
                        if content_cleaned:
                            # Decode JSON escape sequences
                            content_decoded = content_cleaned.encode().decode('unicode_escape')
                            streaming_text += content_decoded

                self.last_response = {"text": streaming_text}
                self.conversation.update_chat_history(prompt, streaming_text)
                return self.last_response if not raw else streaming_text

            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {str(e)}") from e
            except Exception as e:
                err_text = getattr(e, 'response', None) and getattr(e.response, 'text', '')
                raise exceptions.FailedToGenerateResponseError(f"Request failed ({type(e).__name__}): {e} - {err_text}") from e

        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[str, Generator[str, None, None]]:
        def for_stream_chat():
            gen = self.ask(
                prompt, stream=True, raw=False,
                optimizer=optimizer, conversationally=conversationally
            )
            for response_dict in gen:
                yield self.get_message(response_dict)

        def for_non_stream_chat():
            response_data = self.ask(
                prompt, stream=False, raw=False,
                optimizer=optimizer, conversationally=conversationally
            )
            return self.get_message(response_data)

        return for_stream_chat() if stream else for_non_stream_chat()

    def get_message(self, response: dict) -> str:
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response["text"].replace('\\n', '\n').replace('\\n\\n', '\n\n')

if __name__ == "__main__":
    # Simple test
    try:
        ai = K2Think(model="MBZUAI-IFM/K2-Think", timeout=30)
        response = ai.chat("What is artificial intelligence?", stream=True)
        for chunk in response:
            print(chunk, end="", flush=True)
        print()
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()