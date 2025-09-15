from uuid import uuid4
from curl_cffi.requests import Session
from curl_cffi import CurlError
import json
import re
import threading
from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation, sanitize_stream # Import sanitize_stream
from webscout.AIutel import AwesomePrompts
from webscout.AIbase import Provider
from typing import Dict, Union, Any, Optional
from webscout.litagent import LitAgent
from webscout import exceptions

class PiAI(Provider):
    """
    PiAI is a provider class for interacting with the Pi.ai chat API.

    Attributes:
        knowledge_cutoff (str): The knowledge cutoff date for the model
        AVAILABLE_VOICES (Dict[str, int]): Available voice options for audio responses
        AVAILABLE_MODELS (List[str]): Available model options for the API
    """
    required_auth = False
    AVAILABLE_MODELS = ["inflection_3_pi"]
    AVAILABLE_VOICES: Dict[str, int] = {
        "voice1": 1,
        "voice2": 2,
        "voice3": 3,
        "voice4": 4,
        "voice5": 5,
        "voice6": 6,
        "voice7": 7,
        "voice8": 8
    }

    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 2048, # Note: max_tokens is not used by this API
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        voice: bool = False,
        voice_name: str = "voice3",
        output_file: str = "PiAI.mp3",
        model: str = "inflection_3_pi", # Note: model is not used by this API
    ):
        """
        Initializes PiAI with voice support.

        Args:
            voice (bool): Enable/disable voice output
            voice_name (str): Name of the voice to use (if None, uses default)
            output_file (str): Path to save voice output (default: PiAI.mp3)
        """
        # Voice settings
        self.voice_enabled = voice
        self.voice_name = voice_name
        self.output_file = output_file

        if voice and voice_name and voice_name not in self.AVAILABLE_VOICES:
            raise ValueError(f"Voice '{voice_name}' not available. Choose from: {list(self.AVAILABLE_VOICES.keys())}")

        # Initialize curl_cffi Session instead of cloudscraper/requests
        self.session = Session()
        self.primary_url = 'https://pi.ai/api/chat'
        self.fallback_url = 'https://pi.ai/api/v2/chat'
        self.url = self.primary_url
        self.headers = {
            'Accept': 'text/event-stream',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9,en-IN;q=0.8',
            'Content-Type': 'application/json',
            'DNT': '1',
            'Origin': 'https://pi.ai',
            'Referer': 'https://pi.ai/talk',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': LitAgent().random(),
            'X-Api-Version': '3'
        }
        self.cookies = {
            '__cf_bm': uuid4().hex
        }

        # Update curl_cffi session headers, proxies, and cookies
        self.session.headers.update(self.headers)
        self.session.proxies = proxies # Assign proxies directly
        # Set cookies on the session object for curl_cffi
        for name, value in self.cookies.items():
            self.session.cookies.set(name, value)

        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = {} if self.is_conversation else {'text': ""}
        self.conversation_id = None

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
        self.session.proxies = proxies

        if self.is_conversation:
            self.start_conversation()

    @staticmethod
    def _pi_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        """Extracts text content from PiAI stream JSON objects."""
        if isinstance(chunk, dict) and 'text' in chunk and chunk['text'] is not None:
            return chunk.get("text")
        return None

    def start_conversation(self) -> str:
        """
        Initializes a new conversation and returns the conversation ID.
        """
        try:
            # Use curl_cffi session post with impersonate
            # Cookies are handled by the session
            response = self.session.post(
                "https://pi.ai/api/chat/start",
                # headers are set on the session
                # cookies=self.cookies, # Handled by session
                json={},
                timeout=self.timeout,
                # proxies are set on the session
                impersonate="chrome110" # Use a common impersonation profile
            )
            response.raise_for_status() # Check for HTTP errors

            data = response.json()
            # Ensure the expected structure before accessing
            if 'conversations' in data and data['conversations'] and 'sid' in data['conversations'][0]:
                self.conversation_id = data['conversations'][0]['sid']
                return self.conversation_id
            else:
                 raise exceptions.FailedToGenerateResponseError(f"Unexpected response structure from start API: {data}")

        except CurlError as e: # Catch CurlError
            raise exceptions.FailedToGenerateResponseError(f"Failed to start conversation (CurlError): {e}") from e
        except Exception as e: # Catch other potential exceptions (like HTTPError, JSONDecodeError)
            # Extract error text from the response if available
            err_text = e.response.text if hasattr(e, 'response') and hasattr(e.response, 'text') else ''
            raise exceptions.FailedToGenerateResponseError(f"Failed to start conversation ({type(e).__name__}): {e} - {err_text}") from e

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        voice: bool = None,
        voice_name: str = None,
        output_file: str = None
    ) -> Union[dict, str, Any]:
        """
        Interact with Pi.ai by sending a prompt and receiving a response.
        Now supports raw streaming and non-streaming output, matching the pattern in other providers.

        Args:
            prompt (str): The prompt to send
            stream (bool): Whether to stream the response
            raw (bool): Return raw response format
            optimizer (str): Prompt optimizer to use
            conversationally (bool): Use conversation context
            voice (bool): Override default voice setting
            voice_name (str): Override default voice name
            output_file (str): Override default output file path
        """
        # Voice configuration
        voice = self.voice_enabled if voice is None else voice
        voice_name = self.voice_name if voice_name is None else voice_name
        output_file = self.output_file if output_file is None else output_file

        if voice and voice_name and voice_name not in self.AVAILABLE_VOICES:
            raise ValueError(f"Voice '{voice_name}' not available. Choose from: {list(self.AVAILABLE_VOICES.keys())}")

        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise Exception(f"Optimizer is not one of {self.__available_optimizers}")

        data = {
            'text': conversation_prompt,
            'conversation': self.conversation_id
        }

        def process_stream():
            try:
                current_url = self.url
                response = self.session.post(
                    current_url,
                    json=data,
                    stream=True,
                    timeout=self.timeout,
                    impersonate="chrome110"
                )
                if not response.ok and current_url == self.primary_url:
                    current_url = self.fallback_url
                    response = self.session.post(
                        current_url,
                        json=data,
                        stream=True,
                        timeout=self.timeout,
                        impersonate="chrome110"
                    )
                response.raise_for_status()

                sids = []
                streaming_text = ""
                full_raw_data_for_sids = ""

                processed_stream = sanitize_stream(
                    data=response.iter_lines(),
                    intro_value="data: ",
                    to_json=True,
                    content_extractor=self._pi_extractor,
                    raw=raw
                )
                for content in processed_stream:
                    if raw:
                        yield content
                    else:
                        if content and isinstance(content, str):
                            streaming_text += content
                            yield {"text": streaming_text}
                # SID extraction for voice
                for line_bytes in response.iter_lines():
                    if line_bytes:
                        line = line_bytes.decode('utf-8')
                        full_raw_data_for_sids += line + "\n"
                sids = re.findall(r'"sid":"(.*?)"', full_raw_data_for_sids)
                second_sid = sids[1] if len(sids) >= 2 else None
                if voice and voice_name and second_sid:
                    threading.Thread(
                        target=self.download_audio_threaded,
                        args=(voice_name, second_sid, output_file)
                    ).start()
                if not raw:
                    self.last_response = dict(text=streaming_text)
                    self.conversation.update_chat_history(prompt, streaming_text)
            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"API request failed (CurlError): {e}") from e
            except Exception as e:
                err_text = getattr(e, 'response', None) and getattr(e.response, 'text', '')
                raise exceptions.FailedToGenerateResponseError(f"API request failed ({type(e).__name__}): {e} - {err_text}") from e

        if stream:
            return process_stream()
        else:
            full_response = ""
            for chunk in process_stream():
                if raw:
                    if isinstance(chunk, str):
                        full_response += chunk
                else:
                    if isinstance(chunk, dict) and "text" in chunk:
                        full_response = chunk["text"]
            if not raw:
                self.last_response = {"text": full_response}
                self.conversation.update_chat_history(prompt, full_response)
                return self.last_response
            else:
                return full_response

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        voice: bool = None,
        voice_name: str = None,
        output_file: str = None,
        raw: bool = False,  # Added raw parameter
    ) -> Union[str, Any]:
        """
        Generates a response based on the provided prompt.

        Args:
            prompt (str): The prompt to send
            stream (bool): Whether to stream the response
            optimizer (str): Prompt optimizer to use
            conversationally (bool): Use conversation context
            voice (bool): Override default voice setting
            voice_name (str): Override default voice name
            output_file (str): Override default output file path
        """
        # Use instance defaults if not specified
        voice = self.voice_enabled if voice is None else voice
        voice_name = self.voice_name if voice_name is None else voice_name
        output_file = self.output_file if output_file is None else output_file

        if voice and voice_name and voice_name not in self.AVAILABLE_VOICES:
            raise ValueError(f"Voice '{voice_name}' not available. Choose from: {list(self.AVAILABLE_VOICES.keys())}")

        if stream:
            def stream_generator():
                gen = self.ask(
                    prompt,
                    stream=True,
                    raw=raw,
                    optimizer=optimizer,
                    conversationally=conversationally,
                    voice=voice,
                    voice_name=voice_name,
                    output_file=output_file
                )
                for response in gen:
                    if raw:
                        yield response
                    else:
                        yield self.get_message(response)
            return stream_generator()
        else:
            response_data = self.ask(
                prompt,
                stream=False,
                raw=raw,
                optimizer=optimizer,
                conversationally=conversationally,
                voice=voice,
                voice_name=voice_name,
                output_file=output_file
            )
            if raw:
                return response_data
            else:
                return self.get_message(response_data)

    def get_message(self, response: dict) -> str:
        """Retrieves message only from response"""
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response["text"]

    def download_audio_threaded(self, voice_name: str, second_sid: str, output_file: str) -> None:
        """Downloads audio in a separate thread."""
        params = {
            'mode': 'eager',
            'voice': f'voice{self.AVAILABLE_VOICES[voice_name]}',
            'messageSid': second_sid,
        }

        try:
            # Use curl_cffi session get with impersonate
            audio_response = self.session.get(
                'https://pi.ai/api/chat/voice',
                params=params,
                # cookies are handled by the session
                # headers are set on the session
                timeout=self.timeout,
                # proxies are set on the session
                impersonate="chrome110" # Use a common impersonation profile
            )
            audio_response.raise_for_status() # Check for HTTP errors

            with open(output_file, "wb") as file:
                file.write(audio_response.content)

        except CurlError: # Catch CurlError
            # Optionally log the error
            pass
        except Exception: # Catch other potential exceptions
            # Optionally log the error
            pass

if __name__ == '__main__':
    # Ensure curl_cffi is installed
    from rich import print
    try: # Add try-except block for testing
        ai = PiAI(timeout=60)
        print("[bold blue]Testing Chat (Stream):[/bold blue]")
        response = ai.chat("hi", stream=True, raw=False)
        full_response = ""
        for chunk in response:
            print(chunk, end="", flush=True)
    except exceptions.FailedToGenerateResponseError as e:
        print(f"\n[bold red]API Error:[/bold red] {e}")
    except Exception as e:
        print(f"\n[bold red]An unexpected error occurred:[/bold red] {e}")
