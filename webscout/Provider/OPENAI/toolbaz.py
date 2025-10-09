import time
import uuid
import base64
import json
import random
import string
import re
import cloudscraper
from datetime import datetime
from typing import List, Dict, Optional, Union, Generator, Any

from webscout.litagent import LitAgent
from webscout.Provider.OPENAI.base import BaseChat, BaseCompletions, OpenAICompatibleProvider
from webscout.Provider.OPENAI.utils import (
    ChatCompletion,
    ChatCompletionChunk,
    Choice,
    ChatCompletionMessage,
    ChoiceDelta,
    CompletionUsage,
    format_prompt,
    get_system_prompt
)

# ANSI escape codes for formatting
BOLD = "\033[1m"
RED = "\033[91m"
RESET = "\033[0m"

class Completions(BaseCompletions):
    def __init__(self, client: 'Toolbaz'):
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
        # Format the messages using the format_prompt utility
        formatted_prompt = format_prompt(messages, add_special_tokens=True, do_continue=True)
        
        # Get authentication token
        auth = self._client.get_auth()
        if not auth:
            raise IOError("Failed to authenticate with Toolbaz API")

        # Prepare the request data
        data = {
            "text": formatted_prompt,
            "capcha": auth["token"],
            "model": model,
            "session_id": auth["session_id"]
        }

        # Generate a unique request ID
        request_id = f"chatcmpl-{uuid.uuid4().hex}"
        created_time = int(time.time())

        # Handle streaming response
        if stream:
            return self._handle_streaming_response(request_id, created_time, model, data, timeout, proxies)
        else:
            return self._handle_non_streaming_response(request_id, created_time, model, data, timeout, proxies)

    def _handle_streaming_response(
        self,
        request_id: str,
        created_time: int,
        model: str,
        data: Dict[str, Any],
        timeout: Optional[int] = None,
        proxies: Optional[Dict[str, str]] = None
    ) -> Generator[ChatCompletionChunk, None, None]:
        """Handle streaming response from Toolbaz API"""
        try:
            resp = self._client.session.post(
                "https://data.toolbaz.com/writing.php",
                data=data,
                stream=True,
                proxies=proxies or getattr(self._client, "proxies", None),
                timeout=timeout or self._client.timeout
            )
            resp.raise_for_status()

            buffer = ""
            tag_start = "[model:"
            streaming_text = ""
            
            for chunk in resp.iter_content(chunk_size=1):
                if chunk:
                    text = chunk.decode(errors="ignore")
                    buffer += text
                    
                    # Remove all complete [model: ...] tags in buffer
                    while True:
                        match = re.search(r"\[model:.*?\]", buffer)
                        if not match:
                            break
                        buffer = buffer[:match.start()] + buffer[match.end():]
                    
                    # Only yield up to the last possible start of a tag
                    last_tag = buffer.rfind(tag_start)
                    if last_tag == -1 or last_tag + len(tag_start) > len(buffer):
                        if buffer:
                            streaming_text += buffer
                            
                            # Create the delta object
                            delta = ChoiceDelta(
                                content=buffer,
                                role="assistant"
                            )
                            
                            # Create the choice object
                            choice = Choice(
                                index=0,
                                delta=delta,
                                finish_reason=None
                            )
                            
                            # Create the chunk object
                            chunk = ChatCompletionChunk(
                                id=request_id,
                                choices=[choice],
                                created=created_time,
                                model=model
                            )
                            
                            yield chunk
                            buffer = ""
                    else:
                        if buffer[:last_tag]:
                            streaming_text += buffer[:last_tag]
                            
                            # Create the delta object
                            delta = ChoiceDelta(
                                content=buffer[:last_tag],
                                role="assistant"
                            )
                            
                            # Create the choice object
                            choice = Choice(
                                index=0,
                                delta=delta,
                                finish_reason=None
                            )
                            
                            # Create the chunk object
                            chunk = ChatCompletionChunk(
                                id=request_id,
                                choices=[choice],
                                created=created_time,
                                model=model
                            )
                            
                            yield chunk
                        buffer = buffer[last_tag:]
            
            # Remove any remaining [model: ...] tag in the buffer
            buffer = re.sub(r"\[model:.*?\]", "", buffer)
            if buffer:
                # Create the delta object
                delta = ChoiceDelta(
                    content=buffer,
                    role="assistant"
                )
                
                # Create the choice object
                choice = Choice(
                    index=0,
                    delta=delta,
                    finish_reason="stop"
                )
                
                # Create the chunk object
                chunk = ChatCompletionChunk(
                    id=request_id,
                    choices=[choice],
                    created=created_time,
                    model=model
                )
                
                yield chunk
            
            # Final chunk with finish_reason
            delta = ChoiceDelta(
                content=None,
                role=None
            )
            
            choice = Choice(
                index=0,
                delta=delta,
                finish_reason="stop"
            )
            
            chunk = ChatCompletionChunk(
                id=request_id,
                choices=[choice],
                created=created_time,
                model=model
            )
            
            yield chunk
            
        except Exception as e:
            print(f"{RED}Error during Toolbaz streaming request: {e}{RESET}")
            raise IOError(f"Toolbaz streaming request failed: {e}") from e

    def _handle_non_streaming_response(
        self,
        request_id: str,
        created_time: int,
        model: str,
        data: Dict[str, Any],
        timeout: Optional[int] = None,
        proxies: Optional[Dict[str, str]] = None
    ) -> ChatCompletion:
        """Handle non-streaming response from Toolbaz API"""
        try:
            resp = self._client.session.post(
                "https://data.toolbaz.com/writing.php",
                data=data,
                proxies=proxies or getattr(self._client, "proxies", None),
                timeout=timeout or self._client.timeout
            )
            resp.raise_for_status()

            text = resp.text
            # Remove [model: ...] tags
            text = re.sub(r"\[model:.*?\]", "", text)

            # Create the message object
            message = ChatCompletionMessage(
                role="assistant",
                content=text
            )
            
            # Create the choice object
            choice = Choice(
                index=0,
                message=message,
                finish_reason="stop"
            )
            
            # Usage data is not provided by this API in a standard way, set to 0
            usage = CompletionUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
            
            # Create the completion object
            completion = ChatCompletion(
                id=request_id,
                choices=[choice],
                created=created_time,
                model=model,
                usage=usage
            )
            
            return completion
            
        except Exception as e:
            print(f"{RED}Error during Toolbaz non-stream request: {e}{RESET}")
            raise IOError(f"Toolbaz request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'Toolbaz'):
        self.completions = Completions(client)

class Toolbaz(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for Toolbaz API.

    Usage:
        client = Toolbaz()
        response = client.chat.completions.create(
            model="gemini-2.0-flash",
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print(response.choices[0].message.content)
    """

    AVAILABLE_MODELS = [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash-thinking",
        "gemini-2.0-flash",

        "claude-sonnet-4",

        "gpt-5",
        "gpt-oss-120b",
        "o3-mini",
        "gpt-4o-latest",

        "grok-4-fast",
        
        "toolbaz-v4.5-fast",
        "toolbaz_v4",
        "toolbaz_v3.5_pro",

        "deepseek-r1",
        "deepseek-v3.1",
        "deepseek-v3",

        "Llama-4-Maverick",
        "Llama-3.3-70B",
        
        "mixtral_8x22b",
        "L3-70B-Euryale-v2.1",
        "midnight-rose",
        "unfiltered_x"
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,  # Not used but kept for compatibility
        timeout: int = 30,
        proxies: dict = {},
        browser: str = "chrome"
    ):
        """
        Initialize the Toolbaz client.

        Args:
            api_key: Not used but kept for compatibility with OpenAI interface
            timeout: Request timeout in seconds
            proxies: Proxy configuration for requests
            browser: Browser name for LitAgent to generate User-Agent
        """
        self.timeout = timeout
        self.proxies = proxies
        
        # Initialize session with cloudscraper
        self.session = cloudscraper.create_scraper()
        
        # Set up headers
        self.session.headers.update({
            **LitAgent().generate_fingerprint(browser=browser),
            "pragma": "no-cache",
            "referer": "https://toolbaz.com/",
        })

        # Initialize chat property
        self.chat = Chat(self)

    def random_string(self, length):
        """Generate a random string of specified length"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    def generate_token(self):
        """Generate authentication token for Toolbaz API"""
        payload = {
            "bR6wF": {
                "nV5kP": self.session.headers.get("user-agent"),
                "lQ9jX": "en-US",
                "sD2zR": "431x958",
                "tY4hL": time.tzname[0] if time.tzname else "UTC",
                "pL8mC": "Linux armv81",
                "cQ3vD": datetime.now().year,
                "hK7jN": datetime.now().hour
            },
            "uT4bX": {
                "mM9wZ": [],
                "kP8jY": []
            },
            "tuTcS": int(time.time()),
            "tDfxy": None,
            "RtyJt": str(uuid.uuid4())
        }
        return "d8TW0v" + base64.b64encode(json.dumps(payload).encode()).decode()

    def get_auth(self):
        """Get authentication credentials for Toolbaz API"""
        try:
            session_id = self.random_string(36)
            token = self.generate_token()
            data = {
                "session_id": session_id,
                "token": token
            }
            resp = self.session.post("https://data.toolbaz.com/token.php", data=data)
            resp.raise_for_status()
            result = resp.json()
            if result.get("success"):
                return {"token": result["token"], "session_id": session_id}
            return None
        except Exception as e:
            print(f"{RED}Error getting Toolbaz authentication: {e}{RESET}")
            return None

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()

# Example usage
if __name__ == "__main__":
    # Test the provider
    client = Toolbaz()
    response = client.chat.completions.create(
        model="gemini-2.0-flash",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello! How are you today?"}
        ]
    )
    print(response.choices[0].message.content)
