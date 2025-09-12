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

    # Model mapping: actual model names to Scira API format
    MODEL_MAPPING = {
        "grok-3-mini": "scira-default",
        "grok-3-mini-fast": "scira-x-fast-mini",
        "grok-3-fast": "scira-x-fast",
        "gpt-4.1-nano": "scira-nano",
        "grok-3": "scira-grok-3",
        "grok-4": "scira-grok-4",
        "grok-2-vision-1212": "scira-vision",
        "grok-2-latest": "scira-g2",
        "gpt-4o-mini": "scira-4o-mini",
        "o4-mini-2025-04-16": "scira-o4-mini",
        "o3": "scira-o3",
        "qwen/qwen3-32b": "scira-qwen-32b",
        "qwen3-30b-a3b": "scira-qwen-30b",
        "deepseek-v3-0324": "scira-deepseek-v3",
        "claude-3-5-haiku-20241022": "scira-haiku",
        "mistral-small-latest": "scira-mistral",
        "gemini-2.5-flash-lite-preview-06-17": "scira-google-lite",
        "gemini-2.5-flash": "scira-google",
        "gemini-2.5-pro": "scira-google-pro",
        "claude-sonnet-4-20250514": "scira-anthropic",
        "claude-sonnet-4-20250514-thinking": "scira-anthropic-thinking",
        "claude-4-opus-20250514": "scira-opus",
        "claude-4-opus-20250514-pro": "scira-opus-pro",
        "meta-llama/llama-4-maverick-17b-128e-instruct": "scira-llama-4",
        "kimi-k2-instruct": "scira-kimi-k2",
        "scira-kimi-k2": "kimi-k2-instruct",
    }
    
    # Reverse mapping: Scira format to actual model names
    SCIRA_TO_MODEL = {v: k for k, v in MODEL_MAPPING.items()}
    # Add special cases for aliases and duplicate mappings
    SCIRA_TO_MODEL["scira-anthropic-thinking"] = "claude-sonnet-4-20250514"
    SCIRA_TO_MODEL["scira-opus-pro"] = "claude-4-opus-20250514"
    SCIRA_TO_MODEL["scira-x-fast"] = "grok-3-fast"
    SCIRA_TO_MODEL["scira-x-fast-mini"] = "grok-3-mini-fast"
    SCIRA_TO_MODEL["scira-nano"] = "gpt-4.1-nano"
    SCIRA_TO_MODEL["scira-qwen-32b"] = "qwen/qwen3-32b"
    SCIRA_TO_MODEL["scira-qwen-30b"] = "qwen3-30b-a3b"
    SCIRA_TO_MODEL["scira-deepseek-v3"] = "deepseek-v3-0324"
    SCIRA_TO_MODEL["scira-grok-4"] = "grok-4"
    SCIRA_TO_MODEL["scira-kimi-k2"] = "kimi-k2-instruct"
    SCIRA_TO_MODEL["kimi-k2-instruct"] = "scira-kimi-k2"
    MODEL_MAPPING["claude-4-opus-20250514-pro"] = "scira-opus-pro"
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
            "Accept": self.fingerprint["accept"],
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": self.fingerprint["accept_language"],
            "Content-Type": "application/json",
            "Origin": "https://scira.ai",
            "Referer": "https://scira.ai/",
            "Sec-CH-UA": self.fingerprint["sec_ch_ua"] or '"Not)A;Brand";v="99", "Microsoft Edge";v="127", "Chromium";v="127"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": f'"{self.fingerprint["platform"]}"',
            "User-Agent": self.fingerprint["user_agent"],
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin"
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

        # Update headers with new fingerprint
        self.headers.update({
            "Accept": self.fingerprint["accept"],
            "Accept-Language": self.fingerprint["accept_language"],
            "Sec-CH-UA": self.fingerprint["sec_ch_ua"] or self.headers["Sec-CH-UA"],
            "Sec-CH-UA-Platform": f'"{self.fingerprint["platform"]}"',
            "User-Agent": self.fingerprint["user_agent"],
        })

        # Update session headers
        for header, value in self.headers.items():
            self.session.headers[header] = value

        return self.fingerprint

    @staticmethod
    def _scira_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[dict]:
        """Extracts content from the Scira stream format.
        Handles both old format (g:"..." and 0:"...") and new JSON format.
        Returns a dict: {"g": [g1, g2, ...], "0": zero} for old format,
        or {"g": [reasoning_text...], "0": final_text} for new format.
        """
        result = {}
        
        if isinstance(chunk, str):
            # Handle old format with regex patterns
            g_matches = re.findall(r'g:"(.*?)"', chunk)
            zero_match = re.search(r'0:"(.*?)"(?=,|$)', chunk)
            
            if g_matches:
                result["g"] = [g.encode().decode('unicode_escape').replace('\\', '\\').replace('\\"', '"') for g in g_matches]
            if zero_match:
                result["0"] = zero_match.group(1).encode().decode('unicode_escape').replace('\\', '\\').replace('\\"', '"')
            
            # Also try to parse as JSON for new format
            try:
                # Remove 'data: ' prefix if present
                json_str = chunk.strip()
                if json_str.startswith('data: '):
                    json_str = json_str[6:]
                
                # Skip empty lines and special markers
                if not json_str or json_str == '[DONE]':
                    return None
                
                # Parse JSON
                data = json.loads(json_str)
                if isinstance(data, dict):
                    # Handle new JSON format
                    if data.get("type") == "reasoning-delta" and "delta" in data:
                        # Reasoning content (thinking)
                        result["g"] = [data["delta"]]
                    elif data.get("type") == "text-delta" and "delta" in data:
                        # Final answer content (new format)
                        result["0"] = data["delta"]
                    elif data.get("type") == "delta" and "content" in data:
                        # Alternative final answer format
                        result["0"] = data["content"]
                    elif data.get("type") == "content" and "content" in data:
                        # Alternative content format
                        result["0"] = data["content"]
                    # Handle other response types like start, start-step, etc. (ignore for now)
                        
            except (json.JSONDecodeError, KeyError):
                # Not valid JSON or doesn't match expected structure
                pass
                
        elif isinstance(chunk, dict):
            # Direct dict input (new JSON format)
            if chunk.get("type") == "reasoning-delta" and "delta" in chunk:
                # Reasoning content (thinking)
                result["g"] = [chunk["delta"]]
            elif chunk.get("type") == "text-delta" and "delta" in chunk:
                # Final answer content (new format)
                result["0"] = chunk["delta"]
            elif chunk.get("type") == "delta" and "content" in chunk:
                # Alternative final answer format
                result["0"] = chunk["content"]
            elif chunk.get("type") == "content" and "content" in chunk:
                # Alternative content format
                result["0"] = chunk["content"]
        
        return result if result else None

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
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": conversation_prompt, "parts": [{"type": "text", "text": conversation_prompt}]}
        ]

        # Prepare the request payload
        payload = {
            "id": self.chat_id,
            "messages": messages,
            "model": self.model,
            "group": self.search_mode,
            "user_id": self.user_id,
            "timezone": "Asia/Calcutta"
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
                    to_json=True,  # Enable JSON parsing for new format
                    content_extractor=self._scira_extractor,
                    raw=raw
                )

                streaming_response = ""
                in_think = False
                for content in processed_stream:
                    if content is None:
                        continue
                    if isinstance(content, dict):
                        # Handle g chunks
                        g_chunks = content.get("g", [])
                        zero_chunk = content.get("0")
                        if g_chunks:
                            if not in_think:
                                if raw:
                                    yield "<think>\n\n"
                                else:
                                    yield "<think>\n\n"
                                in_think = True
                            for g in g_chunks:
                                if raw:
                                    yield g
                                else:
                                    yield dict(text=g)
                        if zero_chunk is not None:
                            if in_think:
                                if raw:
                                    yield "</think>\n\n"
                                else:
                                    yield "</think>\n\n"
                                in_think = False
                            if raw:
                                yield zero_chunk
                            else:
                                streaming_response += zero_chunk
                                yield dict(text=zero_chunk)
                    else:
                        # fallback for old string/list logic
                        if raw:
                            yield content
                        else:
                            if content and isinstance(content, str):
                                streaming_response += content
                                yield dict(text=content)
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
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)
    
    # Test all available models
    working = 0
    total = len(SciraAI.AVAILABLE_MODELS)
    
    for model in SciraAI.AVAILABLE_MODELS:
        try:
            test_ai = SciraAI(model=model, timeout=60)
            # Test stream first
            response_stream = test_ai.chat("Say 'Hello' in one word", stream=True)
            response_text = ""
            print(f"\r{model:<50} {'Streaming...':<10}", end="", flush=True)
            for chunk in response_stream:
                response_text += chunk
                # Optional: print chunks as they arrive for visual feedback
                # print(chunk, end="", flush=True) 
            
            if response_text and len(response_text.strip()) > 0:
                status = "✓"
                # Clean and truncate response
                clean_text = response_text.strip() # Already decoded in get_message
                display_text = clean_text[:50] + "..." if len(clean_text) > 50 else clean_text
            else:
                status = "✗ (Stream)"
                display_text = "Empty or invalid stream response"
            print(f"\r{model:<50} {status:<10} {display_text}")
            
            # Optional: Add non-stream test if needed, but stream test covers basic functionality
            # print(f"\r{model:<50} {'Non-Stream...':<10}", end="", flush=True)
            # response_non_stream = test_ai.chat("Say 'Hi' again", stream=False)
            # if not response_non_stream or len(response_non_stream.strip()) == 0:
            #      print(f"\r{model:<50} {'✗ (Non-Stream)':<10} Empty non-stream response")


        except Exception as e:
            print(f"\r{model:<50} {'✗':<10} {str(e)}")

