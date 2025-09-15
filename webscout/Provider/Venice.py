from curl_cffi import CurlError
from curl_cffi.requests import Session # Import Session
import json
from typing import Generator, Dict, Any, List, Optional, Union
from uuid import uuid4
import random

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream # Import sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent

class Venice(Provider):
    """
    A class to interact with the Venice AI API.
    """
    
    required_auth = False
    AVAILABLE_MODELS = [
        "mistral-31-24b",
        "dolphin-3.0-mistral-24b",
        "dolphin-3.0-mistral-24b-1dot1",
        "qwen2dot5-coder-32b",
        "deepseek-coder-v2-lite",

    ]
    
    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 2000,
        timeout: int = 30,
        temperature: float = 0.8, # Keep temperature, user might want to adjust
        top_p: float = 0.9, # Keep top_p
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "mistral-31-24b", 
        # System prompt is empty in the example, but keep it configurable
        system_prompt: str = "" 
    ):
        """Initialize Venice AI client"""
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")
            
        # Update API endpoint
        self.api_endpoint = "https://outerface.venice.ai/api/inference/chat" 
        # Initialize curl_cffi Session
        self.session = Session() 
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.timeout = timeout
        self.model = model
        self.system_prompt = system_prompt
        self.last_response = {}
        
        # Update Headers based on successful request
        self.headers = {
            "User-Agent": LitAgent().random(), # Keep using LitAgent
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9", # Keep existing
            "content-type": "application/json",
            "origin": "https://venice.ai",
            "referer": "https://venice.ai/", # Update referer
            # Update sec-ch-ua to match example
            "sec-ch-ua": '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"', 
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            # Update sec-fetch-site to match example
            "sec-fetch-site": "same-site", 
            # Add missing headers from example
            "priority": "u=1, i", 
            "sec-gpc": "1",
            "x-venice-version": "interface@20250424.065523+50bac27" # Add version header
        }

        # Update curl_cffi session headers and proxies
        self.session.headers.update(self.headers)
        self.session.proxies.update(proxies)
        
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
    def _venice_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        """Extracts content from Venice stream JSON objects."""
        if isinstance(chunk, dict) and chunk.get("kind") == "content":
            return chunk.get("content")
        return None


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
            "requestId": str(uuid4())[:7],
            "modelId": self.model,
            "prompt": [{"content": conversation_prompt, "role": "user"}],
            "systemPrompt": self.system_prompt,
            "conversationType": "text",
            "temperature": self.temperature,
            "webEnabled": True,
            "topP": self.top_p,
            "includeVeniceSystemPrompt": True,
            "isCharacter": False,
            "userId": "user_anon_" + str(random.randint(1000000000, 9999999999)),
            "isDefault": True,
            "textToSpeech": {"voiceId": "af_sky", "speed": 1},
            "clientProcessingTime": random.randint(10, 50)
        }
        def for_stream():
            try:
                response = self.session.post(
                    self.api_endpoint, 
                    json=payload, 
                    stream=True, 
                    timeout=self.timeout,
                    impersonate="edge101"
                ) 
                if response.status_code != 200:
                    raise exceptions.FailedToGenerateResponseError(
                        f"Request failed with status code {response.status_code} - {response.text}"
                    )
                streaming_text = ""
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None),
                    intro_value=None,
                    to_json=True,
                    content_extractor=self._venice_extractor,
                    yield_raw_on_error=False,
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
                self.conversation.update_chat_history(prompt, streaming_text)
                self.last_response = {"text": streaming_text} 
            except CurlError as e: 
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}")
            except Exception as e: 
                raise exceptions.FailedToGenerateResponseError(f"An unexpected error occurred ({type(e).__name__}): {e}")
        def for_non_stream():
            full_text = ""
            for chunk_data in for_stream(): 
                if isinstance(chunk_data, dict) and "text" in chunk_data:
                    full_text += chunk_data["text"]
                elif isinstance(chunk_data, str): 
                     full_text += chunk_data
            self.last_response = {"text": full_text} 
            return self.last_response 
        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        raw: bool = False,  # Added raw parameter
    ) -> Union[str, Generator]:
        def for_stream():
            for response in self.ask(prompt, True, raw=raw, optimizer=optimizer, conversationally=conversationally):
                if raw:
                    yield response
                else:
                    yield self.get_message(response)
        def for_non_stream():
            result = self.ask(prompt, False, raw=raw, optimizer=optimizer, conversationally=conversationally)
            if raw:
                return result
            else:
                return self.get_message(result)
        return for_stream() if stream else for_non_stream()

    def get_message(self, response: dict) -> str:
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response["text"]

if __name__ == "__main__":
    # Ensure curl_cffi is installed
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)
    
    # Test all available models
    working = 0
    total = len(Venice.AVAILABLE_MODELS)
    
    for model in Venice.AVAILABLE_MODELS:
        try:
            test_ai = Venice(model=model, timeout=60)
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