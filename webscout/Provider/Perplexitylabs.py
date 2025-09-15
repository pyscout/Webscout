import json
import time
import random
from threading import Event
from curl_cffi import requests
from typing import Dict, Any, Union, Generator

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts
from webscout.AIbase import Provider
from webscout import exceptions

API_URL = "https://www.perplexity.ai/socket.io/"

class PerplexityLabs(Provider):
    """
    A client for interacting with the Perplexity AI Labs API.
    """
    required_auth = False
    AVAILABLE_MODELS = [
        "sonar-pro", 
        "sonar", 
        "sonar-reasoning-pro", 
        "sonar-reasoning"
    ]
    
    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 2048,
        timeout: int = 60,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "r1-1776",
        connection_timeout: float = 10.0,
        max_retries: int = 3,
    ):
        """
        Initialize the Perplexity client.
        
        Args:
            is_conversation: Whether to maintain conversation context
            max_tokens: Maximum token limit for responses
            timeout: Response timeout in seconds
            intro: Conversation intro/system prompt
            filepath: Path for conversation history persistence
            update_file: Whether to update the conversation file
            proxies: Optional proxy configuration
            history_offset: History truncation limit
            act: Persona to use for responses
            model: Default model to use
            connection_timeout: Maximum time to wait for connection
            max_retries: Number of connection retry attempts
        """
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")
            
        self.model = model
        self.connection_timeout = connection_timeout
        self.timeout = timeout 
        self.max_retries = max_retries
        self.connected = Event()
        self.last_answer = None
        
        # Initialize session with headers matching the working example
        self.headers = {
            "Origin": "https://labs.perplexity.ai",
            "Referer": "https://labs.perplexity.ai/",
        }
        self.session = requests.Session(impersonate="chrome")
        
        # Apply proxies if provided
        if proxies:
            self.session.proxies.update(proxies)
        
        # Set up conversation handling
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens

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
            
        # Initialize connection
        self._initialize_connection()

    def _initialize_connection(self) -> None:
        """Initialize the connection to Perplexity using polling approach"""
        for attempt in range(1, self.max_retries + 1):
            try:
                # Get a session ID via polling
                self.timestamp = format(random.getrandbits(32), '08x')
                poll_url = f'{API_URL}?EIO=4&transport=polling&t={self.timestamp}'
                
                response = self.session.get(poll_url, headers=self.headers)
                if response.status_code != 200:
                    if attempt == self.max_retries:
                        raise ConnectionError(f"Failed to get session ID: HTTP {response.status_code}")
                    continue
                
                # Extract the session ID
                try:
                    text = response.text
                    if not text.startswith("0"):
                        raise ConnectionError("Invalid response format")
                    self.sid = json.loads(text[1:])['sid']
                except (json.JSONDecodeError, KeyError) as e:
                    if attempt == self.max_retries:
                        raise ConnectionError(f"Failed to parse session ID: {e}")
                    continue
                
                # Authenticate the session
                self.auth_url = f'{API_URL}?EIO=4&transport=polling&t={self.timestamp}&sid={self.sid}'
                post_data = '40{"jwt":"anonymous-ask-user"}'
                auth_response = self.session.post(self.auth_url, data=post_data, headers=self.headers)
                
                if auth_response.status_code != 200 or auth_response.text != 'OK':
                    if attempt == self.max_retries:
                        raise ConnectionError("Authentication failed")
                    continue
                
                # Get additional response to complete handshake
                get_response = self.session.get(self.auth_url, headers=self.headers)
                if get_response.status_code != 200:
                    if attempt == self.max_retries:
                        raise ConnectionError("Failed to complete authentication handshake")
                    continue
                
                # Connection successful - using polling instead of WebSocket
                self.connected.set()
                return
                
            except Exception as e:
                if attempt == self.max_retries:
                    raise exceptions.FailedToGenerateResponseError(f"Failed to connect: {e}")
            
            # If we get here, the attempt failed, wait before retrying
            if attempt < self.max_retries:
                retry_delay = 2 ** attempt  # Exponential backoff
                time.sleep(retry_delay)
        
        raise exceptions.FailedToGenerateResponseError("Failed to connect to Perplexity after multiple attempts")

    def _send_query_polling(self, message_data):
        """Send query using polling approach"""
        payload = '42' + json.dumps(["perplexity_labs", message_data])
        response = self.session.post(self.auth_url, data=payload, headers=self.headers, timeout=10)
        return response.status_code == 200
    
    def _poll_for_response(self, timeout_seconds):
        """Poll for response using the polling approach"""
        start_time = time.time()
        last_message = 0
        full_output = ""
        
        while True:
            if time.time() - start_time > timeout_seconds:
                if last_message == 0:
                    raise exceptions.FailedToGenerateResponseError("Response timed out")
                else:
                    # Return partial response if we got some content
                    yield {"text": "", "final": True, "full_output": full_output}
                    return
            
            try:
                poll_response = self.session.get(self.auth_url, headers=self.headers, timeout=3)
                
                if poll_response.status_code == 400:
                    # Session expired, try to return what we have
                    if full_output:
                        yield {"text": "", "final": True, "full_output": full_output}
                        return
                    else:
                        raise exceptions.FailedToGenerateResponseError("Session expired")
                
                if poll_response.status_code != 200:
                    time.sleep(0.5)
                    continue
                
                response_text = poll_response.text
                
                # Handle heartbeat
                if response_text == '2':
                    try:
                        self.session.post(self.auth_url, data='3', headers=self.headers, timeout=3)
                    except:
                        pass
                    continue
                
                # Handle data messages containing output
                if '42[' in response_text and 'output' in response_text:
                    try:
                        # Find the JSON part more reliably
                        start = response_text.find('42[')
                        if start != -1:
                            # Find the end of this JSON message
                            bracket_count = 0
                            json_start = start + 2
                            json_end = json_start
                            
                            for j, char in enumerate(response_text[json_start:]):
                                if char == '[':
                                    bracket_count += 1
                                elif char == ']':
                                    bracket_count -= 1
                                    if bracket_count == 0:
                                        json_end = json_start + j + 1
                                        break
                            
                            json_str = response_text[json_start:json_end]
                            parsed_data = json.loads(json_str)
                            
                            if len(parsed_data) > 1 and isinstance(parsed_data[1], dict):
                                data = parsed_data[1]
                                
                                # Handle error responses
                                if data.get("status") == "failed":
                                    error_message = data.get("text", "Unknown API error")
                                    raise exceptions.FailedToGenerateResponseError(f"API Error: {error_message}")
                                
                                # Handle normal responses
                                if "output" in data:
                                    current_output = data["output"]
                                    if len(current_output) > last_message:
                                        delta = current_output[last_message:]
                                        last_message = len(current_output)
                                        full_output = current_output
                                        yield {"text": delta, "final": data.get("final", False), "full_output": full_output}
                                    
                                    if data.get("final", False):
                                        return
                                        
                    except (json.JSONDecodeError, IndexError, KeyError) as e:
                        # Continue on parsing errors
                        pass
                
            except Exception as e:
                # Handle timeout and other errors more gracefully
                if "timeout" in str(e).lower():
                    continue
                time.sleep(0.5)
                continue
            
            time.sleep(0.5)
    
    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        model: str = None
    ) -> Union[Dict[str, Any], Generator]:
        """
        Send a query to Perplexity AI and get a response.
        
        Args:
            prompt: The question to ask
            stream: Whether to stream the response
            raw: Return raw response format
            optimizer: Optimizer function to apply to prompt
            conversationally: Use conversation context
            model: Override the model to use
            
        Returns:
            If stream=True: Generator yielding response updates
            If stream=False: Final response dictionary
        """
        # Check if connection is still active and reconnect if needed
        if not self.connected.is_set():
            self._initialize_connection()
        
        # Use specified model or default
        use_model = model or self.model
        if use_model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {use_model}. Choose from: {', '.join(self.AVAILABLE_MODELS)}")
        
        # Process prompt with conversation and optimizers
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise Exception(f"Optimizer is not one of {self.__available_optimizers}")
        
        # Send the query using polling approach
        message_data = {
            "version": "2.18",
            "source": "default",
            "model": use_model,
            "messages": [{"role": "user", "content": conversation_prompt}],
        }
        
        # Send query
        if not self._send_query_polling(message_data):
            raise exceptions.FailedToGenerateResponseError("Failed to send query")
        
        def for_stream():
            """Handle streaming responses using polling"""
            full_text = ""
            for response_chunk in self._poll_for_response(self.timeout):
                if response_chunk["text"]:
                    full_text += response_chunk["text"]
                    yield dict(text=response_chunk["text"]) if raw else dict(text=response_chunk["text"])
                
                if response_chunk["final"]:
                    self.conversation.update_chat_history(prompt, full_text)
                    return
        
        def for_non_stream():
            """Handle non-streaming responses using polling"""
            full_text = ""
            for response_chunk in self._poll_for_response(self.timeout):
                if response_chunk["text"]:
                    full_text += response_chunk["text"]
                
                if response_chunk["final"]:
                    self.conversation.update_chat_history(prompt, full_text)
                    return dict(text=full_text) if raw else dict(text=full_text)
            
            # If we get here, no final response was received
            if full_text:
                self.conversation.update_chat_history(prompt, full_text)
                return dict(text=full_text) if raw else dict(text=full_text)
            else:
                raise exceptions.FailedToGenerateResponseError("No response received")
        
        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        model: str = None
    ) -> Union[str, Generator[str, None, None]]:
        """
        Send a query and get just the text response.
        
        Args:
            prompt: The question to ask
            stream: Whether to stream the response
            optimizer: Optimizer function to apply to prompt
            conversationally: Use conversation context
            model: Override the model to use
            
        Returns:
            If stream=True: Generator yielding text chunks
            If stream=False: Complete response text
        """
        def for_stream():
            for response in self.ask(
                prompt, 
                stream=True, 
                optimizer=optimizer, 
                conversationally=conversationally,
                model=model
            ):
                yield self.get_message(response)
                
        def for_non_stream():
            return self.get_message(
                self.ask(
                    prompt, 
                    stream=False, 
                    optimizer=optimizer, 
                    conversationally=conversationally,
                    model=model
                )
            )
            
        return for_stream() if stream else for_non_stream()

    def get_message(self, response: dict) -> str:
        """Extract text from response dictionary"""
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response["text"]


if __name__ == "__main__":
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)
    
    # Test all available models
    working = 0
    total = len(PerplexityLabs.AVAILABLE_MODELS)
    
    for model in PerplexityLabs.AVAILABLE_MODELS:
        try:
            test_ai = PerplexityLabs(model=model, timeout=30, connection_timeout=5.0)
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
            print(f"\r{model:<50} {'✗':<10} {str(e)[:80]}")
