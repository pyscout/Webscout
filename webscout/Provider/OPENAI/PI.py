from curl_cffi.requests import Session
from curl_cffi import CurlError
import json
import time
import uuid
import re
import threading
from typing import List, Dict, Optional, Union, Generator, Any
from uuid import uuid4

# Import base classes and utility structures
from webscout.Provider.OPENAI.base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from webscout.Provider.OPENAI.utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage
)

# Attempt to import LitAgent, fallback if not available
try:
    from webscout.litagent import LitAgent
except ImportError:
    pass

# --- PI.ai Client ---

class Completions(BaseCompletions):
    def __init__(self, client: 'PiAI'):
        self._client = client

    def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = 2048,
        stream: bool = False,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        timeout: Optional[int] = None,
        proxies: Optional[Dict[str, str]] = None,
        voice: bool = False,
        voice_name: str = "voice3",
        output_file: str = "PiAI.mp3",
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Creates a model response for the given chat conversation.
        Mimics openai.chat.completions.create with Pi.ai specific features.
        """
        # Validate voice settings
        if voice and voice_name not in self._client.AVAILABLE_VOICES:
            raise ValueError(f"Voice '{voice_name}' not available. Choose from: {list(self._client.AVAILABLE_VOICES.keys())}")

        # Use format_prompt from utils.py to convert OpenAI messages format to Pi.ai prompt
        from webscout.Provider.OPENAI.utils import format_prompt, count_tokens
        prompt = format_prompt(messages, do_continue=True, add_special_tokens=True)
        
        # Ensure conversation is started
        if not self._client.conversation_id:
            self._client.start_conversation()

        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())

        # Use count_tokens for prompt token counting
        prompt_tokens = count_tokens(prompt)

        if stream:
            return self._create_stream(
                request_id, created_time, model, prompt, 
                timeout, proxies, voice, voice_name, output_file, prompt_tokens
            )
        else:
            return self._create_non_stream(
                request_id, created_time, model, prompt, 
                timeout, proxies, voice, voice_name, output_file, prompt_tokens
            )

    def _create_stream(
        self, request_id: str, created_time: int, model: str, prompt: str,
        timeout: Optional[int] = None, proxies: Optional[Dict[str, str]] = None,
        voice: bool = False, voice_name: str = "voice3", output_file: str = "PiAI.mp3",
        prompt_tokens: Optional[int] = None
    ) -> Generator[ChatCompletionChunk, None, None]:
        
        data = {
            'text': prompt,
            'conversation': self._client.conversation_id
        }

        try:
            # Try primary URL first
            current_url = self._client.primary_url
            response = self._client.session.post(
                current_url,
                json=data,
                stream=True,
                timeout=timeout or self._client.timeout,
                impersonate="chrome110"
            )

            # If primary URL fails, try fallback URL
            if not response.ok and current_url == self._client.primary_url:
                current_url = self._client.fallback_url
                response = self._client.session.post(
                    current_url,
                    json=data,
                    stream=True,
                    timeout=timeout or self._client.timeout,
                    impersonate="chrome110"
                )

            response.raise_for_status()

            # Track token usage across chunks
            # prompt_tokens = len(prompt.split()) if prompt else 0
            completion_tokens = 0
            total_tokens = prompt_tokens

            sids = []
            streaming_text = ""
            full_raw_data_for_sids = ""

            # Process streaming response
            for line_bytes in response.iter_lines():
                if line_bytes:
                    line = line_bytes.decode('utf-8')
                    full_raw_data_for_sids += line + "\n"
                    
                    if line.startswith("data: "):
                        json_line_str = line[6:]
                        try:
                            chunk_data = json.loads(json_line_str)
                            content = chunk_data.get('text', '')
                            
                            if content:
                                # Calculate incremental content
                                new_content = content[len(streaming_text):] if len(content) > len(streaming_text) else content
                                streaming_text = content
                                completion_tokens += len(new_content.split()) if new_content else 0
                                total_tokens = prompt_tokens + completion_tokens

                                # Create OpenAI-compatible chunk
                                delta = ChoiceDelta(
                                    content=new_content,
                                    role="assistant"
                                )

                                choice = Choice(
                                    index=0,
                                    delta=delta,
                                    finish_reason=None
                                )

                                chunk = ChatCompletionChunk(
                                    id=request_id,
                                    choices=[choice],
                                    created=created_time,
                                    model=model
                                )

                                yield chunk

                        except (json.JSONDecodeError, KeyError):
                            continue

            # Send final chunk with finish_reason
            final_choice = Choice(
                index=0,
                delta=ChoiceDelta(),
                finish_reason="stop"
            )

            final_chunk = ChatCompletionChunk(
                id=request_id,
                choices=[final_choice],
                created=created_time,
                model=model
            )

            yield final_chunk

            # Handle voice generation
            if voice and voice_name:
                sids = re.findall(r'"sid":"(.*?)"', full_raw_data_for_sids)
                second_sid = sids[1] if len(sids) >= 2 else None
                if second_sid:
                    threading.Thread(
                        target=self._client.download_audio_threaded,
                        args=(voice_name, second_sid, output_file)
                    ).start()

        except CurlError as e:
            raise IOError(f"PI.ai request failed (CurlError): {e}") from e
        except Exception as e:
            raise IOError(f"PI.ai request failed: {e}") from e

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str, prompt: str,
        timeout: Optional[int] = None, proxies: Optional[Dict[str, str]] = None,
        voice: bool = False, voice_name: str = "voice3", output_file: str = "PiAI.mp3",
        prompt_tokens: Optional[int] = None
    ) -> ChatCompletion:
        
        # Collect streaming response into a single response
        full_content = ""
        completion_tokens = 0
        # prompt_tokens = len(prompt.split()) if prompt else 0  # replaced

        # Use provided prompt_tokens if available
        if prompt_tokens is None:
            from webscout.Provider.OPENAI.utils import count_tokens
            prompt_tokens = count_tokens(prompt)

        for chunk in self._create_stream(
            request_id, created_time, model, prompt, 
            timeout, proxies, voice, voice_name, output_file, prompt_tokens
        ):
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                full_content += chunk.choices[0].delta.content
                completion_tokens += len(chunk.choices[0].delta.content.split())

        # Create final completion response
        message = ChatCompletionMessage(
            role="assistant",
            content=full_content
        )

        choice = Choice(
            index=0,
            message=message,
            finish_reason="stop"
        )

        usage = CompletionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens
        )

        completion = ChatCompletion(
            id=request_id,
            choices=[choice],
            created=created_time,
            model=model,
            usage=usage
        )

        return completion


class Chat(BaseChat):
    def __init__(self, client: 'PiAI'):
        self.completions = Completions(client)


class PiAI(OpenAICompatibleProvider):
    """
    PiAI provider following OpenAI-compatible interface.
    
    Supports Pi.ai specific features like voice generation and conversation management.
    """
    
    AVAILABLE_MODELS = ["inflection_3_pi"]
    AVAILABLE_VOICES: Dict[str, int] = {
        "voice1": 1,
        "voice2": 2,
        "voice3": 3,
        "voice4": 4,
        "voice5": 5,
        "voice6": 6,
        "voice7": 7,
        "voice8": 8
    }

    def __init__(
        self, 
        api_key: Optional[str] = None,
        timeout: int = 30,
        proxies: Optional[Dict[str, str]] = None,
        **kwargs: Any
    ):
        """
        Initialize PI.ai provider.
        
        Args:
            api_key: Not used for Pi.ai but kept for compatibility
            timeout: Request timeout in seconds
            proxies: Proxy configuration
            **kwargs: Additional arguments
        """
        super().__init__(proxies=proxies)
        self.timeout = timeout
        self.conversation_id = None
        
        # Setup URLs
        self.primary_url = 'https://pi.ai/api/chat'
        self.fallback_url = 'https://pi.ai/api/v2/chat'
        
        # Setup headers
        self.headers = {
            'Accept': 'text/event-stream',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9,en-IN;q=0.8',
            'Content-Type': 'application/json',
            'DNT': '1',
            'Origin': 'https://pi.ai',
            'Referer': 'https://pi.ai/talk',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': LitAgent().random() if 'LitAgent' in globals() else 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'X-Api-Version': '3'
        }
        
        # Setup cookies
        self.cookies = {
            '__cf_bm': uuid4().hex
        }
        
        # Replace the base session with curl_cffi Session
        self.session = Session()
        
        # Configure session
        self.session.headers.update(self.headers)
        if proxies:
            self.session.proxies = proxies
        
        # Set cookies on the session
        for name, value in self.cookies.items():
            self.session.cookies.set(name, value)
        
        # Initialize chat interface
        self.chat = Chat(self)
        
        # Start conversation
        self.start_conversation()

    def start_conversation(self) -> str:
        """
        Initializes a new conversation and returns the conversation ID.
        """
        try:
            response = self.session.post(
                "https://pi.ai/api/chat/start",
                json={},
                timeout=self.timeout,
                impersonate="chrome110"
            )
            response.raise_for_status()

            data = response.json()
            if 'conversations' in data and data['conversations'] and 'sid' in data['conversations'][0]:
                self.conversation_id = data['conversations'][0]['sid']
                return self.conversation_id
            else:
                raise IOError(f"Unexpected response structure from start API: {data}")

        except CurlError as e:
            raise IOError(f"Failed to start conversation (CurlError): {e}") from e
        except Exception as e:
            raise IOError(f"Failed to start conversation: {e}") from e

    def download_audio_threaded(self, voice_name: str, second_sid: str, output_file: str) -> None:
        """Downloads audio in a separate thread."""
        params = {
            'mode': 'eager',
            'voice': f'voice{self.AVAILABLE_VOICES[voice_name]}',
            'messageSid': second_sid,
        }

        try:
            audio_response = self.session.get(
                'https://pi.ai/api/chat/voice',
                params=params,
                timeout=self.timeout,
                impersonate="chrome110"
            )
            audio_response.raise_for_status()

            with open(output_file, "wb") as file:
                file.write(audio_response.content)

        except (CurlError, Exception):
            # Optionally log the error
            pass

    @property
    def models(self):
        """Return available models in OpenAI-compatible format."""
        class _ModelList:
            def list(inner_self):
                return PiAI.AVAILABLE_MODELS
        return _ModelList()


# Example usage
if __name__ == "__main__":
    # Test the OpenAI-compatible interface
    client = PiAI()
    
    # Test streaming
    print("Testing streaming response:")
    response = client.chat.completions.create(
        model="inflection_3_pi",
        messages=[
            {"role": "user", "content": "Hello! Say 'Hi' in one word."}
        ],
        stream=True
    )
    
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print()
    
    # Test non-streaming
    print("\nTesting non-streaming response:")
    response = client.chat.completions.create(
        model="inflection_3_pi",
        messages=[
            {"role": "user", "content": "Tell me a short joke."}
        ],
        stream=False
    )
    
    print(response.choices[0].message.content)
    print(f"Usage: {response.usage}")