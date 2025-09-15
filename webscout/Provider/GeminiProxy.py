from typing import Any, Dict, Optional, Union, Generator
import requests
import base64
from webscout.litagent import LitAgent
from webscout.AIutel import Optimizers, AwesomePrompts
from webscout.AIutel import Conversation
from webscout.AIbase import Provider
from webscout import exceptions

class GeminiProxy(Provider):
    """
    GeminiProxy is a provider class for interacting with the Gemini API via a proxy endpoint.
    """
    required_auth = False
    AVAILABLE_MODELS = [
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.5-flash-preview-04-17",
        "gemini-2.5-flash-preview-05-20",
        "gemini-2.5-flash-lite-preview-06-17",
        "gemini-2.5-pro",
        "gemini-2.5-flash",

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
        model: str = "gemini-2.0-flash-lite",
        system_prompt: str = "You are a helpful assistant.",
        browser: str = "chrome"
    ):
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")
        self.base_url = "https://us-central1-infinite-chain-295909.cloudfunctions.net/gemini-proxy-staging-v1"
        self.agent = LitAgent()
        self.fingerprint = self.agent.generate_fingerprint(browser)
        self.headers = self.fingerprint.copy()
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.session.proxies.update(proxies)
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = {}
        self.model = model
        self.system_prompt = system_prompt
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

    def get_image(self, img_url):
        try:
            response = self.session.get(img_url, stream=True, timeout=self.timeout)
            response.raise_for_status()
            mime_type = response.headers.get("content-type", "application/octet-stream")
            data = base64.b64encode(response.content).decode("utf-8")
            return {"mime_type": mime_type, "data": data}
        except Exception as e:
            raise exceptions.FailedToGenerateResponseError(f"Error fetching image: {e}")

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        img_url: Optional[str] = None,
    ) -> Union[Dict[str, Any], Generator]:
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise Exception(f"Optimizer is not one of {self.__available_optimizers}")
        parts = []
        if img_url:
            parts.append({"inline_data": self.get_image(img_url)})
        parts.append({"text": conversation_prompt})
        request_data = {
            "model": self.model,
            "contents": [{"parts": parts}]
        }
        def for_non_stream():
            try:
                response = self.session.post(self.base_url, json=request_data, headers=self.headers, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                self.last_response = data
                self.conversation.update_chat_history(prompt, self.get_message(data))
                return data
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"Error during chat request: {e}")
        # Gemini proxy does not support streaming, so only non-stream
        return for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        img_url: Optional[str] = None,
    ) -> str:
        data = self.ask(prompt, stream=stream, optimizer=optimizer, conversationally=conversationally, img_url=img_url)
        return self.get_message(data)

    def get_message(self, response: dict) -> str:
        assert isinstance(response, dict), "Response should be of dict data-type only"
        try:
            return response['candidates'][0]['content']['parts'][0]['text']
        except Exception:
            return str(response)

if __name__ == "__main__":
    # Ensure curl_cffi is installed
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)
    
    # Test all available models
    working = 0
    total = len(GeminiProxy.AVAILABLE_MODELS)
    
    for model in GeminiProxy.AVAILABLE_MODELS:
        try:
            test_ai = GeminiProxy(model=model, timeout=60)
            response = test_ai.chat("Say 'Hello' in one word", stream=True)
            response_text = ""
            for chunk in response:
                response_text += chunk
                print(f"\r{model:<50} {'Testing...':<10}", end="", flush=True)
            
            if response_text and len(response_text.strip()) > 0:
                status = "✓"
                # Truncate response if too long
                display_text = response_text.strip()[:50] + "..." if len(response_text.strip()) > 50 else response_text.strip()
            else:
                status = "✗"
                display_text = "Empty or invalid response"
            print(f"\r{model:<50} {status:<10} {display_text}")
        except Exception as e:
            print(f"\r{model:<50} {'✗':<10} {str(e)}")
