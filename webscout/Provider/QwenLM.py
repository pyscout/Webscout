import json
from typing import Union, Any, Dict, Generator, Optional
import uuid
import time

from curl_cffi import Session

from webscout.AIutel import Optimizers, Conversation, AwesomePrompts
from webscout.AIbase import Provider
from webscout import exceptions

class QwenLM(Provider):
    """
    A class to interact with the QwenLM API
    """
    required_auth = True
    AVAILABLE_MODELS = [
        "qwen-plus-2025-09-11",
        "qwen3-max-preview",
        "qwen3-235b-a22b",
        "qwen3-coder-plus",
        "qwen3-30b-a3b",
        "qwen3-coder-30b-a3b-instruct",
        "qwen-max-latest",
        "qwen-plus-2025-01-25",
        "qwq-32b",
        "qwen-turbo-2025-02-11",
        "qwen2.5-omni-7b",
        "qvq-72b-preview-0310",
        "qwen2.5-vl-32b-instruct",
        "qwen2.5-14b-instruct-1m",
        "qwen2.5-coder-32b-instruct",
        "qwen2.5-72b-instruct"
    ]

    def __init__(
        self,
        cookies_path: str,
        is_conversation: bool = True,
        max_tokens: int = 600,
        timeout: int = 30,
        intro: Optional[str] = None,
        filepath: Optional[str] = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: Optional[str] = None,
        model: str = "qwen-plus-2025-09-11",
        system_prompt: str = "You are a helpful AI assistant."
    ):
        """Initializes the QwenLM API client."""
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(
                f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}"
            )

        self.session = Session(impersonate="chrome")
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.api_endpoint = "https://chat.qwen.ai/api/chat/completions"
        self.stream_chunk_size = 64
        self.timeout = timeout
        self.last_response = {}
        self.model = model
        self.system_prompt = system_prompt
        self.cookies_path = cookies_path
        self.cookies_dict, self.token = self._load_cookies()
        self.chat_id = str(uuid.uuid4())

        self.headers = {
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "DNT": "1",
            "Origin": "https://chat.qwen.ai",
            "Pragma": "no-cache",
            "Referer": f"https://chat.qwen.ai/c/{self.chat_id}",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "authorization": f"Bearer {self.token}" if self.token else '',
        }
        self.session.headers.update(self.headers)
        self.session.cookies.update(self.cookies_dict)
        self.session.proxies = proxies
        self.chat_type = "t2t"  # search - used WEB, t2t - chatbot, t2i - image_gen

        self.__available_optimizers = (
            method
            for method in dir(Optimizers)
            if callable(getattr(Optimizers, method))
            and not method.startswith("__")
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

    def _load_cookies(self) -> tuple[dict, str]:
        """Load cookies from a JSON file and build a cookie dict."""
        try:
            with open(self.cookies_path, "r") as f:
                cookies = json.load(f)
            cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies}
            token = cookies_dict.get("token", "")
            return cookies_dict, token
        except FileNotFoundError:
            raise exceptions.InvalidAuthenticationError(
                "Error: cookies.json file not found!"
            )
        except json.JSONDecodeError:
            raise exceptions.InvalidAuthenticationError(
                "Error: Invalid JSON format in cookies.json!"
            )

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: Optional[str] = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator[Any, None, None]]:
        """Chat with AI."""

        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise Exception(
                    f"Optimizer is not one of {list(self.__available_optimizers)}"
                )

        payload = {
            'stream': stream,
            'incremental_output': False,
            "chat_type": "t2t",
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": conversation_prompt,
                    "chat_type": "t2t",
                    "extra": {},
                    "feature_config": {"thinking_enabled": False},
                }
            ],
            "session_id": str(uuid.uuid4()),
            "chat_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
        }

        def for_stream() -> Generator[Dict[str, Any], None, None]:
            response = self.session.post(
                self.api_endpoint, json=payload, headers=self.headers, stream=True, timeout=self.timeout
            )
            if not response.ok:
                raise exceptions.FailedToGenerateResponseError(
                    f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                )

            cumulative_text = ""
            for line in response.iter_lines(decode_unicode=False):
                if line:
                    line = line.decode('utf-8') if isinstance(line, bytes) else line
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            json_data = json.loads(data)
                            if "response.created" in json_data:
                                # Initial response, can ignore or use for chat_id etc.
                                continue
                            if "choices" in json_data:
                                delta = json_data["choices"][0]["delta"]
                                new_content = delta.get("content", "")
                                status = delta.get("status", "")
                                if status == "finished":
                                    break
                                cumulative_text += new_content
                                if new_content:
                                    yield delta if raw else {"text": new_content}
                        except json.JSONDecodeError:
                            continue
            self.last_response.update(dict(text=cumulative_text))
            self.conversation.update_chat_history(
                prompt, self.get_message(self.last_response)
            )

        def for_non_stream() -> Dict[str, Any]:
            """
            Handles non-streaming responses by making a non-streaming request.
            """

            # Create a non-streaming payload
            non_stream_payload = payload.copy()
            non_stream_payload['stream'] = False
            non_stream_payload['incremental_output'] = False

            response = self.session.post(
                self.api_endpoint, json=non_stream_payload, headers=self.headers, stream=False, timeout=self.timeout
            )
            if not response.ok:
                raise exceptions.FailedToGenerateResponseError(
                    f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                )

            result = response.json()
            assistant_reply = (
                result.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )

            self.last_response.update({"text": assistant_reply})
            self.conversation.update_chat_history(
                prompt, self.get_message(self.last_response)
            )

            return {"text": assistant_reply}

        return for_stream() if stream else for_non_stream()


    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: Optional[str] = None,
        conversationally: bool = False,
    ) -> Union[str, Generator[str, None, None]]:
        """Generate response string from chat."""

        def for_stream() -> Generator[str, None, None]:
            for response in self.ask(prompt, True, optimizer=optimizer, conversationally=conversationally):
                yield response if isinstance(response, str) else response["text"]

        def for_non_stream() -> str:
            result = self.ask(prompt, False, optimizer=optimizer, conversationally=conversationally)
            return self.get_message(result)

        return for_stream() if stream else for_non_stream()

    def get_message(self, response: dict) -> str:
        """Extracts the message content from a response dict."""
        assert isinstance(response, dict), "Response should be a dict"
        return response.get("text", "")

if __name__ == "__main__":
    from rich import print
    cookies_path = r"C:\Users\koula\Desktop\Webscout\cookies.json"
    for model in QwenLM.AVAILABLE_MODELS:
        ai = QwenLM(cookies_path=cookies_path, model=model)
        response = ai.chat("hi")
        print(f"Model: {model}")
        print(response)
        print("-" * 50)
    # for chunk in response:
    #     print(chunk, end="", flush=True)
