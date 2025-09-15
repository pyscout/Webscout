from typing import Optional, Union, Any, Dict, Generator, List
from uuid import uuid4
import json
import re
import random
from curl_cffi import CurlError
from curl_cffi.requests import Session
from curl_cffi.const import CurlHttpVersion

from webscout.AIutel import sanitize_stream
from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent

class ChatSandbox(Provider):
    """
    Sends a chat message to the specified model via the chatsandbox API.

    This provider allows you to interact with various AI models through the chatsandbox.com
    interface, supporting different models/models like OpenAI, DeepSeek, Llama, etc.

    Attributes:
        model (str): The model to chat with (e.g., "openai", "deepseek", "llama").

    Examples:
        >>> from webscout.Provider.chatsandbox import ChatSandbox
        >>> ai = ChatSandbox(model="openai")
        >>> response = ai.chat("Hello, how are you?")
        >>> print(response)
        'I'm doing well, thank you for asking! How can I assist you today?'
    """
    required_auth = False
    AVAILABLE_MODELS = ["openai", "deepseek", "llama", "gemini", "mistral-large", "deepseek-r1", "deepseek-r1-full", "gemini-thinking", "openai-o1-mini", "llama", "mistral", "gemma-3"]


    def __init__(
        self,
        model: str = "openai",
        is_conversation: bool = True,
        max_tokens: int = 600,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
    ):
        """
        Initializes the ChatSandbox API with given parameters.

        Args:
            model (str): The model to chat with (e.g., "openai", "deepseek", "llama").
            is_conversation (bool): Whether the provider is in conversation mode.
            max_tokens (int): Maximum number of tokens to sample.
            timeout (int): Timeout for API requests.
            intro (str): Introduction message for the conversation.
            filepath (str): Filepath for storing conversation history.
            update_file (bool): Whether to update the conversation history file.
            proxies (dict): Proxies for the API requests.
            history_offset (int): Offset for conversation history.
            act (str): Act for the conversation.

        Examples:
            >>> ai = ChatSandbox(model="openai", system_prompt="You are a friendly assistant.")
            >>> print(ai.model)
            'openai'
        """
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        # Initialize curl_cffi Session
        self.session = Session()
        self.model = model
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.api_endpoint = "https://chatsandbox.com/api/chat"
        self.timeout = timeout
        self.last_response = {}

        # Initialize LitAgent for user agent generation
        self.agent = LitAgent()

        # Set up headers
        self.headers = {
            'authority': 'chatsandbox.com',
            'accept': '*/*',
            'accept-encoding': 'gzip, deflate, br',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://chatsandbox.com',
            'referer': f'https://chatsandbox.com/chat/{self.model}',
            'sec-ch-ua': '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': self.agent.random(),
            'dnt': '1',
            'sec-gpc': '1',
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

    @staticmethod
    def _chatsandbox_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        """Extracts content from the chatsandbox stream format."""
        if isinstance(chunk, str):
            try:
                data = json.loads(chunk)
                if isinstance(data, dict) and "reasoning_content" in data:
                    return data["reasoning_content"]
                return chunk
            except json.JSONDecodeError:
                return chunk
        return None

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator]:
        """
        Sends a prompt to the ChatSandbox API and returns the response.

        Args:
            prompt (str): The prompt to send to the API.
            stream (bool): Whether to stream the response.
            raw (bool): Whether to return the raw response.
            optimizer (str): Optimizer to use for the prompt.
            conversationally (bool): Whether to generate the prompt conversationally.

        Returns:
            Union[Dict[str, Any], Generator]: The API response.

        Examples:
            >>> ai = ChatSandbox()
            >>> response = ai.ask("Tell me a joke!")
            >>> print(response)
            {'text': 'Why did the scarecrow win an award? Because he was outstanding in his field!'}
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

        # Prepare the payload
        payload = {
            "messages": [conversation_prompt],
            "character": self.model
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
                    impersonate="chrome120",  # Try a different impersonation profile
                    http_version=CurlHttpVersion.V1_1  # Force HTTP/1.1
                )
                if not response.ok:
                    raise exceptions.FailedToGenerateResponseError(
                        f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                    )
                
                streaming_response = ""
                # Use sanitize_stream with the custom extractor
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None),  # Pass byte iterator
                    intro_value=None,  # No simple prefix to remove here
                    to_json=False,     # Content is not JSON
                    content_extractor=self._chatsandbox_extractor  # Use the specific extractor
                )

                for content_chunk in processed_stream:
                    if content_chunk and isinstance(content_chunk, str):
                        streaming_response += content_chunk
                        yield content_chunk if raw else dict(text=content_chunk)

                self.last_response.update(dict(text=streaming_response))
                self.conversation.update_chat_history(
                    prompt, self.get_message(self.last_response)
                )
            except CurlError as e:  # Catch CurlError
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}")
            except Exception as e:  # Catch other potential exceptions
                # Include the original exception type in the message for clarity
                raise exceptions.FailedToGenerateResponseError(f"An unexpected error occurred ({type(e).__name__}): {e}")

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
        optimizer: str = None,
        conversationally: bool = False,
    ) -> str:
        """
        Generates a response from the ChatSandbox API.

        Args:
            prompt (str): The prompt to send to the API.
            stream (bool): Whether to stream the response.
            optimizer (str): Optimizer to use for the prompt.
            conversationally (bool): Whether to generate the prompt conversationally.

        Returns:
            str: The API response.

        Examples:
            >>> ai = ChatSandbox()
            >>> response = ai.chat("What's the weather today?")
            >>> print(response)
            'I don't have real-time weather data, but I can help you find weather information online.'
        """
        def for_stream():
            for response in self.ask(
                prompt,
                stream=True,
                raw=False,
                optimizer=optimizer,
                conversationally=conversationally,
            ):
                yield response.get("text", "")

        if stream:
            return for_stream()
        else:
            return self.get_message(
                self.ask(
                    prompt,
                    stream=False,
                    raw=False,
                    optimizer=optimizer,
                    conversationally=conversationally,
                )
            )

    def get_message(self, response: Dict[str, Any]) -> str:
        """
        Extract the message from the API response.
        
        Args:
            response (Dict[str, Any]): The API response.
            
        Returns:
            str: The extracted message.
        """
        if not isinstance(response, dict):
            return str(response)
            
        raw_text = response.get("text", "")

        # Try to parse as JSON
        try:
            data = json.loads(raw_text)
            if isinstance(data, dict):
                # Check for different response formats
                if "reasoning_content" in data:
                    return data["reasoning_content"]
                elif "content" in data:
                    return data["content"]
                elif "message" in data:
                    return data["message"]
                elif "response" in data:
                    return data["response"]
                elif "text" in data:
                    return data["text"]
                # Return the whole JSON if no specific field is found
                return json.dumps(data, ensure_ascii=False)
        except json.JSONDecodeError:
            # If it's not JSON, return the raw text
            pass

        return raw_text.strip()

# --- Example Usage ---
if __name__ == "__main__":
    from rich import print
    # Ensure curl_cffi is installed
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)

    for model in ChatSandbox.AVAILABLE_MODELS:
        try:
            test_ai = ChatSandbox(model=model, timeout=60)
            response = test_ai.chat("Say 'Hello' in one word")
            response_text = response
            
            if response_text and len(response_text.strip()) > 0:
                status = "✓"
                # Truncate response if too long
                display_text = response_text.strip()[:50] + "..." if len(response_text.strip()) > 50 else response_text.strip()
            else:
                status = "✗"
                display_text = "Empty or invalid response"
            print(f"{model:<50} {status:<10} {display_text}")
        except Exception as e:
            print(f"{model:<50} {'✗':<10} {str(e)}")