from curl_cffi.requests import Session
from curl_cffi import CurlError
import json
import base64
import time
import os
import pickle
import tempfile
from typing import Any, Dict, Optional, Generator, Union
import re  # Import re for parsing SSE
import urllib.parse

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream # Import sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent
from webscout.Extra.tempmail import get_random_email


class TwoAI(Provider):
    """
    A class to interact with the Two AI API (v2) with LitAgent user-agent.
    SUTRA is a family of large multi-lingual language models (LMLMs) developed by TWO AI.
    SUTRA's dual-transformer extends the power of both MoE and Dense AI language model architectures,
    delivering cost-efficient multilingual capabilities for over 50+ languages.

    API keys can be generated using the generate_api_key() method, which uses a temporary email
    to register for the Two AI service and extract the API key from the confirmation email.
    API keys are cached to avoid regenerating them on every initialization.
    """

    AVAILABLE_MODELS = [
        "sutra-v2",  # Multilingual AI model for instruction execution and conversational intelligence
        "sutra-r0",  # Advanced reasoning model for complex problem-solving and deep contextual understanding
    ]
    
    # Class-level cache for API keys
    _api_key_cache = None
    _cache_file = os.path.join(tempfile.gettempdir(), "webscout_twoai_cache.pkl")

    @classmethod
    def _load_cached_api_key(cls) -> Optional[str]:
        """Load cached API key from file."""
        try:
            if os.path.exists(cls._cache_file):
                with open(cls._cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                    # Check if cache is not too old (24 hours)
                    if time.time() - cache_data.get('timestamp', 0) < 86400:
                        return cache_data.get('api_key')
        except Exception:
            # If cache is corrupted or unreadable, ignore and regenerate
            pass
        return None

    @classmethod
    def _save_cached_api_key(cls, api_key: str):
        """Save API key to cache file."""
        try:
            cache_data = {
                'api_key': api_key,
                'timestamp': time.time()
            }
            with open(cls._cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
        except Exception:
            # If caching fails, continue without caching
            pass

    @classmethod
    def _validate_api_key(cls, api_key: str) -> bool:
        """Validate if an API key is still working."""
        try:
            session = Session()
            headers = {
                'User-Agent': LitAgent().random(),
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}',
            }
            
            # Test with a simple request
            test_payload = {
                "messages": [{"role": "user", "content": "test"}],
                "model": "sutra-v2",
                "max_tokens": 1,
                "stream": False
            }
            
            response = session.post(
                "https://api.two.ai/v2/chat/completions",
                headers=headers,
                json=test_payload,
                timeout=10,
                impersonate="chrome120"
            )
            
            # If we get a 200 or 400 (bad request but auth worked), key is valid
            # If we get 401/403, key is invalid
            return response.status_code not in [401, 403]
        except Exception:
            # If validation fails, assume key is invalid
            return False

    @classmethod
    def get_cached_api_key(cls) -> str:
        """Get a cached API key or generate a new one if needed."""
        # First check class-level cache
        if cls._api_key_cache:
            if cls._validate_api_key(cls._api_key_cache):
                return cls._api_key_cache
            else:
                cls._api_key_cache = None

        # Then check file cache
        cached_key = cls._load_cached_api_key()
        if cached_key and cls._validate_api_key(cached_key):
            cls._api_key_cache = cached_key
            return cached_key

        # Generate new key if no valid cached key
        new_key = cls.generate_api_key()
        cls._api_key_cache = new_key
        cls._save_cached_api_key(new_key)
        return new_key

    @staticmethod
    def generate_api_key() -> str:
        """
        Generate a new Two AI API key using a temporary email.

        This method:
        1. Creates a temporary email using webscout's tempmail module
        2. Registers for Two AI using the Loops.so newsletter form
        3. Waits for and extracts the API key from the confirmation email

        Returns:
            str: The generated API key

        Raises:
            Exception: If the API key cannot be generated
        """
        # Get a temporary email
        email, provider = get_random_email("tempmailio")

        # Register for Two AI using the Loops.so newsletter form
        loops_url = "https://app.loops.so/api/newsletter-form/cm7i4o92h057auy1o74cxbhxo"

        # Create a session with appropriate headers
        session = Session()
        session.headers.update({
            'User-Agent': LitAgent().random(),
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://www.two.ai',
            'Referer': 'https://app.loops.so/',
        })

        # Prepare form data
        form_data = {
            'email': email,
            'userGroup': 'Via Framer',
            'mailingLists': 'cm8ay9cic00x70kjv0bd34k66'
        }

        # Send the registration request
        encoded_data = urllib.parse.urlencode(form_data)
        response = session.post(loops_url, data=encoded_data, impersonate="chrome120")

        if response.status_code != 200:
            raise Exception(f"Failed to register for Two AI: {response.status_code} - {response.text}")

        # Wait for the confirmation email and extract the API key
        max_attempts = 5 
        attempt = 0
        api_key = None
        wait_time = 2 

        while attempt < max_attempts and not api_key:
            messages = provider.get_messages()

            for message in messages:
                # Check if this is likely the confirmation email based on subject and sender
                subject = message.get('subject', '')
                sender = ''

                # Try to get the sender from different possible fields
                if 'from' in message:
                    if isinstance(message['from'], dict):
                        sender = message['from'].get('address', '')
                    else:
                        sender = str(message['from'])
                elif 'sender' in message:
                    if isinstance(message['sender'], dict):
                        sender = message['sender'].get('address', '')
                    else:
                        sender = str(message['sender'])

                # Look for keywords in the subject that indicate this is the confirmation email
                subject_match = any(keyword in subject.lower() for keyword in
                                   ['welcome', 'confirm', 'verify', 'api', 'key', 'sutra', 'two.ai', 'loops'])

                # Look for keywords in the sender that indicate this is from Two AI or Loops
                sender_match = any(keyword in sender.lower() for keyword in
                                  ['two.ai', 'sutra', 'loops.so', 'loops', 'no-reply', 'noreply'])

                is_confirmation = subject_match or sender_match

                if is_confirmation:
                    pass
                # Try to get the message content from various possible fields
                content = None

                # Check for body field (seen in the debug output)
                if 'body' in message:
                    content = message['body']
                # Check for content.text field
                elif 'content' in message and 'text' in message['content']:
                    content = message['content']['text']
                # Check for html field
                elif 'html' in message:
                    content = message['html']
                # Check for text field
                elif 'text' in message:
                    content = message['text']

                if not content:
                    continue
                # Look for the API key pattern in the email content
                # First, try to find the API key directly
                api_key_match = re.search(r'sutra_[A-Za-z0-9]{60,70}', content)

                # If not found, try looking for the key with the label
                if not api_key_match:
                    key_section_match = re.search(r'🔑 SUTRA API Key\s*([^\s]+)', content)
                    if key_section_match:
                        api_key_match = re.search(r'(sutra_[A-Za-z0-9]+)', key_section_match.group(1))

                # If still not found, try a more general pattern
                if not api_key_match:
                    api_key_match = re.search(r'sutra_\S+', content)

                if api_key_match:
                    api_key = api_key_match.group(0)
                    break
            if not api_key:
                attempt += 1
                time.sleep(wait_time)
        if not api_key:
            raise Exception("Failed to get API key from confirmation email")
        return api_key

    def __init__(
        self,
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

        # Use cached API key or generate new one if needed
        api_key = self.get_cached_api_key()

        self.url = "https://api.two.ai/v2/chat/completions"  # API endpoint
        self.headers = {
            'User-Agent': LitAgent().random(),
            'Accept': 'text/event-stream',  # For streaming responses
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',  # Using Bearer token authentication
            'Origin': 'https://chat.two.ai',
            'Referer': 'https://api.two.app/'
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
            "stream": stream,
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
                    timeout=self.timeout,
                    impersonate="chrome110"
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

                # Use sanitize_stream for SSE processing
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None), # Pass byte iterator
                    intro_value="data:",
                    to_json=True,     # Stream sends JSON
                    skip_markers=["[DONE]"],
                    content_extractor=self._twoai_extractor, # Use the specific extractor
                    yield_raw_on_error=False # Skip non-JSON lines or lines where extractor fails
                )

                for content_chunk in processed_stream:
                    # content_chunk is the string extracted by _twoai_extractor
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

        effective_stream = stream if stream is not None else True
        return for_stream() if effective_stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = True,
        optimizer: str = None,
        conversationally: bool = False,
        online_search: bool = True,
        image_path: str = None,
    ) -> str:
        effective_stream = stream if stream is not None else True

        def for_stream_chat():
            # ask() yields dicts when raw=False (default for chat)
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
                yield self.get_message(response_dict) # get_message expects dict

        def for_non_stream_chat():
             # ask() returns a dict when stream=False
            response_dict = self.ask(
                prompt,
                stream=False, # Ensure ask returns dict
                raw=False,
                optimizer=optimizer,
                conversationally=conversationally,
                online_search=online_search,
                image_path=image_path,
            )
            return self.get_message(response_dict) # get_message expects dict

        return for_stream_chat() if effective_stream else for_non_stream_chat()

    def get_message(self, response: dict) -> str:
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response.get("text", "") # Use .get for safety


