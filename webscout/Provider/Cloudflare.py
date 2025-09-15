import json
from uuid import uuid4

import re # Import re
from curl_cffi import CurlError
from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream # Import sanitize_stream
from webscout.AIbase import Provider, AsyncProvider
from webscout import exceptions
from typing import Optional, Union, Any, AsyncGenerator, Dict
from curl_cffi.requests import Session
from webscout.litagent import LitAgent

class Cloudflare(Provider):
    """
    Cloudflare provider to interact with Cloudflare's text generation API.
    """
    required_auth = False
    # Updated AVAILABLE_MODELS from given JSON data
    AVAILABLE_MODELS = [
        "@hf/thebloke/deepseek-coder-6.7b-base-awq",
        "@hf/thebloke/deepseek-coder-6.7b-instruct-awq",
        "@cf/deepseek-ai/deepseek-math-7b-instruct",
        "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b",
        "@cf/thebloke/discolm-german-7b-v1-awq",
        "@cf/tiiuae/falcon-7b-instruct",
        "@cf/google/gemma-3-12b-it",
        "@hf/google/gemma-7b-it",
        "@hf/nousresearch/hermes-2-pro-mistral-7b",
        "@hf/thebloke/llama-2-13b-chat-awq",
        "@cf/meta/llama-2-7b-chat-fp16",
        "@cf/meta/llama-2-7b-chat-int8",
        "@cf/meta/llama-3-8b-instruct",
        "@cf/meta/llama-3-8b-instruct-awq",
        "@cf/meta/llama-3.1-8b-instruct-awq",
        "@cf/meta/llama-3.1-8b-instruct-fp8",
        "@cf/meta/llama-3.2-11b-vision-instruct",
        "@cf/meta/llama-3.2-1b-instruct",
        "@cf/meta/llama-3.2-3b-instruct",
        "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        "@cf/meta/llama-4-scout-17b-16e-instruct",
        "@cf/meta/llama-guard-3-8b",
        "@hf/thebloke/llamaguard-7b-awq",
        "@hf/meta-llama/meta-llama-3-8b-instruct",
        "@cf/mistral/mistral-7b-instruct-v0.1",
        "@hf/thebloke/mistral-7b-instruct-v0.1-awq",
        "@hf/mistral/mistral-7b-instruct-v0.2",
        "@cf/mistralai/mistral-small-3.1-24b-instruct",
        "@hf/thebloke/neural-chat-7b-v3-1-awq",
        "@cf/openchat/openchat-3.5-0106",
        "@hf/thebloke/openhermes-2.5-mistral-7b-awq",
        "@cf/microsoft/phi-2",
        "@cf/qwen/qwen1.5-0.5b-chat",
        "@cf/qwen/qwen1.5-1.8b-chat",
        "@cf/qwen/qwen1.5-14b-chat-awq",
        "@cf/qwen/qwen1.5-7b-chat-awq",
        "@cf/qwen/qwen2.5-coder-32b-instruct",
        "@cf/qwen/qwq-32b",
        "@cf/defog/sqlcoder-7b-2",
        "@hf/nexusflow/starling-lm-7b-beta",
        "@cf/tinyllama/tinyllama-1.1b-chat-v1.0",
        "@cf/fblgit/una-cybertron-7b-v2-bf16",
        "@hf/thebloke/zephyr-7b-beta-awq"
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
        model: str = "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b",
        system_prompt: str = "You are a helpful assistant.",
    ):
        """Instantiates Cloudflare Provider

        Args:
            is_conversation (bool, optional): Flag for conversational mode. Defaults to True.
            max_tokens (int, optional): Max tokens to generate. Defaults to 600.
            timeout (int, optional): HTTP request timeout. Defaults to 30.
            intro (str, optional): Introductory prompt. Defaults to None.
            filepath (str, optional): File path for conversation history. Defaults to None.
            update_file (bool, optional): Update history file flag. Defaults to True.
            proxies (dict, optional): Request proxies. Defaults to {}.
            history_offset (int, optional): Chat history limit. Defaults to 10250.
            act (str, optional): Awesome prompt key/index. Defaults to None.
            model (str, optional): Model to use. Defaults to "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b".
            system_prompt (str, optional): System prompt for conversation. Defaults to "You are a helpful assistant.".
            logging (bool, optional): Enable logging if True. Defaults to False.
        """
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        self.session = Session() # Use curl_cffi Session
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.chat_endpoint = "https://playground.ai.cloudflare.com/api/inference"
        self.stream_chunk_size = 64
        self.timeout = timeout
        self.last_response = {}
        self.model = model
        self.system_prompt = system_prompt

        self.headers = {
            'Accept': 'text/event-stream',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9,en-IN;q=0.8',
            'Content-Type': 'application/json',
            'DNT': '1',
            'Origin': 'https://playground.ai.cloudflare.com',
            'Referer': 'https://playground.ai.cloudflare.com/',
            'Sec-CH-UA': '"Not)A;Brand";v="99", "Microsoft Edge";v="127", "Chromium";v="127"',
            'Sec-CH-UA-Mobile': '?0',
            'Sec-CH-UA-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': LitAgent().random()
        }

        self.cookies = {
            'cfzs_amplitude': uuid4().hex,
            'cfz_amplitude': uuid4().hex,
            '__cf_bm': uuid4().hex,
        }

        self.__available_optimizers = (
            method
            for method in dir(Optimizers)
            if callable(getattr(Optimizers, method)) and not method.startswith("__")
        )

        # Initialize session and apply proxies
        # self.session = cloudscraper.create_scraper() # Replaced above
        self.session.headers.update(self.headers)
        self.session.proxies = proxies

        Conversation.intro = (
            AwesomePrompts().get_act(act, raise_not_found=True, default=None, case_insensitive=True)
            if act else intro or Conversation.intro
        )
        self.conversation = Conversation(is_conversation, self.max_tokens_to_sample, filepath, update_file)
        self.conversation.history_offset = history_offset

        # Initialize logger if logging is enabled
        # self.logger = Logger(
        #     name="Cloudflare",
        #     format=LogFormat.MODERN_EMOJI,
        # ) if logging else None

        # if self.logger:
        #     self.logger.info("Cloudflare initialized successfully")

    @staticmethod
    def _cloudflare_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        """Extracts content from Cloudflare stream JSON objects."""
        # Updated for the 0:"..." format
        if isinstance(chunk, str):
            # Use re.search to find the pattern 0:"<content>"
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
    ) -> dict:
        """Chat with AI

        Args:
            prompt (str): Prompt to be sent.
            stream (bool, optional): Whether to stream the response. Defaults to False.
            raw (bool, optional): Return raw response. Defaults to False.
            optimizer (str, optional): Optimizer to use. Defaults to None.
            conversationally (bool, optional): Conversational mode flag. Defaults to False.
        Returns:
            dict: Response from the API.
        """
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
                # if self.logger:
                #     self.logger.debug(f"Applied optimizer: {optimizer}")
            else:
                # if self.logger:
                #     self.logger.error(f"Invalid optimizer requested: {optimizer}")
                raise Exception(f"Optimizer is not one of {list(self.__available_optimizers)}")
        
        payload = {
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": conversation_prompt}
            ],
            "lora": None,
            "model": self.model,
            "max_tokens": self.max_tokens_to_sample,
            "stream": True
        }

        def for_stream():
            # if self.logger:
            #     self.logger.debug("Sending streaming request to Cloudflare API...") 
            streaming_text = "" # Initialize outside try block
            try:
                response = self.session.post(
                    self.chat_endpoint,
                    headers=self.headers,
                    cookies=self.cookies,
                    data=json.dumps(payload),
                    stream=True,
                    timeout=self.timeout,
                    impersonate="chrome120" # Add impersonate
                )
                response.raise_for_status()

                # Use sanitize_stream
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None), # Pass byte iterator
                    intro_value=None,
                    to_json=False, 
                    skip_markers=None,
                    content_extractor=self._cloudflare_extractor, # Use the specific extractor
                    yield_raw_on_error=False # Skip non-JSON lines or lines where extractor fails
                )

                for content_chunk in processed_stream:
                    if content_chunk and isinstance(content_chunk, str):
                        streaming_text += content_chunk
                        yield content_chunk if raw else dict(text=content_chunk)

            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}") from e
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"An unexpected error occurred ({type(e).__name__}): {e}") from e
            finally:
                # Update history after stream finishes or fails
                self.last_response.update(dict(text=streaming_text))
                self.conversation.update_chat_history(prompt, streaming_text)

        def for_non_stream():
            # Aggregate the stream using the updated for_stream logic
            full_text = ""
            last_response_dict = {}
            self.conversation.update_chat_history(prompt, self.get_message(self.last_response))
            # if self.logger:
            #     self.logger.info("Streaming response completed successfully")
            try:
                # Ensure raw=False so for_stream yields dicts
                for chunk_data in for_stream():
                    if isinstance(chunk_data, dict) and "text" in chunk_data:
                        full_text += chunk_data["text"]
                        last_response_dict = {"text": full_text} # Keep track of last dict structure
                    # Handle raw string case if raw=True was passed
                    elif raw and isinstance(chunk_data, str):
                         full_text += chunk_data
                         last_response_dict = {"text": full_text} # Update dict even for raw
            except Exception as e:
                 # If aggregation fails but some text was received, use it. Otherwise, re-raise.
                 if not full_text:
                     raise exceptions.FailedToGenerateResponseError(f"Failed to get non-stream response: {str(e)}") from e

            # last_response and history are updated within for_stream's finally block
            # Return the final aggregated response dict or raw text
            return full_text if raw else last_response_dict

        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> str:
        """Generate response string from chat

        Args:
            prompt (str): Prompt to be sent.
            stream (bool, optional): Stream response flag. Defaults to False.
            optimizer (str, optional): Optimizer name. Defaults to None.
            conversationally (bool, optional): Conversational mode flag. Defaults to False.
        Returns:
            str: Generated response.
        """
        def for_stream():
            for response in self.ask(prompt, True, optimizer=optimizer, conversationally=conversationally):
                yield self.get_message(response)
        def for_non_stream():
            return self.get_message(self.ask(prompt, False, optimizer=optimizer, conversationally=conversationally))
        return for_stream() if stream else for_non_stream()

    def get_message(self, response: dict) -> str:
        """Extracts the message text from the response

        Args:
            response (dict): API response.
        Returns:
            str: Extracted text.
        """
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response["text"]

if __name__ == '__main__':
    from rich import print
    ai = Cloudflare(timeout=5000)
    response = ai.chat("write a poem about AI", stream=True)
    for chunk in response:
        print(chunk, end="", flush=True)
