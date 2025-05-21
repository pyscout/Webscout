import time
import uuid
import requests
import json
import re
from typing import List, Dict, Optional, Union, Generator, Any

# Import base classes and utility structures
from .base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from .utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage, get_system_prompt, count_tokens
)

# Attempt to import LitAgent, fallback if not available
try:
    from webscout.litagent import LitAgent
except ImportError:
    # Define a dummy LitAgent if webscout is not installed or accessible
    class LitAgent:
        def generate_fingerprint(self, browser: str = "chrome") -> Dict[str, Any]:
            # Return minimal default headers if LitAgent is unavailable
            print("Warning: LitAgent not found. Using default minimal headers.")
            return {
                "accept": "*/*",
                "accept_language": "en-US,en;q=0.9",
                "platform": "Windows",
                "sec_ch_ua": '"Not/A)Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
                "browser_type": browser,
            }

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
            return self._create_stream(request_id, created_time, model, payload)
        else:
            return self._create_non_stream(request_id, created_time, model, payload)

    def _create_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any]
    ) -> Generator[ChatCompletionChunk, None, None]:
        try:
            response = self._client.session.post(
                self._client.api_endpoint,
                json=payload,
                stream=True,
                timeout=self._client.timeout
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
                        timeout=self._client.timeout
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
                        
                        # Update token counts
                        completion_tokens += 1
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
                        
                        # Convert to dict for proper formatting
                        chunk_dict = chunk.to_dict()
                        
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
            
            chunk_dict = chunk.to_dict()
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
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any]
    ) -> ChatCompletion:
        try:
            response = self._client.session.post(
                self._client.api_endpoint,
                json=payload,
                timeout=self._client.timeout
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
                        timeout=self._client.timeout
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
    
    AVAILABLE_MODELS = {
        "scira-default": "Grok3-mini", # thinking model
        "scira-grok-3": "Grok3",
        "scira-anthropic": "Sonnet 3.7 thinking",
        "scira-vision" : "Grok2-Vision", # vision model
        "scira-4o": "GPT4o",
        "scira-qwq": "QWQ-32B",
        "scira-o4-mini": "o4-mini",
        "scira-google": "gemini 2.5 flash",
        "scira-google-pro": "gemini 2.5 pro",
        "scira-llama-4": "llama 4 Maverick",
    }
    
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
    
    def convert_model_name(self, model: str) -> str:
        """
        Convert model names to ones supported by SciraChat.
        
        Args:
            model: Model name to convert
            
        Returns:
            SciraChat model name
        """
        # If the model is already a valid SciraChat model, return it
        if model in self.AVAILABLE_MODELS:
            return model
        
        # Default to scira-default if model not found
        print(f"Warning: Unknown model '{model}'. Using 'scira-default' instead.")
        return "scira-default"

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()
