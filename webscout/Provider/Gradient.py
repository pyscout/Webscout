"""
Gradient Network Chat API Provider
Reverse engineered from https://chat.gradient.network/
"""

from curl_cffi.requests import Session
from curl_cffi import CurlError
from typing import Optional, Generator, Dict, Any, Union

from webscout.AIutel import Optimizers, Conversation, AwesomePrompts, sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent


class Gradient(Provider):
    """
    Provider for Gradient Network chat API
    Supports real-time streaming responses from distributed GPU clusters
    """
    
    required_auth = False
    AVAILABLE_MODELS = [
        "GPT-OSS-120B",
        "Qwen3-235B",
    ]

    def __init__(
        self,
        model: str = "GPT-OSS-120B",
        is_conversation: bool = True,
        max_tokens: int = 2049,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        system_prompt: str = "You are a helpful assistant.",
        cluster_mode: str = "nvidia",
        enable_thinking: bool = True,
    ):
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        self.model = model
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.proxies = proxies
        self.system_prompt = system_prompt
        self.cluster_mode = cluster_mode
        self.enable_thinking = enable_thinking
        
        self.session = Session()
        self.session.proxies = proxies

        self.agent = LitAgent()
        self.fingerprint = self.agent.generate_fingerprint("chrome")
        
        self.headers = {
            "User-Agent": self.fingerprint.get("user_agent", ""),
            "Accept": "*/*",
            "Accept-Language": self.fingerprint.get("accept_language", ""),
            "Content-Type": "application/json",
            "Origin": "https://chat.gradient.network",
            "Referer": "https://chat.gradient.network/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        self.session.headers.update(self.headers)

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

        messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": conversation_prompt},
            ]

        payload = {
            "model": self.model,
            "clusterMode": self.cluster_mode,
            "messages": messages,
            "enableThinking": self.enable_thinking,
        }

        def for_stream():
            streaming_text = ""
            try:
                response = self.session.post(
                    "https://chat.gradient.network/api/generate",
                    json=payload,
                    stream=True,
                    timeout=self.timeout,
                    impersonate="chrome110",
                )
                response.raise_for_status()

                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None),
                    intro_value=None,
                    to_json=True,
                    skip_markers=[],
                    content_extractor=self._Gradient_extractor,
                    yield_raw_on_error=False,
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
                if streaming_text:
                    self.last_response = {"text": streaming_text}
                    self.conversation.update_chat_history(prompt, streaming_text)

        def for_non_stream():
            try:
                full_response = ""
                for chunk in for_stream():
                    full_response += self.get_message(chunk)
                
                self.last_response = {"text": full_response}
                self.conversation.update_chat_history(prompt, full_response)
                return self.last_response if not raw else full_response

            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed ({type(e).__name__}): {str(e)}") from e

        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[str, Generator[str, None, None]]:
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
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response.get("text", "")

    @staticmethod
    def _Gradient_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        if isinstance(chunk, dict):
            chunk_type = chunk.get("type")
            if chunk_type == "reply":
                return chunk.get("data", {}).get("reasoningContent", "")
        return None

if __name__ == "__main__":
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)

    for model in Gradient.AVAILABLE_MODELS:
        try:
            test_ai = Gradient(model=model, timeout=60)
            response = test_ai.chat("Say 'Hello' in one word", stream=True)
            response_text = ""
            for chunk in response:
                response_text += chunk

            if response_text and len(response_text.strip()) > 0:
                status = "v"
                clean_text = response_text.strip().encode('utf-8', errors='ignore').decode('utf-8')
                display_text = clean_text[:50] + "..." if len(clean_text) > 50 else clean_text
            else:
                status = "x"
                display_text = "Empty or invalid response"
            print(f"\r{model:<50} {status:<10} {display_text}")
        except Exception as e:
            print(f"\r{model:<50} {'x':<10} {str(e)}")
