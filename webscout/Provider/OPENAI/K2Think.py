import time
import uuid
import requests
import re
import json
from typing import List, Dict, Optional, Union, Generator, Any

# Import base classes and utility structures
from webscout.Provider.OPENAI.base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from webscout.Provider.OPENAI.utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage, count_tokens
)

# Import LitAgent
from webscout.litagent import LitAgent

# Import logger
from webscout.Litlogger import Logger, LogLevel

logger = Logger(name="K2Think", level=LogLevel.INFO)

class Completions(BaseCompletions):
    def __init__(self, client: 'K2Think'):
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
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Creates a model response for the given chat conversation.
        Mimics openai.chat.completions.create
        """
        # Prepare the payload for K2Think API
        payload = {
            "stream": stream,
            "model": model,
            "messages": messages,
            "params": {}
        }

        # Add optional parameters if provided
        if max_tokens is not None and max_tokens > 0:
            payload["params"]["max_tokens"] = max_tokens

        if temperature is not None:
            payload["params"]["temperature"] = temperature

        if top_p is not None:
            payload["params"]["top_p"] = top_p

        # Add any additional parameters
        payload.update(kwargs)

        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())

        if stream:
            return self._create_stream(request_id, created_time, model, payload, timeout)
        else:
            return self._create_non_stream(request_id, created_time, model, payload, timeout)

    def _create_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any], timeout: Optional[int] = None
    ) -> Generator[ChatCompletionChunk, None, None]:
        try:
            response = self._client.session.post(
                self._client.base_url,
                headers=self._client.headers,
                json=payload,
                stream=True,
                timeout=timeout or self._client.timeout
            )

            # Handle non-200 responses
            if not response.ok:
                raise IOError(
                    f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                )

            # Use count_tokens for prompt tokens
            prompt_tokens = count_tokens([msg.get("content", "") for msg in payload.get("messages", [])])
            completion_tokens = 0
            total_tokens = 0
            seen_content = set()  # Track seen content to avoid duplicates

            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8').strip()

                    # Extract content using regex patterns (similar to x0gpt)
                    extract_regexes = [
                        r'<answer>([\s\S]*?)<\/answer>',
                    ]
                    
                    content = ""
                    for regex in extract_regexes:
                        match = re.search(regex, decoded_line)
                        if match:
                            content = match.group(1)
                            break
                    
                    if content:
                        # Format the content
                        content = self._client.format_text(content)
                        
                        # Skip if we've already seen this exact content
                        if content in seen_content:
                            continue
                        
                        seen_content.add(content)

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

                        # Set usage directly on the chunk object
                        chunk.usage = {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens,
                            "estimated_cost": None
                        }

                        # Return the chunk object with usage information
                        yield chunk

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

            # Set usage directly on the chunk object
            chunk.usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "estimated_cost": None
            }

            yield chunk

        except Exception as e:
            print(f"Error during K2Think stream request: {e}")
            raise IOError(f"K2Think request failed: {e}") from e

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any], timeout: Optional[int] = None
    ) -> ChatCompletion:
        try:
            response = self._client.session.post(
                self._client.base_url,
                headers=self._client.headers,
                json=payload,
                stream=True,
                timeout=timeout or self._client.timeout
            )

            # Handle non-200 responses
            if not response.ok:
                raise IOError(
                    f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                )

            # Collect the full response
            full_text = ""
            seen_content_parts = set()  # Track seen content parts to avoid duplicates
            
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    # Extract content using regex patterns
                    extract_regexes = [
                        r'<answer>([\s\S]*?)<\/answer>',
                    ]
                    
                    for regex in extract_regexes:
                        match = re.search(regex, line)
                        if match:
                            content = match.group(1)
                            # Only add if we haven't seen this exact content before
                            if content not in seen_content_parts:
                                seen_content_parts.add(content)
                                full_text += content
                            break

            # Format the text
            full_text = self._client.format_text(full_text)

            # Use count_tokens for accurate token counts
            prompt_tokens = count_tokens([msg.get("content", "") for msg in payload.get("messages", [])])
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
            print(f"Error during K2Think non-stream request: {e}")
            raise IOError(f"K2Think request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'K2Think'):
        self.completions = Completions(client)

class Models:
    """Models class to mimic OpenAI models.list()"""
    def __init__(self):
        self.available_models = [
            "MBZUAI-IFM/K2-Think",
        ]
    
    def list(self):
        """Return list of available models"""
        return [
            {
                "id": model,
                "object": "model",
                "created": 0,
                "owned_by": "k2think"
            }
            for model in self.available_models
        ]

class K2Think(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for K2Think API.

    Usage:
        client = K2Think()
        response = client.chat.completions.create(
            model="MBZUAI-IFM/K2-Think",
            messages=[{"role": "user", "content": "Hello!"}]
        )
    """

    AVAILABLE_MODELS = ["MBZUAI-IFM/K2-Think"]

    def __init__(
        self,
        browser: str = "chrome",
        proxies: Optional[dict] = None
    ):
        """
        Initialize the K2Think client.

        Args:
            browser: Browser to emulate in user agent
            proxies: Optional proxy configuration dictionary
        """
        super().__init__(proxies=proxies)
        self.timeout = 30
        self.base_url = "https://www.k2think.ai/api/guest/chat/completions"

        # Initialize LitAgent for user agent generation
        agent = LitAgent()
        self.fingerprint = agent.generate_fingerprint(browser)

        self.headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": self.fingerprint["accept_language"],
            "Content-Type": "application/json",
            "User-Agent": self.fingerprint["user_agent"],
            "Origin": "https://www.k2think.ai",
            "Referer": "https://www.k2think.ai/guest",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Ch-Ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": f'"{self.fingerprint["platform"]}"',
            "Priority": "u=1, i"
        }

        self.session.headers.update(self.headers)

        # Initialize the chat interface
        self.chat = Chat(self)

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return K2Think.AVAILABLE_MODELS
        return _ModelList()

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
        Convert model names to ones supported by K2Think.

        Args:
            model: Model name to convert

        Returns:
            K2Think model name
        """
        # K2Think doesn't actually use model names, but we'll keep this for compatibility
        return model

# Convenience function for backward compatibility
def K2ThinkClient(**kwargs):
    """Create a new K2Think client instance"""
    return K2Think(**kwargs)

if __name__ == "__main__":
    from rich import print
    client = K2Think()
    response = client.chat.completions.create(
        model="MBZUAI-IFM/K2-Think",
        messages=[{"role": "user", "content": "Hello!"}],
        stream=True
    )

    for chunk in response:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end='', flush=True)