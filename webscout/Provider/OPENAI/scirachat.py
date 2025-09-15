import time
import uuid
import requests
import json
import re
from typing import List, Dict, Optional, Union, Generator, Any

# Import base classes and utility structures
from webscout.Provider.OPENAI.base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from webscout.Provider.OPENAI.utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage, get_system_prompt, count_tokens
)

# Attempt to import LitAgent, fallback if not available
try:
    from webscout.litagent import LitAgent
except ImportError:
    pass
# --- SciraChat Client ---

class Completions(BaseCompletions):
    def __init__(self, client: 'SciraChat'):
        self._client = client

    def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        stream: bool = False,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        timeout: Optional[int] = None,
        proxies: Optional[Dict[str, str]] = None,
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Creates a model response for the given chat conversation.
        Mimics openai.chat.completions.create
        """
        
        # Prepare the payload for SciraChat API
        payload = {
            "id": self._client.chat_id,
            "messages": messages,
            "model": self._client.convert_model_name(model),
            "group": "chat",  # Always use chat mode (no web search)
            "user_id": self._client.user_id,
            "timezone": "Asia/Calcutta"
        }
        
        # Add optional parameters if provided
        if max_tokens is not None and max_tokens > 0:
            payload["max_tokens"] = max_tokens
        
        # Add any additional parameters
        for key, value in kwargs.items():
            if key not in payload:
                payload[key] = value

        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())

        if stream:
            return self._create_stream(request_id, created_time, model, payload, timeout, proxies)
        else:
            return self._create_non_stream(request_id, created_time, model, payload, timeout, proxies)

    def _create_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any], timeout: Optional[int] = None, proxies: Optional[Dict[str, str]] = None
    ) -> Generator[ChatCompletionChunk, None, None]:
        try:
            response = self._client.session.post(
                self._client.api_endpoint,
                json=payload,
                stream=True,
                timeout=timeout or self._client.timeout,
                proxies=proxies or getattr(self._client, "proxies", None)
            )
            
            # Handle non-200 responses
            if not response.ok:
                # Try to refresh identity if we get a 403 or 429
                if response.status_code in [403, 429]:
                    print(f"Received status code {response.status_code}, refreshing identity...")
                    self._client.refresh_identity()
                    response = self._client.session.post(
                        self._client.api_endpoint,
                        json=payload,
                        stream=True,
                        timeout=timeout or self._client.timeout,
                        proxies=proxies or getattr(self._client, "proxies", None)
                    )
                    if not response.ok:
                        raise IOError(
                            f"Failed to generate response after identity refresh - ({response.status_code}, {response.reason}) - {response.text}"
                        )
                    print("Identity refreshed successfully.")
                else:
                    raise IOError(
                        f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                    )

            # Track token usage across chunks
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            
            # Estimate prompt tokens based on message length
            prompt_tokens = count_tokens(payload.get("messages", [{}])[0].get("content", ""))

            for line in response.iter_lines():
                if not line:
                    continue
                
                try:
                    line_str = line.decode('utf-8')
                    
                    # Format: 0:"content" (quoted format)
                    match = re.search(r'0:"(.*?)"', line_str)
                    if match:
                        content = match.group(1)
                        
                        # Format the content (replace escaped newlines)
                        content = self._client.format_text(content)
                        
                        # Update token counts using count_tokens
                        completion_tokens += count_tokens(content)
                        total_tokens = prompt_tokens + completion_tokens
                        
                        # Create the delta object
                        delta = ChoiceDelta(
                            content=content,
                            role="assistant",
                            tool_calls=None
                        )
                        
                        # Create the choice object
                        choice = Choice(
                            index=0,
                            delta=delta,
                            finish_reason=None,
                            logprobs=None
                        )
                        
                        # Create the chunk object
                        chunk = ChatCompletionChunk(
                            id=request_id,
                            choices=[choice],
                            created=created_time,
                            model=model,
                            system_fingerprint=None
                        )
                        
                        # Convert chunk to dict using Pydantic's API
                        if hasattr(chunk, "model_dump"):
                            chunk_dict = chunk.model_dump(exclude_none=True)
                        else:
                            chunk_dict = chunk.dict(exclude_none=True)
                        
                        # Add usage information to match OpenAI format
                        usage_dict = {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens,
                            "estimated_cost": None
                        }
                        
                        chunk_dict["usage"] = usage_dict
                        
                        # Return the chunk object for internal processing
                        yield chunk
                except Exception as e:
                    print(f"Error processing chunk: {e}")
                    continue
                        
            # Final chunk with finish_reason="stop"
            delta = ChoiceDelta(
                content=None,
                role=None,
                tool_calls=None
            )
            
            choice = Choice(
                index=0,
                delta=delta,
                finish_reason="stop",
                logprobs=None
            )
            
            chunk = ChatCompletionChunk(
                id=request_id,
                choices=[choice],
                created=created_time,
                model=model,
                system_fingerprint=None
            )
            
            if hasattr(chunk, "model_dump"):
                chunk_dict = chunk.model_dump(exclude_none=True)
            else:
                chunk_dict = chunk.dict(exclude_none=True)
            chunk_dict["usage"] = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "estimated_cost": None
            }
            
            yield chunk
            
        except Exception as e:
            print(f"Error during SciraChat stream request: {e}")
            raise IOError(f"SciraChat request failed: {e}") from e

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any], timeout: Optional[int] = None, proxies: Optional[Dict[str, str]] = None
    ) -> ChatCompletion:
        try:
            response = self._client.session.post(
                self._client.api_endpoint,
                json=payload,
                timeout=timeout or self._client.timeout,
                proxies=proxies or getattr(self._client, "proxies", None)
            )
            
            # Handle non-200 responses
            if not response.ok:
                # Try to refresh identity if we get a 403 or 429
                if response.status_code in [403, 429]:
                    print(f"Received status code {response.status_code}, refreshing identity...")
                    self._client.refresh_identity()
                    response = self._client.session.post(
                        self._client.api_endpoint,
                        json=payload,
                        timeout=timeout or self._client.timeout,
                        proxies=proxies or getattr(self._client, "proxies", None)
                    )
                    if not response.ok:
                        raise IOError(
                            f"Failed to generate response after identity refresh - ({response.status_code}, {response.reason}) - {response.text}"
                        )
                    print("Identity refreshed successfully.")
                else:
                    raise IOError(
                        f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                    )
            
            # Collect the full response
            full_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        line_str = line.decode('utf-8')
                        
                        # Format: 0:"content" (quoted format)
                        match = re.search(r'0:"(.*?)"', line_str)
                        if match:
                            content = match.group(1)
                            full_response += content
                    except:
                        continue
            
            # Format the text (replace escaped newlines)
            full_response = self._client.format_text(full_response)
            
            # Estimate token counts
            prompt_tokens = count_tokens(payload.get("messages", [{}])[0].get("content", ""))
            completion_tokens = count_tokens(full_response)
            total_tokens = prompt_tokens + completion_tokens
            
            # Create the message object
            message = ChatCompletionMessage(
                role="assistant",
                content=full_response
            )
            
            # Create the choice object
            choice = Choice(
                index=0,
                message=message,
                finish_reason="stop"
            )
            
            # Create the usage object
            usage = CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )
            
            # Create the completion object
            completion = ChatCompletion(
                id=request_id,
                choices=[choice],
                created=created_time,
                model=model,
                usage=usage,
            )
            
            return completion
            
        except Exception as e:
            print(f"Error during SciraChat non-stream request: {e}")
            raise IOError(f"SciraChat request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'SciraChat'):
        self.completions = Completions(client)

class SciraChat(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for Scira Chat API.
    
    Usage:
        client = SciraChat()
        response = client.chat.completions.create(
            model="scira-default",
            messages=[{"role": "user", "content": "Hello!"}]
        )
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
        "qwen3-4b": "scira-qwen-4b",
        "qwen3-32b": "scira-qwen-32b",
        "qwen3-4b-thinking": "scira-qwen-4b-thinking",
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
        "llama-4-maverick": "scira-llama-4",
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
    SCIRA_TO_MODEL["scira-qwen-4b"] = "qwen3-4b"
    SCIRA_TO_MODEL["scira-qwen-4b-thinking"] = "qwen3-4b-thinking"
    SCIRA_TO_MODEL["scira-deepseek-v3"] = "deepseek-v3-0324"
    SCIRA_TO_MODEL["scira-grok-4"] = "grok-4"
    SCIRA_TO_MODEL["scira-kimi-k2"] = "kimi-k2-instruct"
    SCIRA_TO_MODEL["kimi-k2-instruct"] = "scira-kimi-k2"
    MODEL_MAPPING["claude-4-opus-20250514-pro"] = "scira-opus-pro"
    # Available models list (actual model names + scira aliases)
    AVAILABLE_MODELS = list(MODEL_MAPPING.keys()) + list(SCIRA_TO_MODEL.keys())
    # Optional: pretty display names for UI (reverse mapping)
    MODEL_DISPLAY_NAMES = {v: k for k, v in MODEL_MAPPING.items()}

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

    def convert_model_name(self, model: str) -> str:
        """
        Convert model display names or internal keys to ones supported by SciraChat.
        Args:
            model: Model name or alias to convert
        Returns:
            SciraChat model name
        """
        # Use the new _resolve_model logic
        try:
            return self._resolve_model(model)
        except Exception as e:
            print(f"Warning: {e} Using 'scira-default' instead.")
            return "scira-default"

    def __init__(
        self, 
        timeout: Optional[int] = None, 
        browser: str = "chrome"
    ):
        """
        Initialize the SciraChat client.
        
        Args:
            timeout: Request timeout in seconds (None for no timeout)
            browser: Browser to emulate in user agent
        """
        self.timeout = timeout or 30  # Default to 30 seconds if None
        self.api_endpoint = "https://scira.ai/api/search"
        self.session = requests.Session()
        
        # Initialize LitAgent for user agent generation
        self.agent = LitAgent()
        self.fingerprint = self.agent.generate_fingerprint(browser)
        
        # Use the fingerprint for headers
        self.headers = {
            **self.fingerprint,
            "Origin": "https://scira.ai",
            "Referer": "https://scira.ai/",
        }
        
        self.session.headers.update(self.headers)
        
        # Generate unique IDs for chat session and user
        self.chat_id = str(uuid.uuid4())
        self.user_id = f"user_{str(uuid.uuid4())[:8].upper()}"
        
        # Initialize the chat interface
        self.chat = Chat(self)
    
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
            **self.fingerprint,
        })
        
        # Update session headers
        for header, value in self.headers.items():
            self.session.headers[header] = value
        
        return self.fingerprint
    
    def format_text(self, text: str) -> str:
        """
        Format text by replacing escaped newlines with actual newlines.
        
        Args:
            text: Text to format
            
        Returns:
            Formatted text
        """
        # Use a more comprehensive approach to handle all escape sequences
        try:
            # First handle double backslashes to avoid issues
            text = text.replace('\\\\', '\\')
            
            # Handle common escape sequences
            text = text.replace('\\n', '\n')
            text = text.replace('\\r', '\r')
            text = text.replace('\\t', '\t')
            text = text.replace('\\"', '"')
            text = text.replace("\\'", "'")
            
            # Handle any remaining escape sequences using JSON decoding
            # This is a fallback in case there are other escape sequences
            try:
                # Add quotes to make it a valid JSON string
                json_str = f'"{text}"'
                # Use json module to decode all escape sequences
                decoded = json.loads(json_str)
                return decoded
            except json.JSONDecodeError:
                # If JSON decoding fails, return the text with the replacements we've already done
                return text
        except Exception as e:
            # If any error occurs, return the original text
            print(f"Warning: Error formatting text: {e}")
            return text
    

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                # Return display names (aliases)
                return type(self).AVAILABLE_MODELS
        return _ModelList()

if __name__ == "__main__":
    ai = SciraChat()
    response = ai.chat.completions.create(
        model="grok-3-mini-fast-latest",
        messages=[
            {"role": "user", "content": "who are u?"}
        ],
        stream=True
    )
    for chunk in response:
        if hasattr(chunk, "choices") and chunk.choices and hasattr(chunk.choices[0], "delta"):
            content = getattr(chunk.choices[0].delta, "content", None)
            if content:
                print(content, end="", flush=True)
    print()