if __name__ == "__main__":
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)

    for model in TwoAI.AVAILABLE_MODELS:
        try:
            test_ai = TwoAI(model=model, timeout=60)
            # Test stream first
            response_stream = test_ai.chat("Say 'Hello' in one word", stream=True)
            response_text = ""
            print(f"\r{model:<50} {'Streaming...':<10}", end="", flush=True)
            for chunk in response_stream:
                response_text += chunk
                # Optional: print chunks as they arrive for visual feedback
                # print(chunk, end="", flush=True) 
            
            if response_text and len(response_text.strip()) > 0:
                status = "✓"
                # Clean and truncate response
                clean_text = response_text.strip() # Already decoded in get_message
                display_text = clean_text[:50] + "..." if len(clean_text) > 50 else clean_text
            else:
                status = "✗ (Stream)"
                display_text = "Empty or invalid stream response"
            print(f"\r{model:<50} {status:<10} {display_text}")
            
            # Optional: Add non-stream test if needed, but stream test covers basic functionality
            # print(f"\r{model:<50} {'Non-Stream...':<10}", end="", flush=True)
            # response_non_stream = test_ai.chat("Say 'Hi' again", stream=False)
            # if not response_non_stream or len(response_non_stream.strip()) == 0:
            #      print(f"\r{model:<50} {'✗ (Non-Stream)':<10} Empty non-stream response")


        except Exception as e:
            print(f"\r{model:<50} {'✗':<10} {str(e)}")
