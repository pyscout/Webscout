from curl_cffi.requests import Session
from curl_cffi import CurlError
from typing import Any, Dict, Optional, Generator, Union

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions

class TogetherAI(Provider):
    """
    A class to interact with the TogetherAI API.
    """

    required_auth = True

    # Default models list (will be updated dynamically)
    AVAILABLE_MODELS = [
        "NousResearch/Nous-Hermes-2-Mixtral-8x7B-DPO",
        "Qwen/QwQ-32B",
        "Qwen/Qwen2-72B-Instruct",
        "Qwen/Qwen2-VL-72B-Instruct",
        "Qwen/Qwen2.5-72B-Instruct-Turbo",
        "Qwen/Qwen2.5-7B-Instruct-Turbo",
        "Qwen/Qwen2.5-Coder-32B-Instruct",
        "Qwen/Qwen2.5-VL-72B-Instruct",
        "Qwen/Qwen3-235B-A22B-Instruct-2507-tput",
        "Qwen/Qwen3-235B-A22B-Thinking-2507",
        "Qwen/Qwen3-235B-A22B-fp8-tput",
        "Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8",
        "Salesforce/Llama-Rank-V1",
        "Virtue-AI/VirtueGuard-Text-Lite",
        "arcee-ai/AFM-4.5B",
        "arcee-ai/coder-large",
        "arcee-ai/maestro-reasoning",
        "arcee-ai/virtuoso-large",
        "arcee_ai/arcee-spotlight",
        "blackbox/meta-llama-3-1-8b",
        "deepcogito/cogito-v2-preview-deepseek-671b",
        "deepseek-ai/DeepSeek-R1",
        "deepseek-ai/DeepSeek-R1-0528-tput",
        "deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
        "deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free",
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
        "deepseek-ai/DeepSeek-V3",
        "google/gemma-2-27b-it",
        "google/gemma-3n-E4B-it",
        "lgai/exaone-3-5-32b-instruct",
        "lgai/exaone-deep-32b",
        "marin-community/marin-8b-instruct",
        "meta-llama/Llama-2-70b-hf",
        "meta-llama/Llama-3-70b-chat-hf",
        "meta-llama/Llama-3-8b-chat-hf",
        "meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
        "meta-llama/Llama-3.2-3B-Instruct-Turbo",
        "meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo",
        "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
        "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
        "meta-llama/Llama-4-Scout-17B-16E-Instruct",
        "meta-llama/Llama-Vision-Free",
        "meta-llama/Meta-Llama-3-70B-Instruct-Turbo",
        "meta-llama/Meta-Llama-3-8B-Instruct-Lite",
        "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
        "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "mistralai/Mistral-7B-Instruct-v0.1",
        "mistralai/Mistral-7B-Instruct-v0.2",
        "mistralai/Mistral-7B-Instruct-v0.3",
        "mistralai/Mistral-Small-24B-Instruct-2501",
        "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "moonshotai/Kimi-K2-Instruct",
        "nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
        "perplexity-ai/r1-1776",
        "scb10x/scb10x-llama3-1-typhoon2-70b-instruct",
        "scb10x/scb10x-typhoon-2-1-gemma3-12b",
        "togethercomputer/Refuel-Llm-V2-Small",
        "zai-org/GLM-4.5-Air-FP8"
    ]

    @classmethod
    def get_models(cls, api_key: str = None):
        """Fetch available models from TogetherAI API.
        
        Args:
            api_key (str, optional): TogetherAI API key. If not provided, returns default models.
            
        Returns:
            list: List of available model IDs
        """
        if not api_key:
            return cls.AVAILABLE_MODELS
            
        try:
            # Use a temporary curl_cffi session for this class method
            temp_session = Session()
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            
            response = temp_session.get(
                "https://api.together.xyz/v1/models",
                headers=headers,
                impersonate="chrome110"
            )
            
            if response.status_code != 200:
                return cls.AVAILABLE_MODELS
                
            data = response.json()
            if "data" in data and isinstance(data["data"], list):
                return [model["id"] for model in data["data"]]
            return cls.AVAILABLE_MODELS
            
        except (CurlError, Exception):
            # Fallback to default models list if fetching fails
            return cls.AVAILABLE_MODELS

    def update_available_models(self, api_key: str):
        """Update available models by fetching from TogetherAI API.
        
        Args:
            api_key (str): TogetherAI API key for fetching models.
        """
        self.AVAILABLE_MODELS = self.get_models(api_key)

    @staticmethod
    def _togetherai_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        """Extracts content from TogetherAI stream JSON objects."""
        if isinstance(chunk, dict):
            return chunk.get("choices", [{}])[0].get("delta", {}).get("content")
        return None

    def __init__(
        self,
        api_key: str,
        is_conversation: bool = True,
        max_tokens: int = 2049,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "meta-llama/Llama-3.1-8B-Instruct-Turbo",
        system_prompt: str = "You are a helpful assistant.",
    ):
        """Initializes the TogetherAI API client.

        Args:
            api_key (str): TogetherAI API key.
            is_conversation (bool, optional): Flag for chatting conversationally. Defaults to True.
            max_tokens (int, optional): Maximum number of tokens to be generated upon completion. Defaults to 2049.
            timeout (int, optional): Http request timeout. Defaults to 30.
            intro (str, optional): Conversation introductory prompt. Defaults to None.
            filepath (str, optional): Path to file containing conversation history. Defaults to None.
            update_file (bool, optional): Add new prompts and responses to the file. Defaults to True.
            proxies (dict, optional): Http request proxies. Defaults to {}.
            history_offset (int, optional): Limit conversation history to this number of last texts. Defaults to 10250.
            act (str|int, optional): Awesome prompt key or index. (Used as intro). Defaults to None.
            model (str, optional): LLM model name. Defaults to "meta-llama/Llama-3.1-8B-Instruct-Turbo".
            system_prompt (str, optional): System prompt to guide the conversation. Defaults to None.
        """
        # Update available models from API
        self.update_available_models(api_key)
        
        # Validate model after updating available models
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        self.api_endpoint = "https://api.together.xyz/v1/chat/completions"
        self.session = Session()
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.last_response = {}
        self.system_prompt = system_prompt
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        
        # Update curl_cffi session headers
        self.session.headers.update(self.headers)
        self.session.proxies = proxies

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
        """
        Sends a prompt to the TogetherAI API and returns the response.
        """
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
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": conversation_prompt},
            ],
            "stream": stream
        }
        def for_stream():
            streaming_text = ""
            try:
                response = self.session.post(
                    self.api_endpoint,
                    json=payload,
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
                    content_extractor=self._togetherai_extractor,
                    yield_raw_on_error=False,
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
                            resp = dict(text=content_chunk)
                            yield resp
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
                    self.api_endpoint,
                    json=payload,
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
                    yield_raw_on_error=False,
                    raw=raw
                )
                content = next((c for c in processed_stream if c is not None), None)
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
        raw: bool = False,  # Added raw parameter
    ) -> Union[str, Generator[str, None, None]]:
        def for_stream_chat():
            gen = self.ask(
                prompt, stream=True, raw=raw,
                optimizer=optimizer, conversationally=conversationally
            )
            for response in gen:
                if raw:
                    yield response
                else:
                    yield self.get_message(response)
        def for_non_stream_chat():
            response_data = self.ask(
                prompt, stream=False, raw=raw,
                optimizer=optimizer, conversationally=conversationally
            )
            if raw:
                return response_data
            else:
                return self.get_message(response_data)
        return for_stream_chat() if stream else for_non_stream_chat()

    def get_message(self, response: dict) -> str:
        """Retrieves message only from response"""
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response["text"]


if __name__ == "__main__":
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)

    for model in TogetherAI.AVAILABLE_MODELS:
        try:
            # Skip testing if no API key is provided
            print(f"\r{model:<50} {'⚠':<10} Requires API key for testing")
        except Exception as e:
            print(f"\r{model:<50} {'✗':<10} {str(e)}")