from curl_cffi import CurlError
from curl_cffi.requests import Session
from typing import Any, Dict, Optional, Generator, List, Union
import uuid

from sqlalchemy import True_
from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream # Import sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent


class ChatGLM(Provider):
    """
    A class to interact with the Z.AI Chat API (GLM-4.5).
    """

    url = "https://chat.z.ai"
    AVAILABLE_MODELS = [
        "0727-106B-API",
        "0727-360B-API"
    ]
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
        model: str = "0727-106B-API",
    ):
        """Initializes the Z.AI Chat API client."""
        self.session = Session()
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = {}
        self.headers = {
            'Accept-Language': 'en-US,en;q=0.9',
            'App-Name': 'chatglm',
            'Content-Type': 'application/json',
            'Origin': self.url,
            'User-Agent': LitAgent().random(),
            'X-App-Platform': 'pc',
            'X-App-Version': '0.0.1',
            'Accept': 'text/event-stream',
        }
        self.api_endpoint = f"{self.url}/api/chat/completions" 
        self.__available_optimizers = (
            method
            for method in dir(Optimizers)
            if callable(getattr(Optimizers, method)) and not method.startswith("__")
        )
        self.session.headers.update(self.headers)
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
        self.session.proxies = proxies
        self.model = model

    def _get_api_key(self):
        if not hasattr(self, 'api_key') or not self.api_key:
            response = self.session.get(f"{self.url}/api/v1/auths/")
            self.api_key = response.json().get("token")
        return self.api_key

    def _get_cookie(self):
        """Get authentication cookie from the site"""
        if not hasattr(self, 'cookie') or not self.cookie:
            response = self.session.get(f"{self.url}/")
            self.cookie = response.headers.get('Set-Cookie', '')
        return self.cookie


    # _zai_extractor removed; use extract_regexes in sanitize_stream


    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator[Any, None, None]]:
        """Chat with Z.AI API
        Args:
            prompt (str): Prompt to be sent.
            stream (bool, optional): Flag for streaming response. Defaults to False.
            raw (bool, optional): Stream back raw response as received. Defaults to False.
            optimizer (str, optional): Prompt optimizer name. Defaults to None.
            conversationally (bool, optional): Chat conversationally when using optimizer. Defaults to False.
            model (str, optional): Model name. Defaults to None.
        Returns:
            Union[Dict, Generator[Dict, None, None]]: Response generated
        """
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise exceptions.FailedToGenerateResponseError(
                    f"Optimizer is not one of {self.__available_optimizers}"
                )
        api_key = self._get_api_key()
        payload = {
            "stream": True,
            "model": self.model,
            "messages": [
                {"role": "user", "content": conversation_prompt}
            ],
            "params": {},
            "features": {"image_generation": False, "web_search": False, "auto_web_search": False, "preview_mode": True, "flags": [], "features": [{"type": "mcp", "server": "vibe-coding", "status": "hidden"}, {"type": "mcp", "server": "ppt-maker", "status": "hidden"}, {"type": "mcp", "server": "image-search", "status": "hidden"}], "enable_thinking": True},
            "actions": [],
            "tags": [],
            "chat_id": "local",
            "id": str(uuid.uuid4())
        }

        def for_stream():
            streaming_text = ""
            last_processed_content = ""
            try:
                cookie = self._get_cookie()
                response = self.session.post(
                    self.api_endpoint,
                    json=payload,
                    stream=True,
                    timeout=self.timeout,
                    impersonate="chrome120",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "x-fe-version": "prod-fe-1.0.70",
                    }
                )
                response.raise_for_status()

                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None),
                    intro_value="data:",
                    to_json=True,
                    extract_regexes=[
                        # Extract only the value of delta_content or edit_content (handle escaped quotes and newlines)
                        r'"delta_content"\s*:\s*"((?:[^"\\]|\\.)*)"',
                        r'"edit_content"\s*:\s*"((?:[^"\\]|\\.)*)"'
                    ],
                    skip_regexes=[
                        r'<details[^>]*>.*?</details>',
                        r'<summary>.*?</summary>',
                        r'<[^>]+>',
                        r'^\s*$'
                    ],
                    yield_raw_on_error=False,
                    raw=raw
                )
                for content_chunk in processed_stream:
                    if content_chunk and isinstance(content_chunk, str):
                        streaming_text += content_chunk
                        if raw:
                            yield content_chunk
                        else:
                            yield dict(text=content_chunk)
                        if raw:
                            yield content_chunk
                        else:
                            yield dict(text=content_chunk)

            except CurlError as e:
                raise exceptions.APIConnectionError(f"Request failed (CurlError): {e}") from e
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"An unexpected error occurred ({type(e).__name__}): {e}") from e
            finally:
                if streaming_text:
                    self.last_response.update(dict(text=streaming_text))
                    self.conversation.update_chat_history(
                        prompt, self.get_message(self.last_response)
                    )

        def for_non_stream():
            full_text = ""
            try:
                for chunk_data in for_stream():
                    if raw:
                        if isinstance(chunk_data, str):
                            full_text += chunk_data
                    else:
                        if isinstance(chunk_data, dict) and "text" in chunk_data:
                            full_text += chunk_data["text"]
            except Exception as e:
                if not full_text:
                    raise exceptions.FailedToGenerateResponseError(f"Failed to get non-stream response: {str(e)}") from e
            self.last_response = {"text": full_text}
            return full_text if raw else self.last_response
        return for_stream() if stream else for_non_stream()


    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        raw: bool = False,
    ) -> Union[str, Generator[str, None, None]]:
        """Generate response `str`"""

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
                return result if isinstance(result, str) else self.get_message(result)
            else:
                return self.get_message(result)

        return for_stream() if stream else for_non_stream()


    def get_message(self, response: dict) -> str:
        """Retrieves message only from response"""
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response.get("text", "")



if __name__ == "__main__":
    from rich import print
    ai = ChatGLM()
    response = ai.chat("hi", stream=True, raw=False)
    for chunk in response:
        print(chunk, end="", flush=True)