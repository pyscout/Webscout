#!/usr/bin/env python3
"""
OpenAI-compatible client for the FreeGemini provider,
which uses the free-gemini.vercel.app service.
"""

import time
import uuid
import json
from typing import List, Dict, Optional, Union, Generator, Any

from curl_cffi.requests import Session

from webscout.litagent import LitAgent
from webscout.AIutel import sanitize_stream
from webscout.Provider.OPENAI.base import BaseChat, BaseCompletions, OpenAICompatibleProvider
from webscout.Provider.OPENAI.utils import (
    ChatCompletion,
    ChatCompletionChunk,
    Choice,
    ChatCompletionMessage,
    ChoiceDelta,
    CompletionUsage,
    format_prompt,
    get_system_prompt,
    count_tokens
)

# ANSI escape codes for formatting
BOLD = "\033[1m"
RED = "\033[91m"
RESET = "\033[0m"

class Completions(BaseCompletions):
    def __init__(self, client: 'FreeGemini'):
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
        proxies: Optional[dict] = None,
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Creates a model response for the given chat conversation.
        Mimics openai.chat.completions.create
        """
        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())

        api_payload = {
            "contents": messages,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": top_p
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"}
            ]
        }
        
        if stream:
            return self._create_stream(request_id, created_time, model, api_payload, timeout=timeout, proxies=proxies)
        else:
            return self._create_non_stream(request_id, created_time, model, api_payload, timeout=timeout, proxies=proxies)

    def _create_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any],
        timeout: Optional[int] = None, proxies: Optional[dict] = None
    ) -> Generator[ChatCompletionChunk, None, None]:
        original_proxies = self._client.session.proxies
        if proxies is not None:
            self._client.session.proxies = proxies
        else:
            # Ensure session proxies are reset if no specific proxies are passed for this call
            self._client.session.proxies = {}
        try:
            response = self._client.session.post(
                self._client.api_endpoint,
                json=payload,
                stream=True,
                timeout=timeout if timeout is not None else self._client.timeout,
                impersonate="chrome120"
            )
            response.raise_for_status()

            # Track token usage across chunks
            completion_tokens = 0
            streaming_text = ""

            processed_stream = sanitize_stream(
                data=response.iter_content(chunk_size=None),
                intro_value="data:",
                to_json=True,
                content_extractor=self._gemini_extractor,
                yield_raw_on_error=False
            )
            
            for text_chunk in processed_stream:
                if text_chunk and isinstance(text_chunk, str):
                    streaming_text += text_chunk
                    completion_tokens += count_tokens(text_chunk)
                    
                    delta = ChoiceDelta(content=text_chunk, role="assistant")
                    choice = Choice(index=0, delta=delta, finish_reason=None)
                    chunk = ChatCompletionChunk(
                        id=request_id,
                        choices=[choice],
                        created=created_time,
                        model=model
                    )
                    yield chunk
            
            # Final chunk with finish_reason
            delta = ChoiceDelta(content=None)
            choice = Choice(index=0, delta=delta, finish_reason="stop")
            chunk = ChatCompletionChunk(
                id=request_id,
                choices=[choice],
                created=created_time,
                model=model
            )
            yield chunk

        except Exception as e:
            print(f"{RED}Error during FreeGemini stream request: {e}{RESET}")
            raise IOError(f"FreeGemini stream request failed: {e}") from e
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
            # For non-streaming, we'll still use streaming since the API returns data in chunks
            response = self._client.session.post(
                self._client.api_endpoint,
                json=payload,
                stream=True,  # API always returns streaming format
                timeout=timeout if timeout is not None else self._client.timeout,
                impersonate="chrome120"
            )
            response.raise_for_status()
            
            # Process the streaming response to get the full text
            full_text_response = ""
            
            # Process each chunk using the same method as streaming
            for line in response.iter_lines():
                if line and line.startswith(b"data:"):
                    # Extract the JSON part
                    json_str = line[5:].strip().decode('utf-8')
                    if json_str != "[DONE]":
                        try:
                            data = json.loads(json_str)
                            # Use the existing extractor to get the text
                            text_chunk = self._gemini_extractor(data)
                            if text_chunk:
                                full_text_response += text_chunk
                        except json.JSONDecodeError:
                            # Skip invalid JSON
                            pass
            
            # Create usage statistics using count_tokens
            prompt_tokens = count_tokens(str(payload))
            completion_tokens = count_tokens(full_text_response)
            total_tokens = prompt_tokens + completion_tokens
            
            usage = CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )

            # Create the message and choice objects
            message = ChatCompletionMessage(
                role="assistant",
                content=full_text_response
            )
            choice = Choice(
                index=0,
                message=message,
                finish_reason="stop"
            )

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
            print(f"{RED}Error during FreeGemini non-stream request: {e}{RESET}")
            raise IOError(f"FreeGemini request failed: {e}") from e
        finally:
            self._client.session.proxies = original_proxies

    @staticmethod
    def _gemini_extractor(data: Dict) -> Optional[str]:
        """Extract text content from Gemini API response stream data."""
        try:
            if "candidates" in data and data["candidates"]:
                candidate = data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    parts = candidate["content"]["parts"]
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
        except (KeyError, IndexError, TypeError):
            pass
        return None

class Chat(BaseChat):
    def __init__(self, client: 'FreeGemini'):
        self.completions = Completions(client)


class FreeGemini(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for FreeGemini API.

    Usage:
        client = FreeGemini()
        response = client.chat.completions.create(
            model="gemini-2.0-flash",
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print(response.choices[0].message.content)
    """

    AVAILABLE_MODELS = ["gemini-2.0-flash"]

    def __init__(self, proxies: Optional[dict] = None):
        """
        Initialize the FreeGemini client.
        
        Args:
            proxies: Optional proxy configuration dictionary
        """
        super().__init__(proxies=proxies)
        self.timeout = 30
        # Update the API endpoint to match the working implementation
        self.api_endpoint = "https://free-gemini.vercel.app/api/google/v1beta/models/gemini-2.0-flash:streamGenerateContent?alt=sse"
        
        # Use LitAgent for fingerprinting
        self.agent = LitAgent()
        
        # Set headers for the requests
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": self.agent.random(),
            "Origin": "https://free-gemini.vercel.app",
            "Referer": "https://free-gemini.vercel.app/",
        }
        
        # Update session headers
        self.session.headers.update(self.headers)
        
        # Initialize chat interface
        self.chat = Chat(self)
    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()
if __name__ == "__main__":
    # Example usage
    client = FreeGemini()
    conversation_prompt = "Hello!"
    response = client.chat.completions.create(
        model="gemini-2.0-flash",
        messages=[{"role": "user", "parts": [{"text": conversation_prompt}]}]
    )
    print(response.choices[0].message.content)