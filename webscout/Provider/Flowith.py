import requests  # Use requests for compatibility with zstd streaming
from requests import Session
import zstandard as zstd
from typing import Any, Dict, Generator, Union
import uuid

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent

class Flowith(Provider):
    """
    A provider class for interacting with the Flowith API.
    """
    required_auth = False
    AVAILABLE_MODELS = [
        "gpt-5-nano", "gpt-5-mini", "glm-4.5", "gpt-oss-120b", "gpt-oss-20b", "kimi-k2",
        "gpt-4.1", "gpt-4.1-mini", "deepseek-chat", "deepseek-reasoner",
        "gemini-2.5-flash", "grok-3-mini"
    ]

    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 2048,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "gpt-4.1-mini",
        system_prompt: str = "You are a helpful assistant.",
        browser: str = "chrome"
    ):
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        self.url = "https://edge.flowith.net/ai/chat?mode=general"
        self.session = Session()
        self.agent = LitAgent()
        self.fingerprint = self.agent.generate_fingerprint(browser)
        self.headers = {
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9,en-IN;q=0.8",
            "content-type": "application/json",
            "origin": "https://flowith.io",
            "referer": "https://edge.flowith.net/",
            "user-agent": self.fingerprint["user_agent"],
            "dnt": "1",
            "sec-gpc": "1"
        }
        self.session.headers.update(self.headers)
        self.session.proxies = proxies
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = {}
        self.model = model
        self.system_prompt = system_prompt
        self.node_id = str(uuid.uuid4())
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

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator]:
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
                {"content": self.system_prompt, "role": "system"},
                {"content": conversation_prompt, "role": "user"}
            ],
            "stream": stream,
            "nodeId": self.node_id
        }

        def for_stream():
            try:
                response = requests.post(
                    self.url,
                    headers=self.headers,
                    json=payload,
                    stream=True,
                    timeout=self.timeout
                )
                encoding = response.headers.get('Content-Encoding', '').lower()
                streaming_text = ""
                if encoding == 'zstd':
                    dctx = zstd.ZstdDecompressor()
                    with dctx.stream_reader(response.raw) as reader:
                        while True:
                            chunk = reader.read(4096)
                            if not chunk:
                                break
                            text = chunk.decode('utf-8', errors='replace')
                            streaming_text += text
                            yield text if raw else dict(text=text)
                else:
                    for chunk in response.iter_content(chunk_size=4096):
                        if not chunk:
                            break
                        text = chunk.decode('utf-8', errors='replace')
                        streaming_text += text
                        yield text if raw else dict(text=text)
                self.last_response.update(dict(text=streaming_text))
                self.conversation.update_chat_history(
                    prompt, self.get_message(self.last_response)
                )
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed: {e}")

        def for_non_stream():
            try:
                response = requests.post(
                    self.url,
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout
                )
                encoding = response.headers.get('Content-Encoding', '').lower()
                if encoding == 'zstd':
                    dctx = zstd.ZstdDecompressor()
                    with dctx.stream_reader(response.raw) as reader:
                        decompressed = reader.read()
                        text = decompressed.decode('utf-8', errors='replace')
                else:
                    text = response.text
                self.last_response.update(dict(text=text))
                self.conversation.update_chat_history(
                    prompt, self.get_message(self.last_response)
                )
                return self.last_response
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed: {e}")

        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[str, Generator[str, None, None]]:
        def for_stream():
            for response in self.ask(
                prompt, True, optimizer=optimizer, conversationally=conversationally
            ):
                yield self.get_message(response)

        def for_non_stream():
            return self.get_message(
                self.ask(
                    prompt,
                    False,
                    optimizer=optimizer,
                    conversationally=conversationally,
                )
            )

        return for_stream() if stream else for_non_stream()

    def get_message(self, response: dict) -> str:
        # Always return a non-empty string for the assistant's message
        if not isinstance(response, dict):
            return ""
        text = response.get("text", None)
        if text is None or not isinstance(text, str) or not text.strip():
            # Fallback: return a placeholder to avoid Conversation error
            return "[No response generated]"
        return text

if __name__ == "__main__":
    print("-" * 80)
    print(f"{'Model':<20} {'Status':<10} {'Response'}")
    print("-" * 80)
    for model in Flowith.AVAILABLE_MODELS:
        try:
            ai = Flowith(model=model, timeout=60)
            response = ai.chat("Say 'Hello' in one word", stream=True)
            response_text = ""
            for chunk in response:
                response_text += chunk
            status = '✓' if response_text.strip() else '✗'
            display_text = response_text.strip()[:100]
            print(f"{model:<20} {status:<10} {display_text}")
        except Exception as e:
            print(f"{model:<20} {'✗':<10} {str(e)}")