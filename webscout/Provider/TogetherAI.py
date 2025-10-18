from curl_cffi.requests import Session
from curl_cffi import CurlError
import json
from typing import Any, Dict, Optional, Generator, Union
from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent

class TogetherAI(Provider):
    """
    A class to interact with the Together AI Chat API (https://chat.together.ai/).
    Uses the chat interface API endpoint with model UUIDs.
    """
    required_auth = False
    AVAILABLE_MODELS = {
        "DeepSeek R1 (0528)": "dc11fae1-a7a2-4bed-9bd5-bd31bd8f5053",
        "DeepSeek V3 (0324)": "3e26fb3e-5b59-454d-b4af-dcd10d8c91a4",
        "GPT OSS 120B": "34dd95c6-5b8b-42f8-b7a9-99cc01b27a39",
        "Kimi K2 Instruct (0905)": "e91f96e5-fc2f-4e15-95af-43edaa1c6549",
        "Qwen3 Coder 480B": "4fbbacb9-2b02-42db-827e-4c4dd6e12f84",
        "GLM-4.5-Air": "37fb891c-1c2c-43f5-8cc0-f2a80b1f4a36",
        "Llama 4 Maverick": "84b39408-ac91-43a0-a2f0-6e4fb72e9800",
    }

    @staticmethod
    def _together_ai_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        """Extracts content from Together AI stream JSON objects."""
        if isinstance(chunk, dict):
            # Extract from streaming response format
            choices = chunk.get("choices", [])
            if choices and len(choices) > 0:
                delta = choices[0].get("delta", {})
                if isinstance(delta, dict):
                    return delta.get("content")
        return None

    def __init__(
        self,
        api_key: Optional[str] = None,
        is_conversation: bool = True,
        max_tokens: int = 2049,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "DeepSeek R1 (0528)",
        system_prompt: str = "You are a helpful assistant.",
        temperature: float = 0.6,
        top_p: float = 0.95,
        browser: str = "chrome"
    ):
        """Initializes the Together AI chat client."""
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {list(self.AVAILABLE_MODELS.keys())}")

        self.url = "https://chat.together.ai/api/chat-completion"
        self.model_name = model
        self.model_id = self.AVAILABLE_MODELS[model]
        self.temperature = temperature
        self.top_p = top_p

        # Initialize LitAgent
        self.agent = LitAgent()
        self.fingerprint = self.agent.generate_fingerprint(browser)
        self.api = api_key
        
        # Setup headers
        self.headers = {
            "Accept": self.fingerprint["accept"],
            "Accept-Language": self.fingerprint["accept_language"],
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "Origin": "https://chat.together.ai",
            "Pragma": "no-cache",
            "Referer": "https://chat.together.ai/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": self.fingerprint.get("user_agent", ""),
            "Sec-CH-UA": self.fingerprint.get("sec_ch_ua", ""),
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": f'"{self.fingerprint.get("platform", "")}"',
            "X-Forwarded-For": self.fingerprint.get("x-forwarded-for", ""),
            "X-Real-IP": self.fingerprint.get("x-real-ip", ""),
            "X-Client-IP": self.fingerprint.get("x-client-ip", ""),
        }
        
        if self.api is not None:
            self.headers["Authorization"] = f"Bearer {self.api}"

        # Initialize curl_cffi Session
        self.session = Session()
        self.session.headers.update(self.headers)
        self.session.proxies = proxies
        self.system_prompt = system_prompt
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = {}

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

        # Update headers with new fingerprint
        self.headers.update({
            "Accept": self.fingerprint["accept"],
            "Accept-Language": self.fingerprint["accept_language"],
            "User-Agent": self.fingerprint.get("user_agent", ""),
            "Sec-CH-UA": self.fingerprint.get("sec_ch_ua", ""),
        })

        self.session.headers.update(self.headers)
        return self.fingerprint

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

        # Payload construction
        payload = {
            "modelId": self.model_id,
            "temperature": self.temperature,
            "topP": self.top_p,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": conversation_prompt},
            ],
            "stream": stream,
            "maxTokens": self.max_tokens_to_sample,
            "options": {}
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

                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None),
                    intro_value="data:",
                    to_json=True,
                    skip_markers=["[DONE]"],
                    content_extractor=self._together_ai_extractor,
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

                response_text = response.text

                processed_stream = sanitize_stream(
                    data=response_text,
                    to_json=True,
                    intro_value=None,
                    content_extractor=lambda chunk: chunk.get("choices", [{}])[0].get("message", {}).get("content") if isinstance(chunk, dict) else None,
                    yield_raw_on_error=False
                )
                content = next(processed_stream, None)
                content = content if isinstance(content, str) else ""

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
        return response["text"]

if __name__ == "__main__":
    print("-" * 100)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 100)

    for model_name in TogetherAI.AVAILABLE_MODELS:
        try:
            test_ai = TogetherAI(model=model_name, timeout=60)
            response = test_ai.chat("Say 'Hello' in one word", stream=True)
            response_text = ""
            for chunk in response:
                response_text += chunk

            if response_text and len(response_text.strip()) > 0:
                status = "✓"
                clean_text = response_text.strip().encode('utf-8', errors='ignore').decode('utf-8')
                display_text = clean_text[:50] + "..." if len(clean_text) > 50 else clean_text
            else:
                status = "✗"
                display_text = "Empty or invalid response"
            print(f"\r{model_name:<50} {status:<10} {display_text}")
        except Exception as e:
            print(f"\r{model_name:<50} {'✗':<10} {str(e)[:50]}")
