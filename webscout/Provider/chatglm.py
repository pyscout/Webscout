from curl_cffi import CurlError
from curl_cffi.requests import Session
from typing import Any, Dict, Optional, Generator, List, Union
import uuid
import time
import urllib.parse
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
    required_auth = False
    url = "https://chat.z.ai"
    # Model nickname mapping system
    MODEL_MAPPING = {
        "glm-4.5V": "glm-4.5v",
        "glm-4-32B": "main_chat",
        "glm-4.5-Air": "0727-106B-API",
        "glm-4.5": "0727-360B-API",
        "glm-4.6": "GLM-4-6-API-V1",
        # Add more nicknames as needed
    }
    # Reverse mapping: API format to nickname
    GLM_TO_MODEL = {v: k for k, v in MODEL_MAPPING.items()}
    AVAILABLE_MODELS = list(MODEL_MAPPING.keys()) + list(GLM_TO_MODEL.keys()) + ["0727-106B-API", "0727-360B-API", "glm-4.5v", "main_chat"]

    @classmethod
    def _resolve_model(cls, model: str) -> str:
        """
        Resolve a model nickname or API name to the API format.
        """
        if model in cls.GLM_TO_MODEL:
            return model
        if model in cls.MODEL_MAPPING:
            return cls.MODEL_MAPPING[model]
        # fallback to direct API name if present
        if model in ["0727-106B-API", "0727-360B-API", "glm-4.5v", "main_chat"]:
            return model
        raise ValueError(f"Invalid model: {model}. Choose from: {cls.AVAILABLE_MODELS}")
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
        # Use nickname resolution for model
        self.model = self._resolve_model(model)

    def _get_api_key(self):
        if not hasattr(self, 'api_key') or not self.api_key:
            response = self.session.get(f"{self.url}/api/v1/auths/")
            self.api_key = response.json().get("token")
        return self.api_key

    def _get_user_id(self):
        """Get user_id from the auth response"""
        if not hasattr(self, 'user_id') or not self.user_id:
            response = self.session.get(f"{self.url}/api/v1/auths/")
            data = response.json()
            self.user_id = data.get("id", str(uuid.uuid4()))
        return self.user_id

    def _get_cookie(self):
        """Get authentication cookie from the site"""
        if not hasattr(self, 'cookie') or not self.cookie:
            response = self.session.get(f"{self.url}/")
            self.cookie = response.headers.get('Set-Cookie', '')
        return self.cookie

    def _build_api_url(self, chat_id: str = "local"):
        """Build the API URL with all required query parameters"""
        api_key = self._get_api_key()
        user_id = self._get_user_id()
        timestamp = str(int(time.time() * 1000))
        request_id = str(uuid.uuid4())
        user_agent = self.session.headers.get('User-Agent', 'Mozilla/5.0')
        
        params = {
            'timestamp': timestamp,
            'requestId': request_id,
            'user_id': user_id,
            'version': '0.0.1',
            'platform': 'web',
            'token': api_key,
            'user_agent': user_agent,
            'language': 'en-US',
            'languages': 'en-US,en',
            'timezone': 'UTC',
            'cookie_enabled': 'true',
            'screen_width': '1920',
            'screen_height': '1080',
            'screen_resolution': '1920x1080',
            'viewport_height': '1080',
            'viewport_width': '1920',
            'viewport_size': '1920x1080',
            'color_depth': '24',
            'pixel_ratio': '1',
            'current_url': f'https://chat.z.ai/c/{chat_id}',
            'pathname': f'/c/{chat_id}',
            'search': '',
            'hash': '',
            'host': 'chat.z.ai',
            'hostname': 'chat.z.ai',
            'protocol': 'https:',
            'referrer': '',
            'title': 'Z.ai Chat - Free AI powered by GLM-4.6',
            'timezone_offset': '0',
            'is_mobile': 'false',
            'is_touch': 'false',
            'max_touch_points': '0',
            'browser_name': 'Chrome',
            'os_name': 'Windows',
            'signature_timestamp': timestamp
        }
        
        query_string = urllib.parse.urlencode(params)
        return f"{self.api_endpoint}?{query_string}"


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
        chat_id = str(uuid.uuid4())
        payload = {
            "stream": True,
            "model": self.model,  # Already resolved to API format
            "messages": [
                {"role": "user", "content": conversation_prompt}
            ],
            "params": {},
            "features": {
                "image_generation": False,
                "web_search": False,
                "auto_web_search": False,
                "preview_mode": True,
                "flags": [],
                "features": [
                    {"type": "mcp", "server": "vibe-coding", "status": "hidden"},
                    {"type": "mcp", "server": "ppt-maker", "status": "hidden"},
                    {"type": "mcp", "server": "image-search", "status": "hidden"},
                    {"type": "mcp", "server": "deep-research", "status": "hidden"},
                    {"type": "tool_selector", "server": "tool_selector", "status": "hidden"},
                    {"type": "mcp", "server": "advanced-search", "status": "hidden"}
                ],
                "enable_thinking": True
            },
            "actions": [],
            "tags": [],
            "chat_id": chat_id,
            "id": str(uuid.uuid4())
        }

        def for_stream():
            streaming_text = ""
            try:
                cookie = self._get_cookie()
                api_url = self._build_api_url(chat_id)
                response = self.session.post(
                    api_url,
                    json=payload,
                    stream=True,
                    timeout=self.timeout,
                    impersonate="chrome120",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "x-fe-version": "prod-fe-1.0.95",
                        "accept": "*/*",
                        "accept-language": "en-US",
                        "content-type": "application/json",
                        "dnt": "1",
                        "origin": self.url,
                        "referer": f"{self.url}/c/{chat_id}",
                        "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": '"Windows"',
                        "sec-fetch-dest": "empty",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-site": "same-origin",
                        "sec-gpc": "1",
                    }
                )
                response.raise_for_status()

                def glm_content_extractor(chunk):
                    if not isinstance(chunk, dict) or chunk.get("type") != "chat:completion":
                        return None
                    data = chunk.get("data", {})
                    phase = data.get("phase")
                    usage = data.get("usage")
                    if usage:
                        return None
                    delta_content = data.get("delta_content")
                    if delta_content:
                        if phase == "thinking":
                            # Remove details/summary tags if present
                            split_text = delta_content.split("</summary>\n>")[-1]
                            return {"reasoning_content": split_text}
                        elif phase == "answer":
                            return {"content": delta_content}
                        else:
                            return {"content": delta_content}
                    return None

                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None),
                    intro_value="data:",
                    to_json=True,
                    content_extractor=glm_content_extractor,
                    yield_raw_on_error=False,
                    raw=False
                )
                last_content = ""
                last_reasoning = ""
                in_think = False
                for chunk in processed_stream:
                    if not chunk:
                        continue
                    content = chunk.get('content') if isinstance(chunk, dict) else None
                    reasoning = chunk.get('reasoning_content') if isinstance(chunk, dict) else None
                    # Handle reasoning_content with <think> tags
                    if reasoning and reasoning != last_reasoning:
                        if not in_think:
                            yield "<think>\n\n"
                            in_think = True
                        yield reasoning
                        last_reasoning = reasoning
                    # If we were in <think> and now have new content, close <think>
                    if in_think and content and content != last_content:
                        yield "\n</think>\n\n"
                        in_think = False
                    # Handle normal content
                    if content and content != last_content:
                        yield content
                        streaming_text += content
                        last_content = content
                # Close <think> tag if still open at end
                if in_think:
                    yield "\n</think>\n\n"
                if not raw:
                    self.last_response = {"text": streaming_text}
                    self.conversation.update_chat_history(prompt, streaming_text)
            except CurlError as e:
                raise exceptions.APIConnectionError(f"Request failed (CurlError): {e}") from e
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"An unexpected error occurred ({type(e).__name__}): {e}") from e

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
                    # Only call get_message on dicts, yield str directly
                    if isinstance(response, dict):
                        yield self.get_message(response)
                    elif isinstance(response, str):
                        yield response

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
    ai = ChatGLM(model="glm-4.6")
    response = ai.chat("hi", stream=True, raw=True)
    for chunk in response:
        print(chunk, end="", flush=True)