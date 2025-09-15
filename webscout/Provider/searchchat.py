from curl_cffi.requests import Session
from curl_cffi import CurlError
import json
from datetime import datetime
from typing import Any, Dict, Optional, Generator, Union

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream # Import sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent

class SearchChatAI(Provider):
    """
    A class to interact with the SearchChatAI API.
    """
    required_auth = False
    AVAILABLE_MODELS = ["gpt-4o-mini-2024-07-18"]
    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 2049,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
    ):
        """Initializes the SearchChatAI API client."""
        self.url = "https://search-chat.ai/api/chat-test-stop.php"
        self.timeout = timeout
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.last_response = {}
        
        # Initialize LitAgent for user agent generation
        self.agent = LitAgent()
        # Use fingerprinting to create a consistent browser identity
        self.fingerprint = self.agent.generate_fingerprint("chrome")
        
        # Use the fingerprint for headers
        self.headers = {
            "Accept": self.fingerprint["accept"],
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": self.fingerprint["accept_language"],
            "Content-Type": "application/json",
            "Origin": "https://search-chat.ai",
            "Referer": "https://search-chat.ai/platform/?v2=2",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-CH-UA": self.fingerprint["sec_ch_ua"] or '"Not)A;Brand";v="99", "Microsoft Edge";v="127", "Chromium";v="127"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": f'"{self.fingerprint["platform"]}"',
            "User-Agent": self.fingerprint["user_agent"],
        }
        
        # Initialize curl_cffi Session
        self.session = Session()
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

    def refresh_identity(self, browser: str = None):
        """
        Refreshes the browser identity fingerprint.
        
        Args:
            browser: Specific browser to use for the new fingerprint
        """
        browser = browser or self.fingerprint.get("browser_type", "chrome")
        self.fingerprint = self.agent.generate_fingerprint(browser)
        
        # Update headers with new fingerprint
        self.headers.update({
            "Accept": self.fingerprint["accept"],
            "Accept-Language": self.fingerprint["accept_language"],
            "Sec-CH-UA": self.fingerprint["sec_ch_ua"] or self.headers["Sec-CH-UA"],
            "Sec-CH-UA-Platform": f'"{self.fingerprint["platform"]}"',
            "User-Agent": self.fingerprint["user_agent"],
        })
        
        # Update session headers (already done in the original code, should work with curl_cffi session)
        for header, value in self.headers.items():
            self.session.headers[header] = value
        
        return self.fingerprint

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator]:
        """
        Send a message to the API and get the response.
        
        Args:
            prompt: The message to send
            stream: Whether to stream the response
            raw: Whether to return raw response
            optimizer: The optimizer to use
            conversationally: Whether to use conversation history
            
        Returns:
            Either a dictionary with the response or a generator for streaming
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
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": conversation_prompt
                        }
                    ],
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                }
            ]
        }

        def for_stream():
            try:
                # Use curl_cffi session post with impersonate
                response = self.session.post(
                    self.url,
                    # headers are set on the session
                    json=payload,
                    stream=True,
                    timeout=self.timeout,
                    impersonate=self.fingerprint.get("browser_type", "chrome110") # Use fingerprint browser type
                )
                if response.status_code != 200:
                    # Add identity refresh logic on 403/429
                    if response.status_code in [403, 429]:
                        self.refresh_identity()
                        response = self.session.post(
                            self.url,
                            json=payload,
                            stream=True,
                            timeout=self.timeout,
                            impersonate=self.fingerprint.get("browser_type", "chrome110") # Use updated fingerprint
                        )
                        if not response.ok:
                             raise exceptions.FailedToGenerateResponseError(
                                f"Request failed after identity refresh - ({response.status_code}, {response.reason}) - {response.text}"
                            )
                    else:
                        raise exceptions.FailedToGenerateResponseError(
                            f"Request failed with status code {response.status_code} - {response.text}"
                        )
                    
                streaming_text = ""
                # Use sanitize_stream
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None), # Pass byte iterator
                    intro_value="data:",
                    to_json=True,     # Stream sends JSON
                    skip_markers=["[DONE]"],
                    content_extractor=lambda chunk: chunk.get('choices', [{}])[0].get('delta', {}).get('content') if isinstance(chunk, dict) else None,
                    yield_raw_on_error=False # Skip non-JSON or lines where extractor fails
                )

                for content_chunk in processed_stream:
                    # content_chunk is the string extracted by the content_extractor
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
            # Aggregate the stream using the updated for_stream logic
            full_text = ""
            # Iterate through the generator provided by for_stream
            # Ensure raw=False so for_stream yields dicts
            for chunk_data in for_stream(): 
                if isinstance(chunk_data, dict) and "text" in chunk_data:
                    full_text += chunk_data["text"]
                # If raw=True was somehow passed, handle string chunks
                elif isinstance(chunk_data, str):
                    full_text += chunk_data
            
            # last_response and history are updated within for_stream
            # Return the final aggregated response dict or raw string
            return full_text if raw else self.last_response


        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        raw: bool = False,  # Added raw parameter
    ) -> Union[str, Generator[str, None, None]]:
        """
        Chat with the API.
        
        Args:
            prompt: The message to send
            stream: Whether to stream the response
            optimizer: The optimizer to use
            conversationally: Whether to use conversation history
            
        Returns:
            Either a string response or a generator for streaming
        """
        def for_stream_chat():
            for response in self.ask(
                prompt, stream=True, raw=raw, optimizer=optimizer, conversationally=conversationally
            ):
                if raw:
                    yield response
                else:
                    yield self.get_message(response)
        def for_non_stream_chat():
            response_data = self.ask(
                prompt, stream=False, raw=raw, optimizer=optimizer, conversationally=conversationally
            )
            if raw:
                return response_data if isinstance(response_data, str) else self.get_message(response_data)
            else:
                return self.get_message(response_data)
        return for_stream_chat() if stream else for_non_stream_chat()

    def get_message(self, response: dict) -> str:
        """Extract the message from the response."""
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response["text"]

if __name__ == "__main__":
    # Ensure curl_cffi is installed
    print("-" * 80)
    print(f"{'Status':<10} {'Response'}")
    print("-" * 80)

    try:
        test_ai = SearchChatAI(timeout=60)
        response = test_ai.chat("Say 'Hello' in one word")
        response_text = response
        
        if response_text and len(response_text.strip()) > 0:
            status = "✓"
            # Truncate response if too long
            display_text = response_text.strip()[:50] + "..." if len(response_text.strip()) > 50 else response_text.strip()
        else:
            status = "✗"
            display_text = "Empty or invalid response"
        print(f"{status:<10} {display_text}")
    except Exception as e:
        print(f"{'✗':<10} {str(e)}")