import os
import base64
import random
import json
from typing import Union, Dict, Any, Optional, Generator
from urllib import response

from curl_cffi import CurlError
from curl_cffi.requests import Session
from curl_cffi.const import CurlHttpVersion

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent

class GizAI(Provider):
    """
    A class to interact with the GizAI API.
    
    Attributes:
        system_prompt (str): The system prompt to define the assistant's role.
        
    Examples:
        >>> from webscout.Provider.GizAI import GizAI
        >>> ai = GizAI()
        >>> response = ai.chat("What's the weather today?")
        >>> print(response)
    """
    required_auth = False
    AVAILABLE_MODELS = [
        "azure-gpt-4-1",
        "chat-gpt4",
        "chat-grok-2",
        "chat-o4-mini",
        "chat-o4-mini-high",
        "chat-o4-mini-medium",
        "claude-haiku",
        "claude-sonnet",
        "deepinfra-llama-4-maverick",
        "deepseek",
        "deepseek-r1-distill-llama-70b",
        "gemini-2.0-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gpt-4-1-mini",
        "gpt-4-1-nano",
        "gpt-4o-image",
        "hyperbolic-deepseek-r1",
        "llama-3-70b",
        "llama-4-scout",
        "o3",
        "phi-4",
        "qwq-32b"
    ]
    
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
        model: str = "gemini-2.0-flash-lite",
        system_prompt: str = "You are a helpful assistant."
    ):
        """Initializes the GizAI API client."""
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")
            
        self.api_url = "https://app.giz.ai/api/data/users/inferenceServer.infer"
        
        # Initialize LitAgent for user-agent generation
        self.agent = LitAgent()
        
        # Initialize curl_cffi Session
        self.session = Session()
        
        # Set up the headers
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "user-agent": self.agent.random(),
            "origin": "https://app.giz.ai",
            "referer": "https://app.giz.ai/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin"
        }
        
        # Update session headers and proxies
        self.session.headers.update(self.headers)
        self.session.proxies = proxies
        
        # Store configuration
        self.system_prompt = system_prompt
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
    
    def _generate_id(self, length: int = 21) -> str:
        """Generates a random URL-safe base64 string."""
        random_bytes = os.urandom(length * 2)  # Generate more bytes initially
        b64_encoded = base64.urlsafe_b64encode(random_bytes).decode('utf-8')
        return b64_encoded[:length]
    
    def _get_random_ip(self) -> str:
        """Generates a random IPv4 address string."""
        return f"{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}"
    
    def ask(
        self,
        prompt: str,
        stream: bool = False,  # Parameter kept for compatibility but not used
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Dict[str, Any]:
        """
        Sends a prompt to the GizAI API and returns the response.
        
        Args:
            prompt (str): The prompt to send to the API.
            stream (bool): Not supported by GizAI, kept for compatibility.
            raw (bool): Whether to return the raw response.
            optimizer (str): Optimizer to use for the prompt.
            conversationally (bool): Whether to generate the prompt conversationally.
            
        Returns:
            Dict[str, Any]: The API response.
            
        Examples:
            >>> ai = GizAI()
            >>> response = ai.ask("Tell me a joke!")
        """
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise Exception(f"Optimizer is not one of {self.__available_optimizers}")
        
        # Generate random IDs for request
        instance_id = self._generate_id()
        subscribe_id = self._generate_id()
        x_forwarded_for = self._get_random_ip()
        
        # Set up request body - GizAI doesn't support streaming
        request_body = {
            "model": "chat",
            "baseModel": self.model, # Use the specific model ID here
            "input": {
                "messages": [{
                    "type": "human",
                    "content": conversation_prompt
                }],
                "mode": "plan"
            },
            "noStream": True,
            "instanceId": instance_id,
            "subscribeId": subscribe_id
        }
        
        # Combine default headers with the dynamic x-forwarded-for header
        request_headers = {**self.headers, "x-forwarded-for": x_forwarded_for}
        
        try:
            # Use curl_cffi session post with impersonate
            response = self.session.post(
                self.api_url,
                headers=request_headers,
                json=request_body,
                timeout=self.timeout,
                impersonate="chrome120",  # Use a common impersonation profile
                http_version=CurlHttpVersion.V2_0    # Use HTTP/2
            )
            response.raise_for_status()  # Check for HTTP errors
            
            # Process the response
            try:
                response_json = response.json()
                # GizAI responses have "status" and "output" fields
                if response_json.get("status") == "completed" and "output" in response_json:
                    content = response_json["output"]
                else:
                    content = ""
                    # Try to extract content from any available field that might contain the response
                    for key, value in response_json.items():
                        if isinstance(value, str) and len(value) > 10:
                            content = value
                            break
            except json.JSONDecodeError:
                # Handle case where response is not valid JSON
                content = response.text
            
            # Update conversation history
            self.last_response = {"text": content}
            self.conversation.update_chat_history(prompt, content)
            
            return self.last_response if not raw else content
        
        except CurlError as e:
            raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {str(e)}")
        except Exception as e:
            error_text = getattr(e, 'response', None) and getattr(e.response, 'text', '')
            raise exceptions.FailedToGenerateResponseError(f"Request failed ({type(e).__name__}): {str(e)} - {error_text}")
    
    def chat(
        self,
        prompt: str,
        stream: bool = False,  # Parameter kept for compatibility but not used
        optimizer: str = None,
        conversationally: bool = False,
    ) -> 'Generator[str, None, None]':
        """
        Generates a response from the GizAI API.
        
        Args:
            prompt (str): The prompt to send to the API.
            stream (bool): Not supported by GizAI, kept for compatibility.
            optimizer (str): Optimizer to use for the prompt.
            conversationally (bool): Whether to generate the prompt conversationally.
            
        Returns:
            Generator[str, None, None]: The API response text as a generator.
            
        Examples:
            >>> ai = GizAI()
            >>> response = ai.chat("What's the weather today?")
        """
        # GizAI doesn't support streaming, so ignore the stream parameter
        response_data = self.ask(
            prompt, stream=False, raw=False,
            optimizer=optimizer, conversationally=conversationally
        )
        result = self.get_message(response_data)
        if stream:
            yield result
        else:
            return result
    
    def get_message(self, response: Union[dict, str]) -> str:
        """
        Extracts the message from the API response.
        
        Args:
            response (Union[dict, str]): The API response.
            
        Returns:
            str: The message content.
            
        Examples:
            >>> ai = GizAI()
            >>> response = ai.ask("Tell me a joke!")
            >>> message = ai.get_message(response)
        """
        if isinstance(response, str):
            return response
        assert isinstance(response, dict), "Response should be either dict or str"
        return response.get("text", "")

if __name__ == "__main__":
    ai = GizAI()
    response = ai.chat("Hello, how are you?", stream=True)
    for chunk in response:
        print(chunk, end="", flush=True)