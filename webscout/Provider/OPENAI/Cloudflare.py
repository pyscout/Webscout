import json
import time
import uuid
import re
from typing import List, Dict, Optional, Union, Generator, Any

from curl_cffi import CurlError
from curl_cffi.requests import Session
from uuid import uuid4

# Import base classes and utility structures
from webscout.Provider.OPENAI.base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from webscout.Provider.OPENAI.utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage, count_tokens
)

from webscout.AIutel import sanitize_stream
from webscout.litagent import LitAgent

class Completions(BaseCompletions):
    def __init__(self, client: 'Cloudflare'):
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
        Create a chat completion with Cloudflare API.
        
        Args:
            model: The model to use (from AVAILABLE_MODELS)
            messages: List of message dictionaries with 'role' and 'content'
            max_tokens: Maximum number of tokens to generate
            stream: Whether to stream the response
            temperature: Sampling temperature (0-1)
            top_p: Nucleus sampling parameter (0-1)
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            If stream=False, returns a ChatCompletion object
            If stream=True, returns a Generator yielding ChatCompletionChunk objects
        """
        # Prepare the payload
        payload = {
            "messages": messages,
            "lora": None,
            "model": model,
            "max_tokens": max_tokens or 600,
            "stream": True  # Always use streaming API
        }
        
        # Generate request ID and timestamp
        request_id = str(uuid.uuid4())
        created_time = int(time.time())
        
        # Use streaming implementation if requested
        if stream:
            return self._create_streaming(
                request_id=request_id,
                created_time=created_time,
                model=model,
                payload=payload,
                timeout=timeout,
                proxies=proxies
            )
        
        # Otherwise use non-streaming implementation
        return self._create_non_streaming(
            request_id=request_id,
            created_time=created_time,
            model=model,
            payload=payload,
            timeout=timeout,
            proxies=proxies
        )
    
    def _create_streaming(
        self,
        *,
        request_id: str,
        created_time: int,
        model: str,
        payload: Dict[str, Any],
        timeout: Optional[int] = None,
        proxies: Optional[dict] = None
    ) -> Generator[ChatCompletionChunk, None, None]:
        """Implementation for streaming chat completions."""
        original_proxies = self._client.session.proxies
        if proxies is not None:
            self._client.session.proxies = proxies
        try:
            response = self._client.session.post(
                self._client.chat_endpoint,
                headers=self._client.headers,
                cookies=self._client.cookies,
                data=json.dumps(payload),
                stream=True,
                timeout=timeout if timeout is not None else self._client.timeout,
                impersonate="chrome120"
            )
            response.raise_for_status()
            
            # Process the stream using sanitize_stream
            # This handles the extraction of content from Cloudflare's response format
            processed_stream = sanitize_stream(
                data=response.iter_content(chunk_size=None),
                intro_value=None,
                to_json=False,
                skip_markers=None,
                content_extractor=self._cloudflare_extractor,
                yield_raw_on_error=False
            )
            
            # Track accumulated content for token counting
            accumulated_content = ""
            
            # Stream the chunks
            for content_chunk in processed_stream:
                if content_chunk and isinstance(content_chunk, str):
                    accumulated_content += content_chunk
                    
                    # Create and yield a chunk
                    delta = ChoiceDelta(content=content_chunk)
                    choice = Choice(index=0, delta=delta, finish_reason=None)
                    
                    # Estimate token usage using count_tokens
                    prompt_tokens = count_tokens([msg.get("content", "") for msg in payload["messages"]])
                    completion_tokens = count_tokens(accumulated_content)
                    
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
            
        except CurlError as e:
            raise IOError(f"Cloudflare streaming request failed (CurlError): {e}") from e
        except Exception as e:
            raise IOError(f"Cloudflare streaming request failed: {e}") from e
        finally:
            if proxies is not None:
                self._client.session.proxies = original_proxies
    
    def _create_non_streaming(
        self,
        *,
        request_id: str,
        created_time: int,
        model: str,
        payload: Dict[str, Any],
        timeout: Optional[int] = None,
        proxies: Optional[dict] = None
    ) -> ChatCompletion:
        """Implementation for non-streaming chat completions."""
        original_proxies = self._client.session.proxies
        if proxies is not None:
            self._client.session.proxies = proxies
        try:
            response = self._client.session.post(
                self._client.chat_endpoint,
                headers=self._client.headers,
                cookies=self._client.cookies,
                data=json.dumps(payload),
                stream=True,  # Still use streaming API but collect all chunks
                timeout=timeout if timeout is not None else self._client.timeout,
                impersonate="chrome120"
            )
            response.raise_for_status()
            
            # Process the stream and collect all content
            processed_stream = sanitize_stream(
                data=response.iter_content(chunk_size=None),
                intro_value=None,
                to_json=False,
                skip_markers=None,
                content_extractor=self._cloudflare_extractor,
                yield_raw_on_error=False
            )
            
            full_content = ""
            for content_chunk in processed_stream:
                if content_chunk and isinstance(content_chunk, str):
                    full_content += content_chunk
            
            # Create the completion message
            message = ChatCompletionMessage(
                role="assistant",
                content=full_content
            )
            
            # Create the choice
            choice = Choice(
                index=0,
                message=message,
                finish_reason="stop"
            )
            
            # Estimate token usage using count_tokens
            prompt_tokens = count_tokens([msg.get("content", "") for msg in payload["messages"]])
            completion_tokens = count_tokens(full_content)
            usage = CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
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
            raise IOError(f"Cloudflare request failed (CurlError): {e}") from e
        except Exception as e:
            raise IOError(f"Cloudflare request failed: {e}") from e
        finally:
            if proxies is not None:
                self._client.session.proxies = original_proxies
    
    @staticmethod
    def _cloudflare_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        """
        Extracts content from Cloudflare stream JSON objects.
        
        Args:
            chunk: The chunk to extract content from
            
        Returns:
            Extracted content or None if extraction failed
        """
        if isinstance(chunk, str):
            # Use re.search to find the pattern 0:"<content>"
            match = re.search(r'0:"(.*?)"(?=,|$)', chunk)
            if match:
                # Decode potential unicode escapes and handle escaped quotes/backslashes
                content = match.group(1).encode().decode('unicode_escape')
                return content.replace('\\\\', '\\').replace('\\"', '"')
        return None


class Chat(BaseChat):
    def __init__(self, client: 'Cloudflare'):
        self.completions = Completions(client)


class Cloudflare(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for Cloudflare API.
    
    Usage:
        client = Cloudflare()
        response = client.chat.completions.create(
            model="@cf/meta/llama-3-8b-instruct",
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print(response.choices[0].message.content)
    """
    
    AVAILABLE_MODELS = [
        "@hf/thebloke/deepseek-coder-6.7b-base-awq",
        "@hf/thebloke/deepseek-coder-6.7b-instruct-awq",
        "@cf/deepseek-ai/deepseek-math-7b-instruct",
        "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b",
        "@cf/thebloke/discolm-german-7b-v1-awq",
        "@cf/tiiuae/falcon-7b-instruct",
        "@cf/google/gemma-3-12b-it",
        "@hf/google/gemma-7b-it",
        "@hf/nousresearch/hermes-2-pro-mistral-7b",
        "@hf/thebloke/llama-2-13b-chat-awq",
        "@cf/meta/llama-2-7b-chat-fp16",
        "@cf/meta/llama-2-7b-chat-int8",
        "@cf/meta/llama-3-8b-instruct",
        "@cf/meta/llama-3-8b-instruct-awq",
        "@cf/meta/llama-3.1-8b-instruct-awq",
        "@cf/meta/llama-3.1-8b-instruct-fp8",
        "@cf/meta/llama-3.2-11b-vision-instruct",
        "@cf/meta/llama-3.2-1b-instruct",
        "@cf/meta/llama-3.2-3b-instruct",
        "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        "@cf/meta/llama-4-scout-17b-16e-instruct",
        "@cf/meta/llama-guard-3-8b",
        "@hf/thebloke/llamaguard-7b-awq",
        "@hf/meta-llama/meta-llama-3-8b-instruct",
        "@cf/mistral/mistral-7b-instruct-v0.1",
        "@hf/thebloke/mistral-7b-instruct-v0.1-awq",
        "@hf/mistral/mistral-7b-instruct-v0.2",
        "@cf/mistralai/mistral-small-3.1-24b-instruct",
        "@hf/thebloke/neural-chat-7b-v3-1-awq",
        "@cf/openchat/openchat-3.5-0106",
        "@hf/thebloke/openhermes-2.5-mistral-7b-awq",
        "@cf/microsoft/phi-2",
        "@cf/qwen/qwen1.5-0.5b-chat",
        "@cf/qwen/qwen1.5-1.8b-chat",
        "@cf/qwen/qwen1.5-14b-chat-awq",
        "@cf/qwen/qwen1.5-7b-chat-awq",
        "@cf/qwen/qwen2.5-coder-32b-instruct",
        "@cf/qwen/qwq-32b",
        "@cf/defog/sqlcoder-7b-2",
        "@hf/nexusflow/starling-lm-7b-beta",
        "@cf/tinyllama/tinyllama-1.1b-chat-v1.0",
        "@cf/fblgit/una-cybertron-7b-v2-bf16",
        "@hf/thebloke/zephyr-7b-beta-awq"
    ]
    
    def __init__(
        self,
        api_key: Optional[str] = None,  # Not used but included for compatibility
        proxies: Optional[dict] = None
    ):
        """
        Initialize the Cloudflare client.
        
        Args:
            api_key: Not used but included for compatibility with OpenAI interface
            proxies: Optional proxy configuration dictionary
        """
        super().__init__(proxies=proxies)
        self.timeout = 30
        self.chat_endpoint = "https://playground.ai.cloudflare.com/api/inference"
        
        # Set headers
        self.headers = {
            'Accept': 'text/event-stream',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9,en-IN;q=0.8',
            'Content-Type': 'application/json',
            'DNT': '1',
            'Origin': 'https://playground.ai.cloudflare.com',
            'Referer': 'https://playground.ai.cloudflare.com/',
            'Sec-CH-UA': '"Not)A;Brand";v="99", "Microsoft Edge";v="127", "Chromium";v="127"',
            'Sec-CH-UA-Mobile': '?0',
            'Sec-CH-UA-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': LitAgent().random()
        }
        
        # Set cookies
        self.cookies = {
            'cfzs_amplitude': uuid4().hex,
            'cfz_amplitude': uuid4().hex,
            '__cf_bm': uuid4().hex,
        }
        
        # Apply headers to session
        self.session.headers.update(self.headers)
        
        # Initialize chat interface
        self.chat = Chat(self)

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()

    # @classmethod
    # def models(cls):
    #     """Return the list of available models for Cloudflare."""
    #     return cls.AVAILABLE_MODELS