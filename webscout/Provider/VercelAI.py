import re
import time
from curl_cffi import requests
import json
from typing import Union, Any, Dict, Generator, Optional
import uuid

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream # Import sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent


class VercelAI(Provider):
    """
    A class to interact with the Vercel AI API.
    """

    required_auth = False
    AVAILABLE_MODELS = [
        "chat-model",
        "chat-model-reasoning"
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
        model: str = "chat-model",
        system_prompt: str = "You are a helpful AI assistant."
    ):
        """Initializes the Vercel AI API client."""

        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        self.session = requests.Session()
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.api_endpoint = "https://chat.vercel.ai/api/chat"
        self.stream_chunk_size = 64
        self.timeout = timeout
        self.last_response = {}
        self.model = model
        self.system_prompt = system_prompt
        self.litagent = LitAgent()
        self.headers = self.litagent.generate_fingerprint()
        self.session.headers.update(self.headers)
        self.session.proxies = proxies

        # Add Vercel AI specific headers
        self.session.headers.update({
            "authority": "chat.vercel.ai",
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9,en-IN;q=0.8",
            "content-type": "application/json",
            "dnt": "1",
            "origin": "https://chat.vercel.ai",
            "priority": "u=1, i",
            "referer": "https://chat.vercel.ai/",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "sec-gpc": "1",
            "x-kpsdk-c": "1-Cl4OUDwFNA",
            "x-kpsdk-cd": json.dumps({
                "workTime": int(time.time() * 1000),
                "id": str(uuid.uuid4()),
                "answers": [5, 5],
                "duration": 26.9,
                "d": 1981,
                "st": int(time.time() * 1000) - 1000,
                "rst": int(time.time() * 1000) - 500
            }),
            "x-kpsdk-ct": str(uuid.uuid4()),
            "x-kpsdk-r": "1-B1NfB2A",
            "x-kpsdk-v": "j-1.0.0"
        })

        # Add cookies
        self.session.cookies.update({
            "KP_UIDz": str(uuid.uuid4()),
            "KP_UIDz-ssn": str(uuid.uuid4())
        })

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

    @staticmethod
    def _vercelai_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        """Extracts content from the VercelAI stream format '0:"..."'."""
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
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator[Any, None, None]]:
        """Chat with AI"""
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
            "id": "guest",
            "messages": [
                {
                    "id": str(uuid.uuid4()),
                    "createdAt": "2025-03-29T09:13:16.992Z",
                    "role": "user",
                    "content": conversation_prompt,
                    "parts": [{"type": "text", "text": conversation_prompt}]
                }
            ],
            "selectedChatModelId": self.model
        }
        def for_stream():
            response = self.session.post(
                self.api_endpoint, headers=self.headers, json=payload, stream=True, timeout=self.timeout
            )
            if not response.ok:
                error_msg = f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                raise exceptions.FailedToGenerateResponseError(error_msg)
            streaming_text = ""
            processed_stream = sanitize_stream(
                data=response.iter_content(chunk_size=None), # Pass byte iterator
                intro_value=None, # No simple prefix
                to_json=False,    # Content is not JSON
                content_extractor=self._vercelai_extractor, # Use the specific extractor
                raw=raw
            )
            for content_chunk in processed_stream:
                # Always yield as string, even in raw mode
                if isinstance(content_chunk, bytes):
                    content_chunk = content_chunk.decode('utf-8', errors='ignore')
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
        """Retrieves message only from response"""
        assert isinstance(response, dict), "Response should be of dict data-type only" 
        # Formatting is handled by the extractor now
        text = response.get("text", "")
        return text.replace('\\n', '\n').replace('\\n\\n', '\n\n') # Keep newline replacement if needed

if __name__ == "__main__":
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)
    
    # Test all available models
    working = 0
    total = len(VercelAI.AVAILABLE_MODELS)
    
    for model in VercelAI.AVAILABLE_MODELS:
        try:
            test_ai = VercelAI(model=model, timeout=60)
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