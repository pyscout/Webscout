from curl_cffi.requests import Session
from curl_cffi import CurlError
import re
from typing import Union, Any, Dict, Optional, Generator
import secrets


from webscout.AIutel import Optimizers, Conversation, AwesomePrompts, sanitize_stream # Import sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions

class JadveOpenAI(Provider):
    """
    A class to interact with the OpenAI API through jadve.com using the streaming endpoint.
    """
    required_auth = False
    AVAILABLE_MODELS = ["gpt-5-mini", "claude-3-5-haiku-20241022"]

    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 600,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "gpt-5-mini",
        system_prompt: str = "You are a helpful AI assistant." # Note: system_prompt is not used by this API
    ):
        """
        Initializes the JadveOpenAI client.

        Args:
            is_conversation (bool, optional): Enable conversational mode. Defaults to True.
            max_tokens (int, optional): Maximum tokens for generation. Defaults to 600.
            timeout (int, optional): HTTP request timeout in seconds. Defaults to 30.
            intro (str, optional): Introductory prompt text. Defaults to None.
            filepath (str, optional): Path to conversation history file. Defaults to None.
            update_file (bool, optional): Whether to update the conversation history file. Defaults to True.
            proxies (dict, optional): Proxies for HTTP requests. Defaults to {}.
            history_offset (int, optional): Limit for conversation history. Defaults to 10250.
            act (str|int, optional): Act key for AwesomePrompts. Defaults to None.
            model (str, optional): AI model to be used. Defaults to "gpt-4o-mini".
            system_prompt (str, optional): System prompt text. Defaults to "You are a helpful AI assistant."
        """
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        # Initialize curl_cffi Session
        self.session = Session()
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.api_endpoint = "https://ai-api.jadve.com/api/chat"
        self.stream_chunk_size = 64
        self.timeout = timeout
        self.last_response = {}
        self.model = model
        self.system_prompt = system_prompt

        # Headers for API requests
        self.headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9,en-IN;q=0.8",
            "content-type": "application/json",
            "dnt": "1",
            "origin": "https://jadve.com",
            "priority": "u=1, i",
            "referer": "https://jadve.com/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-gpc": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"
        }
        
        # Update curl_cffi session headers and proxies
        self.session.headers.update(self.headers)
        self.session.proxies = proxies # Assign proxies directly

        self.__available_optimizers = (
            method for method in dir(Optimizers)
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
    def _jadve_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        """Extracts content from the Jadve stream format '0:"..."'."""
        if isinstance(chunk, str):
            match = re.search(r'0:"(.*?)"(?=,|$)', chunk) # Look for 0:"...", possibly followed by comma or end of string
            if match:
                # Decode potential unicode escapes like \u00e9 and handle escaped quotes/backslashes
                content = match.group(1).encode().decode('unicode_escape')
                return content.replace('\\\\', '\\').replace('\\"', '"')
        return None

    def ask(
        self,
        prompt: str,
        stream: bool = False, # API supports streaming
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[dict, Generator[dict, None, None]]:
        """
        Chat with AI.

        Args:
            prompt (str): Prompt to be sent.
            stream (bool, optional): Flag for streaming response. Defaults to False.
            raw (bool, optional): Return raw content chunks. Defaults to False.
            optimizer (str, optional): Prompt optimizer name. Defaults to None.
            conversationally (bool, optional): Flag for conversational optimization. Defaults to False.
        Returns:
            dict or generator: A dictionary with the generated text or a generator yielding text chunks.
        """
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(conversation_prompt if conversationally else prompt)
            else:
                raise Exception(f"Optimizer is not one of {list(self.__available_optimizers)}")

        payload = {
            "id": secrets.token_hex(8),
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": conversation_prompt}]}
            ],
            "model": self.model,
            "botId": "",
            "chatId": "",
            "stream": True,
            "returnTokensUsage": True,
            "useTools": False
        }

        def for_stream():
            full_response_text = "" # Initialize outside try block
            try:
                # Use curl_cffi session post with impersonate
                response = self.session.post(
                    self.api_endpoint, 
                    # headers are set on the session
                    json=payload, 
                    stream=True, 
                    timeout=self.timeout,
                    # proxies are set on the session
                    impersonate="chrome120" # Use a common impersonation profile
                )
                response.raise_for_status() # Check for HTTP errors

                # Use sanitize_stream
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None), # Pass byte iterator
                    intro_value=None, # No simple prefix
                    to_json=False,    # Content is text after extraction
                    content_extractor=self._jadve_extractor, # Use the specific extractor
                    yield_raw_on_error=True,
                    raw=raw
                )

                for content_chunk in processed_stream:
                    if raw:
                        if content_chunk and isinstance(content_chunk, str):
                            full_response_text += content_chunk
                        yield content_chunk
                    else:
                        if content_chunk and isinstance(content_chunk, str):
                            full_response_text += content_chunk
                            resp = {"text": content_chunk}
                            yield resp

                # Update history after stream finishes
                self.last_response = {"text": full_response_text}
                self.conversation.update_chat_history(prompt, full_response_text)

            except CurlError as e: # Catch CurlError
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}") from e
            except Exception as e: # Catch other potential exceptions (like HTTPError)
                err_text = getattr(e, 'response', None) and getattr(e.response, 'text', '')
                raise exceptions.FailedToGenerateResponseError(f"Failed to generate response ({type(e).__name__}): {e} - {err_text}") from e

        def for_non_stream():
            collected_text = ""
            try:
                for chunk_data in for_stream():
                    if raw:
                        if isinstance(chunk_data, str):
                            collected_text += chunk_data
                    else:
                        if isinstance(chunk_data, dict) and "text" in chunk_data:
                            collected_text += chunk_data["text"]
            except Exception as e:
                if not collected_text:
                    raise exceptions.FailedToGenerateResponseError(f"Failed to get non-stream response: {str(e)}") from e
            # last_response and history are updated within for_stream
            return collected_text if raw else self.last_response

        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        raw: bool = False,
    ) -> Union[str, Generator[str, None, None]]:
        """
        Generate a chat response (string). 

        Args:
            prompt (str): Prompt to be sent.
            stream (bool, optional): Flag for streaming response. Defaults to False.
            optimizer (str, optional): Prompt optimizer name. Defaults to None.
            conversationally (bool, optional): Flag for conversational optimization. Defaults to False.
            raw (bool, optional): Return raw response. Defaults to False.
        Returns:
            str or generator: Generated response string or generator yielding response chunks.
        """
        def for_stream_chat():
            gen = self.ask(
                prompt, stream=True, raw=raw,
                optimizer=optimizer, conversationally=conversationally
            )
            for response in gen:
                if raw:
                    yield response
                else:
                    yield self.get_message(response)

        def for_non_stream_chat():
            response_data = self.ask(
                prompt, stream=False, raw=raw,
                optimizer=optimizer, conversationally=conversationally
            )
            if raw:
                return response_data if isinstance(response_data, str) else str(response_data)
            return self.get_message(response_data)

        return for_stream_chat() if stream else for_non_stream_chat()

    def get_message(self, response: dict) -> str:
        """
        Retrieves message from the response.

        Args:
            response (dict): Response from the ask() method.
        Returns:
            str: Extracted text.
        """
        assert isinstance(response, dict), "Response should be of dict data-type only"
        # Extractor handles formatting
        return response.get("text", "")

if __name__ == "__main__":
    for model in JadveOpenAI.AVAILABLE_MODELS:
        ai = JadveOpenAI(model=model)    
        response = ai.chat("hi")
        print(f"Model: {model}")
        print(response)
        print("-" * 50)
    # for chunk in response:
    #     print(chunk, end="", flush=True)
