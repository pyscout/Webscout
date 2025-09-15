from curl_cffi.requests import Session
from curl_cffi import CurlError
import json
import re
from typing import Any, Dict, Optional, Generator, Union, List

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent


class DeepSeekAssistant(Provider):
    """
    A class to interact with the DeepSeek Assistant API.
    
    This provider interfaces with the deepseek-assistant.com API to provide
    AI chat completions using the V3 model.
    
    Attributes:
        AVAILABLE_MODELS (list): List of available models for the provider.
    
    Examples:
        >>> from webscout.Provider.deepseek_assistant import DeepSeekAssistant
        >>> ai = DeepSeekAssistant()
        >>> response = ai.chat("What's the weather today?")
        >>> print(response)
        'I can help you with weather information...'
    """

    AVAILABLE_MODELS = ["V3 model", "R1 model"]
    required_auth = False
    @staticmethod
    def _deepseek_assistant_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        """Extracts content from DeepSeek Assistant stream JSON objects."""
        if isinstance(chunk, dict):
            return chunk.get("choices", [{}])[0].get("delta", {}).get("content")
        return None

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
        model: str = "V3 model",
        system_prompt: str = "You are a helpful assistant.",
        browser: str = "chrome"
    ):
        """
        Initializes the DeepSeek Assistant API client.
        
        Args:
            is_conversation (bool): Whether the provider is in conversation mode.
            max_tokens (int): Maximum number of tokens to sample.
            timeout (int): Timeout for API requests.
            intro (str): Introduction message for the conversation.
            filepath (str): Filepath for storing conversation history.
            update_file (bool): Whether to update the conversation history file.
            proxies (dict): Proxies for the API requests.
            history_offset (int): Offset for conversation history.
            act (str): Act for the conversation.
            model (str): The model to use for completions.
            system_prompt (str): The system prompt to define the assistant's role.
            browser (str): Browser type for fingerprinting.
        
        Examples:
            >>> ai = DeepSeekAssistant(model="V3 model")
            >>> print(ai.model)
            'V3 model'
        """
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        self.url = "https://deepseek-assistant.com/api/search-stream-deep-chat-testing.php"

        # Initialize LitAgent for user agent generation
        self.agent = LitAgent()
        self.fingerprint = self.agent.generate_fingerprint(browser)

        # Headers based on the JavaScript code
        self.headers = {
            "accept": "*/*",
            "accept-language": "id-ID,id;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/json",
            "cookie": "click_id=OS3Hz0E1yKfu4YnZNwedESMEdKEgMTzL; organic_user_deepseek_assistant_ch=%7B%22pixel%22%3A%22OS3Hz0E1yKfu4YnZNwedESMEdKEgMTzL%22%2C%22cc%22%3A%22ID%22%2C%22channel%22%3A%22organic_flag%22%7D",
            "origin": "https://deepseek-assistant.com",
            **self.fingerprint

        }

        # Initialize curl_cffi Session
        self.session = Session()
        self.session.headers.update(self.headers)
        self.session.proxies = proxies
        
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

    def refresh_identity(self, browser: str = None):
        """
        Refreshes the browser identity fingerprint.

        Args:
            browser: Specific browser to use for the new fingerprint
        """
        browser = browser or self.fingerprint.get("browser_type", "chrome")
        self.fingerprint = self.agent.generate_fingerprint(browser)

        # Update user-agent header with new fingerprint
        self.headers.update({
            "user-agent": self.fingerprint.get("user_agent", self.headers["user-agent"])
        })

        # Update session headers
        self.session.headers.update(self.headers)

        return self.fingerprint

    def _parse_chat_response(self, input_text: str) -> str:
        """
        Parses the chat response from the API, similar to the JavaScript parseChatResponse method.
        
        Args:
            input_text (str): The raw response text from the API
            
        Returns:
            str: The parsed content from the response
        """
        lines = input_text.strip().split("\n")
        result = ""
        
        for line in lines:
            trimmed_line = line.strip()
            if trimmed_line.startswith("data: {") and trimmed_line.endswith("}"):
                try:
                    # Extract JSON from the line
                    json_start = trimmed_line.find("{")
                    if json_start != -1:
                        json_str = trimmed_line[json_start:]
                        parsed_data = json.loads(json_str)
                        
                        # Extract content from the parsed data
                        content = parsed_data.get("choices", [{}])[0].get("delta", {}).get("content")
                        if content is not None:
                            result += content
                except (json.JSONDecodeError, KeyError, IndexError):
                    # Skip malformed JSON or missing keys
                    continue
        
        return result.strip()

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator]:
        """
        Sends a prompt to the DeepSeek Assistant API and returns the response.

        Args:
            prompt (str): The prompt to send to the API.
            stream (bool): Whether to stream the response.
            raw (bool): Whether to return the raw response.
            optimizer (str): Optimizer to use for the prompt.
            conversationally (bool): Whether to generate the prompt conversationally.

        Returns:
            Union[Dict[str, Any], Generator]: The API response.

        Examples:
            >>> ai = DeepSeekAssistant()
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
                raise Exception(f"Optimizer is not one of {self.__available_optimizers}")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},  # Add system role
                {"role": "user", "content": conversation_prompt}
            ]
        }

        def for_stream():
            streaming_text = ""
            try:
                response = self.session.post(
                    self.url,
                    data=json.dumps(payload),
                    stream=True,
                    timeout=self.timeout,
                    impersonate="chrome110"
                )
                response.raise_for_status()

                # Use sanitize_stream to process the response
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None),
                    intro_value="data:",
                    to_json=True,
                    skip_markers=["[DONE]"],
                    content_extractor=self._deepseek_assistant_extractor,
                    yield_raw_on_error=False
                )

                for content_chunk in processed_stream:
                    if content_chunk and isinstance(content_chunk, str):
                        streaming_text += content_chunk
                        resp = dict(text=content_chunk)
                        yield resp if not raw else content_chunk

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
                response = self.session.post(
                    self.url,
                    data=json.dumps(payload),
                    timeout=self.timeout,
                    impersonate="chrome110"
                )
                response.raise_for_status()

                # Parse the response using the custom parser
                content = self._parse_chat_response(response.text)

                self.last_response = {"text": content}
                self.conversation.update_chat_history(prompt, content)
                return self.last_response if not raw else content

            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}") from e
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
        """
        Initiates a chat with the DeepSeek Assistant API using the provided prompt.

        Args:
            prompt (str): The prompt to send to the API.
            stream (bool): Whether to stream the response.
            optimizer (str): Optimizer to use for the prompt.
            conversationally (bool): Whether to generate the prompt conversationally.

        Returns:
            Union[str, Generator[str, None, None]]: The chat response.

        Examples:
            >>> ai = DeepSeekAssistant()
            >>> response = ai.chat("Tell me a joke")
            >>> print(response)
            'Why did the scarecrow win an award? Because he was outstanding in his field!'
        """
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
        """
        Extracts the message content from the API response.

        Args:
            response (dict): The API response.

        Returns:
            str: The message content.

        Examples:
            >>> ai = DeepSeekAssistant()
            >>> response = ai.ask("Tell me a joke!")
            >>> message = ai.get_message(response)
            >>> print(message)
            'Why did the scarecrow win an award? Because he was outstanding in his field!'
        """
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response["text"]


if __name__ == "__main__":
    # Test the provider
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)

    for model in DeepSeekAssistant.AVAILABLE_MODELS:
        try:
            test_ai = DeepSeekAssistant(model=model, timeout=60)
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
