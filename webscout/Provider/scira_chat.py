from os import system
from curl_cffi import CurlError
from curl_cffi.requests import Session
import json
import uuid
import re
from typing import Any, Dict, Optional, Union, List
from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation, sanitize_stream # Import sanitize_stream
from webscout.AIutel import AwesomePrompts
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent

class SciraAI(Provider):
    """
    A class to interact with the Scira AI chat API.
    """
    required_auth = False
    # Model mapping: actual model names to Scira API format
    MODEL_MAPPING = {
        "grok-3-mini": "scira-default",
        "llama-4-maverick": "scira-llama-4",
        "qwen3-4b": "scira-qwen-4b",
        "qwen3-32b": "scira-qwen-32b",
        "qwen3-4b-thinking": "scira-qwen-4b-thinking",
    }
    
    # Reverse mapping: Scira format to actual model names
    SCIRA_TO_MODEL = {v: k for k, v in MODEL_MAPPING.items()}
    # Available models list (actual model names + scira aliases)
    AVAILABLE_MODELS = list(MODEL_MAPPING.keys()) + list(SCIRA_TO_MODEL.keys())
    
    @classmethod
    def _resolve_model(cls, model: str) -> str:
        """
        Resolve a model name to its Scira API format.
        
        Args:
            model: Either an actual model name or a Scira alias
            
        Returns:
            The Scira API format model name
            
        Raises:
            ValueError: If the model is not supported
        """
        # If it's already a Scira format, return as-is
        if model in cls.SCIRA_TO_MODEL:
            return model
            
        # If it's an actual model name, convert to Scira format
        if model in cls.MODEL_MAPPING:
            return cls.MODEL_MAPPING[model]
            
        # Model not found
        raise ValueError(f"Invalid model: {model}. Choose from: {cls.AVAILABLE_MODELS}")

    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 2049,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "grok-3-mini",
        chat_id: str = None,
        user_id: str = None,
        browser: str = "chrome",
        system_prompt: str = "You are a helpful assistant.",
    ):
        """Initializes the Scira AI API client.

        Args:
            is_conversation (bool): Whether to maintain conversation history.
            max_tokens (int): Maximum number of tokens to generate.
            timeout (int): Request timeout in seconds.
            intro (str): Introduction text for the conversation.
            filepath (str): Path to save conversation history.
            update_file (bool): Whether to update the conversation history file.
            proxies (dict): Proxy configuration for requests.
            history_offset (int): Maximum history length in characters.
            act (str): Persona for the AI to adopt.
            model (str): Model to use, must be one of AVAILABLE_MODELS.
            chat_id (str): Unique identifier for the chat session.
            user_id (str): Unique identifier for the user.
            browser (str): Browser to emulate in requests.
            system_prompt (str): System prompt for the AI.

        """
        # Resolve the model to Scira format
        self.model = self._resolve_model(model)
        
        self.url = "https://scira.ai/api/search"

        # Initialize LitAgent for user agent generation
        self.agent = LitAgent()
        # Use fingerprinting to create a consistent browser identity
        self.fingerprint = self.agent.generate_fingerprint(browser)
        self.system_prompt = system_prompt
        
        # Use the fingerprint for headers
        self.headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9,en-IN;q=0.8",
            "Content-Type": "application/json",
            "Origin": "https://scira.ai",
            "Referer": "https://scira.ai/",
            "Sec-CH-UA": '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Windows"',
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "DNT": "1",
            "Priority": "u=1, i"
        }

        self.session = Session() # Use curl_cffi Session
        self.session.headers.update(self.headers)
        self.session.proxies = proxies # Assign proxies directly

        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = {}
        self.chat_id = chat_id or str(uuid.uuid4())
        self.user_id = user_id or f"user_{str(uuid.uuid4())[:8].upper()}"

        # Always use chat mode (no web search)
        self.search_mode = "chat"

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

        # Update headers with new fingerprint (keeping the updated values)
        self.headers.update({
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9,en-IN;q=0.8",
            "Sec-CH-UA": '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
            "Sec-CH-UA-Platform": '"Windows"',
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
        })

        # Update session headers
        for header, value in self.headers.items():
            self.session.headers[header] = value

        return self.fingerprint

    @staticmethod
    def _scira_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[dict]:
        """Extracts JSON chunks from the Scira stream format.
        Returns a dict with the parsed JSON data.
        """
        if isinstance(chunk, str):
            if chunk.startswith("data: "):
                json_str = chunk[6:].strip()  # Remove "data: " prefix
                if json_str == "[DONE]":
                    return {"type": "done"}
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    return None
        return None

    def ask(
        self,
        prompt: str,
        optimizer: str = None,
        conversationally: bool = False,
        stream: bool = True,  # Default to True, always stream
        raw: bool = False,    # Added raw parameter
    ) -> Union[Dict[str, Any], Any]:
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise Exception(f"Optimizer is not one of {self.__available_optimizers}")

        messages = [
            {"role": "user", "content": conversation_prompt, "parts": [{"type": "text", "text": conversation_prompt}], "id": str(uuid.uuid4())[:16]}
        ]

        # Prepare the request payload
        payload = {
            "id": self.chat_id,
            "messages": messages,
            "model": self.model,
            "group": self.search_mode,
            "user_id": self.user_id,
            "timezone": "Asia/Calcutta",
            "isCustomInstructionsEnabled": False,
            "searchProvider": "parallel"
        }

        def for_stream():
            try:
                response = self.session.post(
                    self.url,
                    json=payload,
                    timeout=self.timeout,
                    impersonate="chrome120",
                    stream=True
                )
                if response.status_code != 200:
                    try:
                        error_content = response.text
                    except:
                        error_content = "<could not read response content>"

                    if response.status_code in [403, 429]:
                        print(f"Received status code {response.status_code}, refreshing identity...")
                        self.refresh_identity()
                        response = self.session.post(
                            self.url, json=payload, timeout=self.timeout,
                            impersonate="chrome120", stream=True
                        )
                        if not response.ok:
                            raise exceptions.FailedToGenerateResponseError(
                                f"Failed to generate response after identity refresh - ({response.status_code}, {response.reason}) - {error_content}"
                            )
                        print("Identity refreshed successfully.")
                    else:
                        raise exceptions.FailedToGenerateResponseError(
                            f"Request failed with status code {response.status_code}. Response: {error_content}"
                        )

                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None),
                    intro_value=None,
                    to_json=False,
                    content_extractor=self._scira_extractor,
                    raw=raw
                )

                streaming_response = ""
                in_think = False
                for content in processed_stream:
                    if content is None:
                        continue
                    if isinstance(content, dict):
                        event_type = content.get("type")
                        if event_type == "reasoning-start":
                            if not in_think:
                                if raw:
                                    yield "<think>\n\n"
                                else:
                                    yield "<think>\n\n"
                                in_think = True
                        elif event_type == "reasoning-delta":
                            if in_think:
                                delta = content.get("delta", "")
                                if raw:
                                    yield delta
                                else:
                                    yield dict(text=delta)
                        elif event_type == "reasoning-end":
                            if in_think:
                                if raw:
                                    yield "</think>\n\n"
                                else:
                                    yield "</think>\n\n"
                                in_think = False
                        elif event_type == "text-delta":
                            delta = content.get("delta", "")
                            if raw:
                                yield delta
                            else:
                                streaming_response += delta
                                yield dict(text=delta)
                        elif event_type == "done":
                            break  # End of stream
                if not raw:
                    self.last_response = {"text": streaming_response}
                    self.conversation.update_chat_history(prompt, streaming_response)
            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}") from e
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed: {e}")

        def for_non_stream():
            # Always use streaming logic, but aggregate the result
            full_response = ""
            for chunk in for_stream():
                if raw:
                    if isinstance(chunk, str):
                        full_response += chunk
                else:
                    if isinstance(chunk, dict) and "text" in chunk:
                        full_response += chunk["text"]
            if not raw:
                self.last_response = {"text": full_response}
                self.conversation.update_chat_history(prompt, full_response)
                return {"text": full_response}
            else:
                return full_response

        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        optimizer: str = None,
        conversationally: bool = False,
        stream: bool = True,  # Default to True, always stream
        raw: bool = False,    # Added raw parameter
    ) -> Any:
        def for_stream():
            for response in self.ask(
                prompt, optimizer=optimizer, conversationally=conversationally, stream=True, raw=raw
            ):
                if raw:
                    yield response
                else:
                    if isinstance(response, dict):
                        yield self.get_message(response)
                    else:
                        # For <think> and </think> tags (strings), yield as is
                        yield response
        def for_non_stream():
            result = self.ask(
                prompt, optimizer=optimizer, conversationally=conversationally, stream=False, raw=raw
            )
            if raw:
                return result
            else:
                if isinstance(result, dict):
                    return self.get_message(result)
                else:
                    return result
        return for_stream() if stream else for_non_stream()

    def get_message(self, response: dict) -> str:
        """
        Retrieves message only from response

        Args:
            response (dict): Response generated by `self.ask`

        Returns:
            str: Message extracted
        """
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response.get("text", "")

if __name__ == "__main__":
    ai = SciraAI(model="grok-3-mini", is_conversation=True, system_prompt="You are a helpful assistant.")
    for resp in ai.chat("Explain the theory of relativity in simple terms.", stream=True, raw=False):
        print(resp, end="", flush=True)