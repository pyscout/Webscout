from curl_cffi import CurlError
from curl_cffi.requests import Session
from typing import Any, Dict, Optional, Generator, List, Union
import uuid
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
    models = ['GLM-4.5', 'GLM-4.5-Air', 'GLM-4.5V', 'GLM-4-32B', 'GLM-4.1V-9B-Thinking', 'Z1-Rumination', 'Z1-32B', '任务专用']

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
        model: str = None,
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

    @classmethod
    def get_models(cls, **kwargs) -> List[str]:
        """Fetches available models and API key."""
        # Models are static or fetched elsewhere; just return the list
        print(cls.models)
        return cls.models

    @classmethod
    def get_model(cls, model: str) -> str:
        """Get model name (no alias lookup)."""
        cls.get_models()
        return model

    def _get_api_key(self):
        if not hasattr(self, 'api_key') or not self.api_key:
            import requests
            response = requests.get(f"{self.url}/api/v1/auths/")
            self.api_key = response.json().get("token")
        return self.api_key

    def _get_cookie(self):
        """Get authentication cookie from the site"""
        if not hasattr(self, 'cookie') or not self.cookie:
            import requests
            # Make a request to get the cookie
            response = requests.get(f"{self.url}/")
            self.cookie = response.headers.get('Set-Cookie', '')
        return self.cookie


    @staticmethod
    def _zai_extractor(chunk: Dict[str, Any]) -> Optional[str]:
        """Extracts content from Z.AI stream JSON objects."""
        if chunk.get("type") == "chat:completion":
            data = chunk.get("data", {})
            if data.get("phase") == "thinking":
                delta_content = data.get("delta_content")
                if delta_content:
                    return delta_content.split("</summary>\n>")[-1]
            else:
                edit_content = data.get("edit_content")
                if edit_content:
                    return edit_content.split("\n</details>\n")[-1]
                delta_content = data.get("delta_content")
                if delta_content:
                    return delta_content
        return None


    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        model: str = None,
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
        model_id = self.get_model(model or self.model)
        api_key = self._get_api_key()
        print(api_key)
        payload = {
            "stream": True,
            "model": "0727-106B-API",
            "messages": [
                {"role": "user", "content": conversation_prompt}
            ],
            "params": {},
            "features": {"image_generation": False, "web_search": False, "auto_web_search": False, "preview_mode": True, "flags": [], "features": [{"type": "mcp", "server": "vibe-coding", "status": "hidden"}, {"type": "mcp", "server": "ppt-maker", "status": "hidden"}, {"type": "mcp", "server": "image-search", "status": "hidden"}], "enable_thinking": True},
            "variables": {"{{USER_NAME}}": "Guest-1755710598", "{{USER_LOCATION}}": "Unknown", "{{CURRENT_DATETIME}}": "2025-08-20 22:53:20", "{{CURRENT_DATE}}": "2025-08-20", "{{CURRENT_TIME}}": "22:53:20", "{{CURRENT_WEEKDAY}}": "Wednesday", "{{CURRENT_TIMEZONE}}": "Asia/Calcutta", "{{CURRENT_TIME}}": "22:53:20", "{{USER_LANGUAGE}}": "en-US"},
            "model_item": {
                "id": "0727-106B-API",
                "name": "GLM-4.5-Air",
                "owned_by": "openai",
                "openai": {
                    "id": "0727-106B-API",
                    "name": "0727-106B-API",
                    "owned_by": "openai",
                    "openai": {
                        "id": "0727-106B-API"
                    },
                    "urlIdx": 1
                },
                "urlIdx": 1,
                "info": {
                    "id": "0727-106B-API",
                    "user_id": "a3856153-cf5b-49ea-a336-e26669288071",
                    "base_model_id": None,
                    "name": "GLM-4.5-Air",
                    "params": {"temperature": 0.6, "top_p": 0.95, "max_tokens": 80000},
                    "meta": {
                        "profile_image_url": "/static/favicon.png",
                        "description": "Lightweight model, ready for daily tasks",
                        "capabilities": {"vision": False, "citations": False, "preview_mode": False, "web_search": False, "language_detection": False, "restore_n_source": False, "mcp": True, "file_qa": True, "returnFc": True, "returnThink": True, "think": True},
                        "mcpServerIds": ["deep-web-search", "ppt-maker", "vibe-coding", "image-search"],
                        "suggestion_prompts": []
                    },
                    "flags": [],
                    "features": [{"type": "mcp", "server": "vibe-coding", "status": "hidden"}, {"type": "mcp", "server": "ppt-maker", "status": "hidden"}, {"type": "mcp", "server": "image-search", "status": "hidden"}],
                    "tags": []
                },
                "access_control": None,
                "is_active": True,
                "updated_at": 1753672961,
                "created_at": 1753672961
            },
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
                        "Content-Type": "application/json",
                        "Origin": "https://chat.z.ai",
                        "Referer": "https://chat.z.ai/c/local",
                        "Cookie": cookie,
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
                        "Accept": "text/event-stream",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept-Encoding": "gzip, deflate, br, zstd",
                        "DNT": "1",
                        "Sec-CH-UA": '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
                        "Sec-CH-UA-Mobile": "?0",
                        "Sec-CH-UA-Platform": '"Windows"',
                        "Sec-Fetch-Dest": "empty",
                        "Sec-Fetch-Mode": "cors",
                        "Sec-Fetch-Site": "same-origin",
                        "Sec-GPC": "1"
                    }
                )
                response.raise_for_status()

                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None),
                    intro_value="data:",
                    to_json=True,
                    content_extractor=self._zai_extractor,
                    yield_raw_on_error=False
                )

                for current_full_text in processed_stream:
                    if current_full_text and isinstance(current_full_text, str):
                        new_text = current_full_text[len(last_processed_content):]
                        if new_text:
                            streaming_text += new_text
                            last_processed_content = current_full_text
                            yield new_text if raw else dict(text=new_text)

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
        model: str = None,
    ) -> Union[str, Generator[str, None, None]]:
        """Generate response `str`"""

        def for_stream():
            for response in self.ask(
                prompt, True, optimizer=optimizer, conversationally=conversationally, model=model
            ):
                yield self.get_message(response)

        def for_non_stream():
            return self.get_message(
                self.ask(
                    prompt,
                    False,
                    optimizer=optimizer,
                    conversationally=conversationally,
                    model=model,
                )
            )

        return for_stream() if stream else for_non_stream()


    def get_message(self, response: dict) -> str:
        """Retrieves message only from response"""
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response.get("text", "")



if __name__ == "__main__":
    from rich import print
    ai = ChatGLM()
    response = ai.chat(input(">>> "), stream=True)
    for chunk in response:
        print(chunk, end="", flush=True)