from curl_cffi.requests import Session
from curl_cffi import CurlError
import json
from typing import Union, Any, Dict, Generator

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts
from webscout.AIbase import Provider
from webscout import exceptions

class Sambanova(Provider):
    """
    A class to interact with the Sambanova API.
    """
    required_auth = True
    AVAILABLE_MODELS = [
        "DeepSeek-R1-0528",
        "DeepSeek-R1-Distill-Llama-70B",
        "DeepSeek-V3.1",
        "gpt-oss-120b",
        "Qwen3-32B",
        "DeepSeek-V3-0324",
        "Meta-Llama-3.1-8B-Instruct",
        "Meta-Llama-3.3-70B-Instruct",
        "Llama-3.3-Swallow-70B-Instruct-v0.4",
        "Llama-4-Maverick-17B-128E-Instruct"
    ]

    def __init__(
        self,
        api_key: str = None,
        is_conversation: bool = True,
        max_tokens: int = 600,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "Meta-Llama-3.1-8B-Instruct",
        system_prompt: str = "You are a helpful AI assistant.",
    ):
        """
        Initializes the Sambanova API with given parameters.
        """
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        self.api_key = api_key
        self.model = model
        self.system_prompt = system_prompt

        # Initialize curl_cffi Session
        self.session = Session()
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = ""

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

        # Configure the API base URL and headers
        self.base_url = "https://api.sambanova.ai/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # Add User-Agent or sec-ch-ua headers if needed, or rely on impersonate
        }
        
        # Update curl_cffi session headers and proxies
        self.session.headers.update(self.headers)
        self.session.proxies = proxies # Assign proxies directly

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Any, Generator[Any, None, None]]:
        """Chat with AI using the Sambanova API."""
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
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": conversation_prompt},
            ],
            "max_tokens": self.max_tokens_to_sample,
            "stream": True # API seems to always stream based on endpoint name
        }

        def for_stream():
            streaming_text = "" # Initialize outside try block
            try:
                # Use curl_cffi session post with impersonate
                response = self.session.post(
                    self.base_url, 
                    # headers are set on the session
                    json=payload, 
                    stream=True, 
                    timeout=self.timeout,
                    # proxies are set on the session
                    impersonate="chrome110" # Use a common impersonation profile
                )
                response.raise_for_status() # Check for HTTP errors

                # Iterate over bytes and decode manually
                for line_bytes in response.iter_lines():
                    if line_bytes:
                        try:
                            line_str = line_bytes.decode('utf-8').strip()
                            if line_str.startswith("data:"):
                                data = line_str[5:].strip()
                            else:
                                data = line_str # Handle cases where 'data:' prefix might be missing
                            
                            if data == "[DONE]":
                                break
                            
                            json_data = json.loads(data)
                            # Skip entries without valid choices
                            if not json_data.get("choices"):
                                continue
                            choice = json_data["choices"][0]
                            delta = choice.get("delta", {})
                            if "content" in delta:
                                content = delta["content"]
                                if content: # Ensure content is not None or empty
                                    streaming_text += content
                                    resp = {"text": content}
                                    # Yield dict or raw string chunk
                                    yield resp if not raw else content
                            # If finish_reason is provided, consider the stream complete
                            if choice.get("finish_reason"):
                                break
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            continue # Ignore lines that are not valid JSON or cannot be decoded
                
                # Update history after stream finishes
                self.last_response = streaming_text # Store aggregated text
                self.conversation.update_chat_history(
                    prompt, self.last_response
                )
            except CurlError as e: # Catch CurlError
                raise exceptions.ProviderConnectionError(f"Request failed (CurlError): {e}") from e
            except Exception as e: # Catch other potential exceptions (like HTTPError)
                err_text = getattr(e, 'response', None) and getattr(e.response, 'text', '')
                raise exceptions.ProviderConnectionError(f"Request failed ({type(e).__name__}): {e} - {err_text}") from e


        def for_non_stream():
            # Aggregate the stream using the updated for_stream logic
            full_response_text = ""
            try:
                # Ensure raw=False so for_stream yields dicts
                for chunk_data in for_stream():
                    if isinstance(chunk_data, dict) and "text" in chunk_data:
                        full_response_text += chunk_data["text"]
                    # Handle raw string case if raw=True was passed
                    elif raw and isinstance(chunk_data, str):
                         full_response_text += chunk_data
            except Exception as e:
                 # If aggregation fails but some text was received, use it. Otherwise, re-raise.
                 if not full_response_text:
                     raise exceptions.FailedToGenerateResponseError(f"Failed to get non-stream response: {str(e)}") from e

            # last_response and history are updated within for_stream
            # Return the final aggregated response dict or raw string
            return full_response_text if raw else {"text": self.last_response} # Return dict for consistency


        # Since the API endpoint suggests streaming, always call the stream generator.
        # The non-stream wrapper will handle aggregation if stream=False.
        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[str, Generator[str, None, None]]:
        """Generate response `str`"""
        
        def for_stream_chat():
             # ask() yields dicts or strings when streaming
             gen = self.ask(
                 prompt, stream=True, raw=False, # Ensure ask yields dicts
                 optimizer=optimizer, conversationally=conversationally
             )
             for response_dict in gen:
                 yield self.get_message(response_dict) # get_message expects dict or string

        def for_non_stream_chat():
             # ask() returns dict or str when not streaming
             response_data = self.ask(
                 prompt,
                 stream=False,
                 raw=False, # Ensure ask returns dict
                 optimizer=optimizer,
                 conversationally=conversationally,
             )
             return self.get_message(response_data) # get_message expects dict or string

        return for_stream_chat() if stream else for_non_stream_chat()

    def get_message(self, response: Any) -> str:
        """
        Retrieves a clean message from the provided response.

        Args:
            response: The raw response data.

        Returns:
            str: The extracted message.
        """
        if isinstance(response, str):
            return response
        elif isinstance(response, dict) and "text" in response:
            return response["text"]
        return ""

if __name__ == "__main__":
    # Ensure curl_cffi is installed
    from rich import print
    ai = Sambanova(api_key='')
    response = ai.chat(input(">>> "), stream=True)
    for chunk in response:
        print(chunk, end="", flush=True)