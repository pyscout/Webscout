import time
import uuid
import json
import re
from typing import List, Dict, Optional, Union, Generator, Any

# Import base classes and utility structures
from .base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from .utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage,
    format_prompt, get_system_prompt, count_tokens  # Import format_prompt and get_system_prompt
)

# Import LitAgent for browser fingerprinting
from webscout.litagent import LitAgent

# Import curl_cffi for better request handling
from curl_cffi.requests import Session
from curl_cffi import CurlError

# ANSI escape codes for formatting
BOLD = "\033[1m"
RED = "\033[91m"
RESET = "\033[0m"

class Completions(BaseCompletions):
    def __init__(self, client: 'TypefullyAI'):
        self._client = client

    def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        stream: bool = False,
        temperature: Optional[float] = None,
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Creates a model response for the given chat conversation.
        Mimics openai.chat.completions.create
        """
        # Extract system message using get_system_prompt utility
        system_prompt = get_system_prompt(messages) or self._client.system_prompt

        # Format the conversation using format_prompt utility
        # Use add_special_tokens=True to format as "User: ... Assistant: ..."
        # Use do_continue=True to ensure it ends with "Assistant: " for model to continue
        conversation_prompt = format_prompt(
            messages, 
            add_special_tokens=True, 
            do_continue=True,
            include_system=False  # System prompt is sent separately
        )

        # Prepare the payload for Typefully API
        payload = {
            "prompt": conversation_prompt,
            "systemPrompt": system_prompt,
            "modelIdentifier": self._client.convert_model_name(model),
            "outputLength": max_tokens if max_tokens is not None else self._client.output_length
        }

        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())

        if stream:
            return self._create_streaming(request_id, created_time, model, payload)
        else:
            return self._create_non_streaming(request_id, created_time, model, payload)

    def _create_streaming(
        self,
        request_id: str,
        created_time: int,
        model: str,
        payload: Dict[str, Any]
    ) -> Generator[ChatCompletionChunk, None, None]:
        """Implementation for streaming chat completions."""
        try:
            # Make the streaming request
            response = self._client.session.post(
                self._client.api_endpoint, 
                headers=self._client.headers, 
                json=payload, 
                stream=True, 
                timeout=self._client.timeout,
                impersonate="chrome120"
            )

            if not response.ok:
                raise IOError(f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}")

            streaming_text = ""
            
            for chunk in response.iter_content(chunk_size=None):
                if not chunk:
                    continue
                
                chunk_str = chunk.decode('utf-8', errors='replace')
                content = self._client._typefully_extractor(chunk_str)
                
                if content:
                    streaming_text += content
                    
                    # Create the delta object
                    delta = ChoiceDelta(
                        content=content,
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

            # Final chunk with finish_reason="stop"
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

        except CurlError as e:
            print(f"{RED}Error during Typefully streaming request (CurlError): {e}{RESET}")
            raise IOError(f"Typefully streaming request failed (CurlError): {e}") from e
        except Exception as e:
            print(f"{RED}Error during Typefully streaming request: {e}{RESET}")
            raise IOError(f"Typefully streaming request failed: {e}") from e

    def _create_non_streaming(
        self,
        request_id: str,
        created_time: int,
        model: str,
        payload: Dict[str, Any]
    ) -> ChatCompletion:
        """Implementation for non-streaming chat completions."""
        try:
            # Make the non-streaming request
            response = self._client.session.post(
                self._client.api_endpoint, 
                headers=self._client.headers, 
                json=payload, 
                stream=True, 
                timeout=self._client.timeout,
                impersonate="chrome120"
            )

            if not response.ok:
                raise IOError(f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}")

            # Collect the full response
            full_text = ""
            for chunk in response.iter_content(chunk_size=None):
                if not chunk:
                    continue
                
                chunk_str = chunk.decode('utf-8', errors='replace')
                content = self._client._typefully_extractor(chunk_str)
                
                if content:
                    full_text += content

            # Format the text (replace escaped newlines)
            full_text = full_text.replace('\\n', '\n').replace('\\n\\n', '\n\n')

            # Estimate token counts
            prompt_tokens = count_tokens(payload.get("prompt", "")) + count_tokens(payload.get("systemPrompt", ""))
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

        except CurlError as e:
            print(f"{RED}Error during Typefully non-streaming request (CurlError): {e}{RESET}")
            raise IOError(f"Typefully request failed (CurlError): {e}") from e
        except Exception as e:
            print(f"{RED}Error during Typefully non-streaming request: {e}{RESET}")
            raise IOError(f"Typefully request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'TypefullyAI'):
        self.completions = Completions(client)

class TypefullyAI(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for Typefully AI API.

    Usage:
        client = TypefullyAI()
        response = client.chat.completions.create(
            model="openai:gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print(response.choices[0].message.content)
    """

    AVAILABLE_MODELS = [
        "openai:gpt-4o-mini", 
        "openai:gpt-4o", 
        "anthropic:claude-3-5-haiku-20241022", 
        "groq:llama-3.3-70b-versatile"
    ]

    def __init__(
        self,
        timeout: int = 30,

    ):
        """
        Initialize the TypefullyAI client.

        Args:
            timeout: Request timeout in seconds
            proxies: Optional proxy configuration
            system_prompt: Default system prompt
            output_length: Maximum length of the generated output
        """
        self.timeout = timeout
        self.api_endpoint = "https://typefully.com/tools/ai/api/completion"

        # Initialize curl_cffi Session
        self.session = Session()

        # Initialize LitAgent for user agent generation
        agent = LitAgent()
        self.user_agent = agent.random()

        # Set headers
        self.headers = {
            "authority": "typefully.com",
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9",
            "content-type": "application/json",
            "dnt": "1",
            "origin": "https://typefully.com",
            "referer": "https://typefully.com/tools/ai/chat-gpt-alternative",
            "sec-ch-ua": '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "user-agent": self.user_agent
        }

        # Update curl_cffi session headers and proxies
        self.session.headers.update(self.headers)

        # Initialize chat interface
        self.chat = Chat(self)

    @staticmethod
    def _typefully_extractor(chunk: str) -> Optional[str]:
        """Extracts content from the Typefully stream format '0:"..."'."""
        if isinstance(chunk, str):
            match = re.search(r'0:"(.*?)"(?=,|$)', chunk)
            if match:
                # Decode potential unicode escapes like \u00e9 and handle escaped quotes/backslashes
                content = match.group(1).encode().decode('unicode_escape')
                return content.replace('\\\\', '\\').replace('\\"', '"')
        return None

    def convert_model_name(self, model: str) -> str:
        """
        Convert model names to ones supported by Typefully.

        Args:
            model: Model name to convert

        Returns:
            Typefully model name
        """
        # If the model is already a valid Typefully model, return it
        if model in self.AVAILABLE_MODELS:
            return model

        # Map common OpenAI model names to Typefully models
        model_mapping = {
            "gpt-4o-mini": "openai:gpt-4o-mini",
            "gpt-4o": "openai:gpt-4o",
            "claude-3-5-haiku": "anthropic:claude-3-5-haiku-20241022",
            "llama-3.3-70b": "groq:llama-3.3-70b-versatile"
        }

        if model in model_mapping:
            return model_mapping[model]

        # Default to the most capable model
        print(f"{RED}Warning: Unknown model '{model}'. Using 'openai:gpt-4o-mini' instead.{RESET}")
        return "openai:gpt-4o-mini"

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()

