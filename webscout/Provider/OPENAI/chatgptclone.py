import time
import uuid
# import cloudscraper
from curl_cffi.requests import Session, RequestsError
import json
import re
from typing import List, Dict, Optional, Union, Generator, Any

# Import base classes and utility structures
from webscout.Provider.OPENAI.base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from webscout.Provider.OPENAI.utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage, count_tokens
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

# --- ChatGPTClone Client ---

class Completions(BaseCompletions):
    def __init__(self, client: 'ChatGPTClone'):
        self._client = client

    def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = 2049,
        stream: bool = False,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        timeout: Optional[int] = None,
        proxies: Optional[dict] = None,
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Creates a model response for the given chat conversation.
        Mimics openai.chat.completions.create
        """
        # Prepare the payload for ChatGPTClone API
        payload = {
            "messages": messages,
            "model": self._client.convert_model_name(model),
        }

        # Add optional parameters if provided
        if max_tokens is not None and max_tokens > 0:
            payload["max_tokens"] = max_tokens

        if temperature is not None:
            payload["temperature"] = temperature

        if top_p is not None:
            payload["top_p"] = top_p

        # Add any additional parameters
        payload.update(kwargs)

        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())

        if stream:
            return self._create_stream(request_id, created_time, model, payload, timeout=timeout, proxies=proxies)
        else:
            return self._create_non_stream(request_id, created_time, model, payload, timeout=timeout, proxies=proxies)

    def _create_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any],
        timeout: Optional[int] = None, proxies: Optional[dict] = None
    ) -> Generator[ChatCompletionChunk, None, None]:
        original_proxies = self._client.session.proxies
        if proxies is not None:
            self._client.session.proxies = proxies
        else:
            self._client.session.proxies = {}
        try:
            timeout_val = timeout if timeout is not None else self._client.timeout
            response = self._client.session.post(
                f"{self._client.url}/api/chat",
                headers=self._client.headers,
                cookies=self._client.cookies,
                json=payload,
                stream=True,
                timeout=timeout_val
            )

            # Handle non-200 responses
            if not response.ok:
                # If we get a non-200 response, try refreshing our identity once
                if response.status_code in [403, 429]:
                    self._client.refresh_identity()
                    # Retry with new identity
                    response = self._client.session.post(
                        f"{self._client.url}/api/chat",
                        headers=self._client.headers,
                        cookies=self._client.cookies,
                        json=payload,
                        stream=True,
                        timeout=timeout_val
                    )
                    if not response.ok:
                        raise IOError(
                            f"Failed to generate response after identity refresh - ({response.status_code}, {response.reason}) - {response.text}"
                        )
                else:
                    raise IOError(
                        f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                    )

            # Track token usage across chunks
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0

            # Estimate prompt tokens based on message length
            for msg in payload.get("messages", []):
                prompt_tokens += count_tokens(msg.get("content", ""))

            buffer = ""
            for line in response.iter_content():
                if line:
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="replace")
                    buffer += line

                    # ChatGPTClone uses a different format, so we need to extract the content
                    match = re.search(r'0:"(.*?)"', buffer)
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

                        # Clear buffer after processing
                        buffer = ""
                    # If buffer gets too long, reset it to avoid memory issues
                    elif len(buffer) > 1024:
                        buffer = ""

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
            print(f"Error during ChatGPTClone stream request: {e}")
            raise IOError(f"ChatGPTClone request failed: {e}") from e
        finally:
            self._client.session.proxies = original_proxies

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any],
        timeout: Optional[int] = None, proxies: Optional[dict] = None
    ) -> ChatCompletion:
        original_proxies = self._client.session.proxies
        if proxies is not None:
            self._client.session.proxies = proxies
        else:
            self._client.session.proxies = {}
        try:
            timeout_val = timeout if timeout is not None else self._client.timeout
            # For non-streaming, we still use streaming internally to collect the full response
            response = self._client.session.post(
                f"{self._client.url}/api/chat",
                headers=self._client.headers,
                cookies=self._client.cookies,
                json=payload,
                stream=True,
                timeout=timeout_val
            )

            # Handle non-200 responses
            if not response.ok:
                # If we get a non-200 response, try refreshing our identity once
                if response.status_code in [403, 429]:
                    self._client.refresh_identity()
                    # Retry with new identity
                    response = self._client.session.post(
                        f"{self._client.url}/api/chat",
                        headers=self._client.headers,
                        cookies=self._client.cookies,
                        json=payload,
                        stream=True,
                        timeout=timeout_val
                    )
                    if not response.ok:
                        raise IOError(
                            f"Failed to generate response after identity refresh - ({response.status_code}, {response.reason}) - {response.text}"
                        )
                else:
                    raise IOError(
                        f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                    )

            # Collect the full response
            full_text = ""
            buffer = ""
            for line in response.iter_content():
                if line:
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="replace")
                    buffer += line
                    match = re.search(r'0:"(.*?)"', buffer)
                    if match:
                        content = match.group(1)
                        full_text += content
                        buffer = ""
                    # If buffer gets too long, reset it to avoid memory issues
                    elif len(buffer) > 1024:
                        buffer = ""

            # Format the text (replace escaped newlines)
            full_text = self._client.format_text(full_text)

            # Estimate token counts
            prompt_tokens = 0
            for msg in payload.get("messages", []):
                prompt_tokens += count_tokens(msg.get("content", ""))

            completion_tokens = count_tokens(full_text)
            total_tokens = prompt_tokens + completion_tokens

            # Create the message object
            message = ChatCompletionMessage(
                role="assistant",
                content=full_text
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
            print(f"Error during ChatGPTClone non-stream request: {e}")
            raise IOError(f"ChatGPTClone request failed: {e}") from e
        finally:
            self._client.session.proxies = original_proxies

class Chat(BaseChat):
    def __init__(self, client: 'ChatGPTClone'):
        self.completions = Completions(client)

class ChatGPTClone(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for ChatGPT Clone API.

    Usage:
        client = ChatGPTClone()
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello!"}]
        )
    """

    url = "https://chatgpt-clone-ten-nu.vercel.app"
    AVAILABLE_MODELS = ["gpt-4", "gpt-3.5-turbo"]

    def __init__(
        self,
        browser: str = "chrome",
        impersonate: str = "chrome120",
        proxies: Optional[Dict[str, str]] = None
    ):
        """
        Initialize the ChatGPTClone client.

        Args:
            browser: Browser to emulate in user agent (for LitAgent fallback)
            impersonate: Browser impersonation for curl_cffi (default: chrome120)
            proxies: Optional proxy configuration dict, e.g. {"http": "http://proxy:8080", "https": "https://proxy:8080"}
        """
        super().__init__(proxies=proxies)
        self.timeout = 30
        self.temperature = 0.6  # Default temperature
        self.top_p = 0.7  # Default top_p

        # Use LitAgent for fingerprint if available, else fallback
        agent = LitAgent()
        self.fingerprint = agent.generate_fingerprint(browser)

        # Use the fingerprint for headers
        self.headers = {
            "Accept": self.fingerprint["accept"],
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": self.fingerprint["accept_language"],
            "Content-Type": "application/json",
            "DNT": "1",
            "Origin": self.url,
            "Referer": f"{self.url}/",
            "Sec-CH-UA": self.fingerprint["sec_ch_ua"] or '"Not)A;Brand";v="99", "Microsoft Edge";v="127", "Chromium";v="127"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": f'"{self.fingerprint["platform"]}"',
            "User-Agent": self.fingerprint["user_agent"],
        }

        # Create session cookies with unique identifiers
        self.cookies = {"__Host-session": uuid.uuid4().hex, '__cf_bm': uuid.uuid4().hex}

        # Set consistent headers for the scraper session
        for header, value in self.headers.items():
            self.session.headers[header] = value

        # Initialize the chat interface
        self.chat = Chat(self)

    def refresh_identity(self, browser: str = None, impersonate: str = None):
        """Refreshes the browser identity fingerprint and curl_cffi session."""
        browser = browser or self.fingerprint.get("browser_type", "chrome")
        impersonate = impersonate or "chrome120"
        self.fingerprint = LitAgent().generate_fingerprint(browser)
        self.session = Session(impersonate=impersonate)
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

        # Generate new cookies
        self.cookies = {"__Host-session": uuid.uuid4().hex, '__cf_bm': uuid.uuid4().hex}

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
            text = text.replace("\\'\'", "'")

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
        Convert model names to ones supported by ChatGPTClone.

        Args:
            model: Model name to convert

        Returns:
            ChatGPTClone model name
        """
        # If the model is already a valid ChatGPTClone model, return it
        if model in self.AVAILABLE_MODELS:
            return model

        # Map similar models to supported ones
        if model.startswith("gpt-4"):
            return "gpt-4"
        elif model.startswith("gpt-3.5"):
            return "gpt-3.5-turbo"

        # Default to the most capable model
        print(f"Warning: Unknown model '{model}'. Using 'gpt-4' instead.")
        return "gpt-4"

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()
if __name__ == "__main__":
    # Example usage
    client = ChatGPTClone()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    print(response.choices[0].message.content)
    print()
