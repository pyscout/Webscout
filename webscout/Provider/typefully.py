from typing import Optional, Union, Any, Dict
import re
from uuid import uuid4

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent
from curl_cffi.requests import Session
from curl_cffi import CurlError

class TypefullyAI(Provider):
    required_auth = False
    AVAILABLE_MODELS = ["openai:gpt-4o-mini", "openai:gpt-4o", "anthropic:claude-3-5-haiku-20241022", "groq:llama-3.3-70b-versatile"]

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
        system_prompt: str = "You're a helpful assistant.",
        model: str = "openai:gpt-4o-mini",
    ):
        self.session = Session()
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.api_endpoint = "https://typefully.com/tools/ai/api/completion"
        self.timeout = timeout
        self.last_response = {}
        self.system_prompt = system_prompt
        self.model = model
        self.output_length = max_tokens
        self.agent = LitAgent()
        self.headers = {
            "authority": "typefully.com",
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9",
            "content-type": "application/json",
            "dnt": "1",
            "origin": "https://typefully.com",
            "referer": "https://typefully.com/tools/ai/chat-gpt-alternative",
            "sec-ch-ua": '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "user-agent": self.agent.random()
        }
        self.__available_optimizers = (
            method
            for method in dir(Optimizers)
            if callable(getattr(Optimizers, method)) and not method.startswith("__")
        )
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


    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Dict[str, Any]:
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
        payload = {
            "prompt": conversation_prompt,
            "systemPrompt": self.system_prompt,
            "modelIdentifier": self.model,
            "outputLength": self.output_length
        }
        def for_stream():
            try:
                response = self.session.post(
                    self.api_endpoint, 
                    headers=self.headers, 
                    json=payload, 
                    stream=True, 
                    timeout=self.timeout,
                    impersonate="chrome120"
                )
                if not response.ok:
                    raise exceptions.FailedToGenerateResponseError(
                        f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                    )
                streaming_text = ""
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None),
                    intro_value=None,
                    to_json=False,
                    extract_regexes=[r'0:"(.*?)"'],
                    raw=raw
                )
                for content_chunk in processed_stream:
                    if isinstance(content_chunk, bytes):
                        content_chunk = content_chunk.decode('utf-8', errors='ignore')
                    if content_chunk is None:
                        continue
                    if raw:
                        yield content_chunk
                    else:
                        if content_chunk and isinstance(content_chunk, str):
                            streaming_text += content_chunk
                            yield dict(text=content_chunk)
                self.last_response.update(dict(text=streaming_text))
                self.conversation.update_chat_history(
                    prompt, self.get_message(self.last_response)
                )
            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}")
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"An unexpected error occurred ({type(e).__name__}): {e}")
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
        raw: bool = False,  # Added raw parameter
    ) -> str:
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
                return result
            else:
                return self.get_message(result)
        return for_stream() if stream else for_non_stream()

    def get_message(self, response: dict) -> str:
        assert isinstance(response, dict), "Response should be of dict data-type only"
        text = response.get("text", "")
        try:
            formatted_text = text.replace('\\n', '\n').replace('\\n\\n', '\n\n')
            return formatted_text
        except Exception:
             return text

if __name__ == "__main__":
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)
    working = 0
    total = len(TypefullyAI.AVAILABLE_MODELS)
    for model in TypefullyAI.AVAILABLE_MODELS:
        try:
            test_ai = TypefullyAI(model=model, timeout=60)
            response_stream = test_ai.chat("Say 'Hello' in one word", stream=True)
            response_text = ""
            for chunk in response_stream:
                response_text += chunk
            if response_text and len(response_text.strip()) > 0:
                status = "OK"
                clean_text = response_text.strip()
                display_text = clean_text[:50] + "..." if len(clean_text) > 50 else clean_text
            else:
                status = "FAIL (Stream)"
                display_text = "Empty or invalid stream response"
            print(f"\r{model:<50} {status:<10} {display_text}")
        except Exception as e:
            print(f"\r{model:<50} {'FAIL':<10} {str(e)}")