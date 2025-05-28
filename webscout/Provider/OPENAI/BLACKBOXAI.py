import requests
import random
import string
import base64
from datetime import datetime, timedelta
from typing import Generator, List, Dict, Optional, Any, Union
import json # Not used directly in this snippet, but often useful
import uuid
import time
import codecs
import re # Ensure re is imported at the module level

# Import base classes and utility structures
from webscout.Provider.OPENAI.base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from webscout.Provider.OPENAI.utils import (
    ChatCompletion, Choice,
    ChatCompletionMessage, CompletionUsage, count_tokens,
    ChatCompletionChunk, ChoiceDelta # Added for streaming return type
)
from webscout.litagent import LitAgent, agent
agent = LitAgent()

def to_data_uri(image_data):
    """Convert image data to a data URI format"""
    if isinstance(image_data, str):
        # Assume it's already a data URI
        return image_data

    # Encode binary data to base64
    encoded = base64.b64encode(image_data).decode('utf-8')

    # Determine MIME type (simplified)
    mime_type = "image/jpeg"  # Default
    if image_data.startswith(b'\x89PNG'):
        mime_type = "image/png"
    elif image_data.startswith(b'\xff\xd8'):
        mime_type = "image/jpeg"
    elif image_data.startswith(b'GIF'):
        mime_type = "image/gif"

    return f"data:{mime_type};base64,{encoded}"

def clean_text(text: str) -> str: # Add type hints
    if not isinstance(text, str):
        return text

    # Step 1: Handle specific prefixes observed in BlackboxAI streamed chunks.
    # These prefixes are 'k(', '@ ', 'H ', '8 '.
    # Apply this logic first.
    # Note: This assumes that only one such prefix will occur at the beginning of a text segment.
    # If multiple prefixes could stack (e.g., "k(@ Hello"), this logic would need adjustment,
    # but based on current examples, they appear mutually exclusive per chunk.
    
    # original_text_for_prefix_check = text # Store original for sequential prefix checking if needed, though current logic is fine.

    if text.startswith("k("):
        text = text[2:]
    elif text.startswith("@ "): # Important: space after @
        text = text[2:]
    elif text.startswith("H "): # Important: space after H
        text = text[2:]
    elif text.startswith("8 "): # Important: space after 8
        text = text[2:]
    # Add any other confirmed prefixes here in elif clauses.

    # Step 2: Remove specific noise characters like '@' that might still be present
    # (e.g., if they are not prefixes but appear at the end of words like "Hello!@").
    # This regex removes '@' if it's preceded by an alphanumeric character or '!'
    # and is not followed by a non-whitespace character (i.e., it's at the end of a word or before a space).
    text = re.sub(r'(?<=[a-zA-Z0-9!])@(?![^\s])', '', text)


    # Step 3: Apply the original cleaning for null bytes and ASCII control characters.
    if text is not None: # text could become None if original input was None, though isinstance check handles this.
        text = text.replace('\x00', '')  # Remove null bytes
        # This regex matches control characters except \n, \r, \t (newlines, carriage returns, tabs)
        text = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    return text


class Completions(BaseCompletions):
    def __init__(self, client: 'BLACKBOXAI'):
        self._client = client

    def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        stream: bool = False,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        timeout: Optional[int] = None,
        proxies: Optional[dict] = None,
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Create a chat completion with BlackboxAI API.

        Args:
            model: The model to use (from AVAILABLE_MODELS)
            messages: List of message dictionaries with 'role' and 'content'
            max_tokens: Maximum number of tokens to generate
            stream: If True, yields streaming chunks
            temperature: Sampling temperature (0-1)
            top_p: Nucleus sampling parameter (0-1)
            **kwargs: Additional parameters to pass to the API

        Returns:
            Returns a ChatCompletion object or a generator for streaming
        """
        # Generate request ID and timestamp
        request_id = str(uuid.uuid4())
        created_time = int(time.time())

        # Extract system message if present
        system_message = "You are a helpful AI assistant."
        for msg in messages:
            if msg.get("role") == "system":
                system_message = msg.get("content")
                break

        # Look for any image content
        media = []
        for msg in messages:
            if msg.get("role") == "user":
                # Check for image attachments in content
                content = msg.get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "image_url":
                            image_url = item.get("image_url", {})
                            if isinstance(image_url, dict) and "url" in image_url:
                                url = image_url["url"]
                                if url.startswith("data:"):
                                    # It's already a data URI
                                    image_name = f"image_{len(media)}.png"
                                    media.append((url, image_name))
                                else:
                                    # Need to fetch and convert to data URI
                                    try:
                                        image_response = requests.get(url)
                                        if image_response.ok:
                                            image_name = f"image_{len(media)}.png"
                                            media.append((image_response.content, image_name))
                                    except Exception as e:
                                        pass

        # Check if streaming is requested and raise an error
        if stream:
            return self._create_streaming(
                request_id=request_id,
                created_time=created_time,
                model=model,
                messages=messages,
                system_message=system_message,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                media=media,
                timeout=timeout,
                proxies=proxies
            )

        # Use non-streaming implementation
        return self._create_non_streaming(
            request_id=request_id,
            created_time=created_time,
            model=model,
            messages=messages,
            system_message=system_message,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            media=media,
            timeout=timeout,
            proxies=proxies
        )


    def _create_non_streaming(
        self,
        *,
        request_id: str,
        created_time: int,
        model: str,
        messages: List[Dict[str, Any]],
        system_message: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        media: List = None,
        timeout: Optional[int] = None,
        proxies: Optional[dict] = None
    ) -> ChatCompletion:
        """Implementation for non-streaming chat completions."""
        original_proxies = self._client.session.proxies
        if proxies is not None:
            self._client.session.proxies = proxies
        try:
            # Prepare user messages for BlackboxAI API format
            blackbox_messages = []
            for i, msg in enumerate(messages):
                if msg["role"] == "system":
                    continue  # System message handled separately

                msg_id = self._client.generate_id() if i > 0 else request_id
                blackbox_messages.append({
                    "id": msg_id,
                    "content": msg["content"],
                    "role": msg["role"]
                })

            # Add image data if provided
            if media and blackbox_messages:
                blackbox_messages[-1]['data'] = {
                    "imagesData": [
                        {
                            "filePath": f"/",
                            "contents": to_data_uri(image[0])
                        } for image in media
                    ],
                    "fileText": "",
                    "title": ""
                }

            # Generate request payload with session
            request_email = f"{self._client.generate_random_string(8)}@blackbox.ai"
            session_data = self._client.generate_session(request_email)

            # Create the API request payload
            payload = self._client.create_request_payload(
                messages=blackbox_messages,
                chat_id=request_id,
                system_message=system_message,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                session_data=session_data,
                model=model
            )

            # Make the API request with cookies
            response = self._client.session.post(
                self._client.api_endpoint,
                json=payload,
                headers=self._client.headers,
                cookies=self._client.cookies,
                timeout=timeout if timeout is not None else self._client.timeout
            )

            # Process the response
            full_content = ""
            if response.status_code == 200:
                # Use incremental decoder for UTF-8 to avoid splitting multi-byte chars
                decoder = codecs.getincrementaldecoder("utf-8")("replace")
                response_bytes = response.content
                response_text = decoder.decode(response_bytes, final=True)

                # Check for BlackboxAI specific error messages
                error_messages = ["service has been suspended", "api request failed", "you have reached your request limit"]
                for error_msg in error_messages:
                    if error_msg in response_text.lower():
                        raise IOError(f"BlackboxAI provider error: {error_msg}")

                # Handle possible SSE format in response
                if "data: " in response_text:
                    # Extract content from SSE format
                    content_lines = []
                    for line in response_text.split('\n'):
                        if line.startswith("data: "):
                            line = line[6:].strip()
                            # Secondary check within lines just in case, though primary check above should catch most
                            if line and not any(error_msg in line.lower() for error_msg in error_messages):
                                content_lines.append(line)
                    full_content = "".join(content_lines)
                else:
                    # Regular response
                    full_content = response_text
            else:
                # Handle error response
                raise IOError(f"BlackboxAI request failed with status code {response.status_code}: {response.text}")

            # Clean and create the completion message
            cleaned_content = clean_text(full_content) # clean_text is already applied to full_content
            message = ChatCompletionMessage(
                role="assistant",
                content=cleaned_content
            )

            # Create the choice with the message
            choice = Choice(
                index=0,
                message=message,
                finish_reason="stop"
            )

            # Estimate token usage using count_tokens
            prompt_tokens = count_tokens([str(msg.get("content", "")) for msg in messages])
            completion_tokens = count_tokens(cleaned_content)

            # Create the final completion object
            completion = ChatCompletion(
                id=request_id,
                choices=[choice],
                created=created_time,
                model=model,
                usage=CompletionUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens
                )
            )

            return completion

        except requests.exceptions.RequestException as e:
            raise IOError(f"BlackboxAI request failed due to a network error: {str(e)}") from e
        except IOError: # Re-raise IOErrors (like the one from provider error check)
            raise
        except Exception as e: # Catch other unexpected errors
            raise IOError(f"An unexpected error occurred in BlackboxAI non-streaming request: {str(e)}") from e
        finally:
            if proxies is not None:
                self._client.session.proxies = original_proxies

    def _create_streaming(
        self,
        *,
        request_id: str,
        created_time: int,
        model: str,
        messages: List[Dict[str, Any]],
        system_message: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        media: List = None,
        timeout: Optional[int] = None,
        proxies: Optional[dict] = None
    ):
        """Implementation for streaming chat completions (OpenAI-compatible chunks)."""
        original_proxies = self._client.session.proxies
        if proxies is not None:
            self._client.session.proxies = proxies
        
        # Define error messages to check
        blackbox_error_indicators = [
            "service has been suspended",
            "api request failed",
            "you have reached your request limit"
        ]

        try:
            # Prepare user messages for BlackboxAI API format
            blackbox_messages = []
            for i, msg in enumerate(messages):
                if msg["role"] == "system":
                    continue  # System message handled separately
                msg_id = self._client.generate_id() if i > 0 else request_id
                blackbox_messages.append({
                    "id": msg_id,
                    "content": msg["content"],
                    "role": msg["role"]
                })
            # Add image data if provided
            if media and blackbox_messages:
                blackbox_messages[-1]['data'] = {
                    "imagesData": [
                        {
                            "filePath": f"/",
                            "contents": to_data_uri(image[0])
                        } for image in media
                    ],
                    "fileText": "",
                    "title": ""
                }
            # Generate request payload with session
            request_email = f"{self._client.generate_random_string(8)}@blackbox.ai"
            session_data = self._client.generate_session(request_email)
            payload = self._client.create_request_payload(
                messages=blackbox_messages,
                chat_id=request_id,
                system_message=system_message,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                session_data=session_data,
                model=model
            )
            # Make the API request with cookies, stream=True
            response = self._client.session.post(
                self._client.api_endpoint,
                json=payload,
                headers=self._client.headers,
                cookies=self._client.cookies,
                stream=True,
                timeout=timeout if timeout is not None else self._client.timeout
            )
            response.raise_for_status() # Will raise HTTPError for bad status codes (4xx or 5xx)

            # Blackbox streams as raw text, no line breaks, so chunk manually
            import codecs
            buffer = bytearray()
            decoder = codecs.getincrementaldecoder("utf-8")("replace")
            chunk_size = 128  # Increased chunk_size
            # from webscout.Provider.OPENAI.utils import ChatCompletionChunk, Choice, ChoiceDelta # Already imported at top level

            for chunk_bytes in response.iter_content(chunk_size=chunk_size):
                if not chunk_bytes:
                    continue
                
                # It's possible a full error message is in a single chunk
                try:
                    potential_error_text_chunk = chunk_bytes.decode("utf-8", errors="replace")
                    for error_msg_indicator in blackbox_error_indicators:
                        if error_msg_indicator in potential_error_text_chunk.lower():
                            # Yield error chunk and stop
                            error_delta = ChoiceDelta(content=f"BlackboxAI provider error: {error_msg_indicator}", role="assistant")
                            error_choice = Choice(index=0, delta=error_delta, finish_reason="error")
                            error_chunk_obj = ChatCompletionChunk(
                                id=request_id, choices=[error_choice], created=created_time, model=model, system_fingerprint="provider_error"
                            )
                            yield error_chunk_obj
                            return
                except UnicodeDecodeError:
                    pass # Will be handled by the incremental decoder below

                buffer.extend(chunk_bytes)
                text = decoder.decode(buffer, final=False) # Decode as much as possible
                buffer.clear() # Clear buffer after decoding part of it
                
                if text:
                    cleaned_text = clean_text(text) # Apply clean_text after decoding
                    # Check for error messages in the decoded text
                    for error_msg_indicator in blackbox_error_indicators:
                        if error_msg_indicator in cleaned_text.lower():
                            error_delta = ChoiceDelta(content=f"BlackboxAI provider error: {error_msg_indicator}", role="assistant")
                            error_choice = Choice(index=0, delta=error_delta, finish_reason="error")
                            error_chunk_obj = ChatCompletionChunk(
                                id=request_id, choices=[error_choice], created=created_time, model=model, system_fingerprint="provider_error"
                            )
                            yield error_chunk_obj
                            return

                    if cleaned_text.strip(): # Ensure there's actual content
                        delta = ChoiceDelta(content=cleaned_text, role="assistant")
                        choice = Choice(index=0, delta=delta, finish_reason=None)
                        chunk_obj = ChatCompletionChunk(
                            id=request_id, choices=[choice], created=created_time, model=model, system_fingerprint=None
                        )
                        yield chunk_obj
            
            # Flush any remaining bytes
            final_text_raw = decoder.decode(b"", final=True)
            if final_text_raw:
                final_text = clean_text(final_text_raw) # Apply clean_text after final decoding
                # Check for error messages in the final decoded text
                for error_msg_indicator in blackbox_error_indicators:
                    if error_msg_indicator in final_text.lower():
                        error_delta = ChoiceDelta(content=f"BlackboxAI provider error: {error_msg_indicator}", role="assistant")
                        error_choice = Choice(index=0, delta=error_delta, finish_reason="error")
                        error_chunk_obj = ChatCompletionChunk(
                            id=request_id, choices=[error_choice], created=created_time, model=model, system_fingerprint="provider_error"
                        )
                        yield error_chunk_obj
                        return
                
                if final_text.strip(): # Ensure there's actual content
                    delta = ChoiceDelta(content=final_text, role="assistant")
                    choice = Choice(index=0, delta=delta, finish_reason="stop") # Typically, the last chunk might indicate 'stop'
                    chunk_obj = ChatCompletionChunk(
                        id=request_id, choices=[choice], created=created_time, model=model, system_fingerprint=None
                    )
                    yield chunk_obj

        except requests.exceptions.RequestException as e:
            # Yield error chunk for network-related errors
            error_message = f"BlackboxAI request failed due to a network error: {str(e)}"
            error_delta = ChoiceDelta(content=error_message, role="assistant")
            error_choice = Choice(index=0, delta=error_delta, finish_reason="error")
            error_chunk_obj = ChatCompletionChunk(
                id=request_id, choices=[error_choice], created=created_time, model=model, system_fingerprint="network_error"
            )
            yield error_chunk_obj
            return
        # No general Exception catch here to let other unexpected errors propagate if necessary,
        # or add one if all errors should be yielded as Chunks.
        # For now, only RequestException and specific provider errors are yielded as error chunks.
        finally:
            if proxies is not None:
                self._client.session.proxies = original_proxies


class Chat(BaseChat):
    def __init__(self, client: 'BLACKBOXAI'):
        self.completions = Completions(client)


class BLACKBOXAI(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for BlackboxAI API.

    Usage:
        client = BLACKBOXAI()
        response = client.chat.completions.create(
            model="GPT-4.1",
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print(response.choices[0].message.content)
    """
    # Default model
    default_model = "GPT-4.1"
    default_vision_model = default_model # This was duplicated, keeping one.
    api_endpoint = "https://www.blackbox.ai/api/chat"
    timeout = 30

    # New OpenRouter models list
    openrouter_models = [
        "Deepcoder 14B Preview",
        "DeepHermes 3 Llama 3 8B Preview",
        "DeepSeek R1 Zero",
        "Dolphin3.0 Mistral 24B",
        "Dolphin3.0 R1 Mistral 24B",
        "Flash 3",
        "Gemini 2.0 Flash Experimental",
        "Gemma 2 9B",
        "Gemma 3 12B",
        "Gemma 3 1B",
        "Gemma 3 27B",
        "Gemma 3 4B",
        "Kimi VL A3B Thinking",
        "Llama 3.1 8B Instruct",
        "Llama 3.1 Nemotron Ultra 253B v1",
        "Llama 3.2 11B Vision Instruct",
        "Llama 3.2 1B Instruct",
        "Llama 3.2 3B Instruct",
        "Llama 3.3 70B Instruct",
        "Llama 3.3 Nemotron Super 49B v1",
        "Llama 4 Maverick",
        "Llama 4 Scout",
        "Mistral 7B Instruct",
        "Mistral Nemo",
        "Mistral Small 3",
        "Mistral Small 3.1 24B",
        "Molmo 7B D",
        "Moonlight 16B A3B Instruct",
        "Qwen2.5 72B Instruct",
        "Qwen2.5 7B Instruct",
        "Qwen2.5 Coder 32B Instruct",
        "Qwen2.5 VL 32B Instruct",
        "Qwen2.5 VL 3B Instruct",
        "Qwen2.5 VL 72B Instruct",
        "Qwen2.5-VL 7B Instruct",
        "Qwerky 72B",
        "QwQ 32B",
        "QwQ 32B Preview",
        "QwQ 32B RpR v1",
        "R1",
        "R1 Distill Llama 70B",
        "R1 Distill Qwen 14B",
        "R1 Distill Qwen 32B",
    ]

    # New base models list
    models = [
        "gpt-4.1-mini", # Added new model
        default_model,
        "o3-mini",
        "gpt-4.1-nano",
        "Claude Opus 4",  # Added Claude Opus 4
        "Claude Sonnet 4",  # Added Claude Sonnet 4
        "Claude-sonnet-3.7",
        "Claude-sonnet-3.5",
        "Grok 3",  # Added Grok 3
        "Gemini 2.5 Pro",  # Added Gemini 2.5 Pro
        "UI-TARS 72B",  # Added UI-TARS 72B
        "DeepSeek-R1",
        "Mistral-Small-24B-Instruct-2501",
        *openrouter_models,
        # Trending agent modes (names)
        'Python Agent', 'HTML Agent', 'Builder Agent', 'Java Agent', 'JavaScript Agent',
        'React Agent', 'Android Agent', 'Flutter Agent', 'Next.js Agent', 'AngularJS Agent',
        'Swift Agent', 'MongoDB Agent', 'PyTorch Agent', 'Xcode Agent', 'Azure Agent',
        'Bitbucket Agent', 'DigitalOcean Agent', 'Docker Agent', 'Electron Agent',
        'Erlang Agent', 'FastAPI Agent', 'Firebase Agent', 'Flask Agent', 'Git Agent',
        'Gitlab Agent', 'Go Agent', 'Godot Agent', 'Google Cloud Agent', 'Heroku Agent'
    ]

    # Models that support vision capabilities
    vision_models = [default_vision_model, 'o3-mini', "Llama 3.2 11B Vision Instruct", "Gemini 2.5 Pro", "Claude Sonnet 4", "Claude Opus 4", "UI-TARS 72B"] # Added Llama vision, Gemini 2.5 Pro, Claude Sonnet 4, Claude Opus 4, and UI-TARS 72B

    # Models that can be directly selected by users
    userSelectedModel = ['o3-mini', 'Claude Opus 4', 'Claude Sonnet 4', 'Claude-sonnet-3.7', 'Claude-sonnet-3.5', 'Grok 3', 'Gemini 2.5 Pro', 'UI-TARS 72B', 'DeepSeek-R1', 'Mistral-Small-24B-Instruct-2501'] + openrouter_models

    # Agent mode configurations
    agentMode = {
        # OpenRouter Free
        'Deepcoder 14B Preview': {'mode': True, 'id': "agentica-org/deepcoder-14b-preview:free", 'name': "Deepcoder 14B Preview"},
        'DeepHermes 3 Llama 3 8B Preview': {'mode': True, 'id': "nousresearch/deephermes-3-llama-3-8b-preview:free", 'name': "DeepHermes 3 Llama 3 8B Preview"},
        'DeepSeek R1 Zero': {'mode': True, 'id': "deepseek/deepseek-r1-zero:free", 'name': "DeepSeek R1 Zero"},
        'Dolphin3.0 Mistral 24B': {'mode': True, 'id': "cognitivecomputations/dolphin3.0-mistral-24b:free", 'name': "Dolphin3.0 Mistral 24B"},
        'Dolphin3.0 R1 Mistral 24B': {'mode': True, 'id': "cognitivecomputations/dolphin3.0-r1-mistral-24b:free", 'name': "Dolphin3.0 R1 Mistral 24B"},
        'Flash 3': {'mode': True, 'id': "rekaai/reka-flash-3:free", 'name': "Flash 3"},
        'Gemini 2.0 Flash Experimental': {'mode': True, 'id': "google/gemini-2.0-flash-exp:free", 'name': "Gemini 2.0 Flash Experimental"},
        'Gemma 2 9B': {'mode': True, 'id': "google/gemma-2-9b-it:free", 'name': "Gemma 2 9B"},
        'Gemma 3 12B': {'mode': True, 'id': "google/gemma-3-12b-it:free", 'name': "Gemma 3 12B"},
        'Gemma 3 1B': {'mode': True, 'id': "google/gemma-3-1b-it:free", 'name': "Gemma 3 1B"},
        'Gemma 3 27B': {'mode': True, 'id': "google/gemma-3-27b-it:free", 'name': "Gemma 3 27B"},
        'Gemma 3 4B': {'mode': True, 'id': "google/gemma-3-4b-it:free", 'name': "Gemma 3 4B"},
        'Kimi VL A3B Thinking': {'mode': True, 'id': "moonshotai/kimi-vl-a3b-thinking:free", 'name': "Kimi VL A3B Thinking"},
        'Llama 3.1 8B Instruct': {'mode': True, 'id': "meta-llama/llama-3.1-8b-instruct:free", 'name': "Llama 3.1 8B Instruct"},
        'Llama 3.1 Nemotron Ultra 253B v1': {'mode': True, 'id': "nvidia/llama-3.1-nemotron-ultra-253b-v1:free", 'name': "Llama 3.1 Nemotron Ultra 253B v1"},
        'Llama 3.2 11B Vision Instruct': {'mode': True, 'id': "meta-llama/llama-3.2-11b-vision-instruct:free", 'name': "Llama 3.2 11B Vision Instruct"},
        'Llama 3.2 1B Instruct': {'mode': True, 'id': "meta-llama/llama-3.2-1b-instruct:free", 'name': "Llama 3.2 1B Instruct"},
        'Llama 3.2 3B Instruct': {'mode': True, 'id': "meta-llama/llama-3.2-3b-instruct:free", 'name': "Llama 3.2 3B Instruct"},
        'Llama 3.3 70B Instruct': {'mode': True, 'id': "meta-llama/llama-3.3-70b-instruct:free", 'name': "Llama 3.3 70B Instruct"},
        'Llama 3.3 Nemotron Super 49B v1': {'mode': True, 'id': "nvidia/llama-3.3-nemotron-super-49b-v1:free", 'name': "Llama 3.3 Nemotron Super 49B v1"},
        'Llama 4 Maverick': {'mode': True, 'id': "meta-llama/llama-4-maverick:free", 'name': "Llama 4 Maverick"},
        'Llama 4 Scout': {'mode': True, 'id': "meta-llama/llama-4-scout:free", 'name': "Llama 4 Scout"},
        'Mistral 7B Instruct': {'mode': True, 'id': "mistralai/mistral-7b-instruct:free", 'name': "Mistral 7B Instruct"},
        'Mistral Nemo': {'mode': True, 'id': "mistralai/mistral-nemo:free", 'name': "Mistral Nemo"},
        'Mistral Small 3': {'mode': True, 'id': "mistralai/mistral-small-24b-instruct-2501:free", 'name': "Mistral Small 3"}, 
        'Mistral Small 3.1 24B': {'mode': True, 'id': "mistralai/mistral-small-3.1-24b-instruct:free", 'name': "Mistral Small 3.1 24B"},
        'Molmo 7B D': {'mode': True, 'id': "allenai/molmo-7b-d:free", 'name': "Molmo 7B D"},
        'Moonlight 16B A3B Instruct': {'mode': True, 'id': "moonshotai/moonlight-16b-a3b-instruct:free", 'name': "Moonlight 16B A3B Instruct"},
        'Qwen2.5 72B Instruct': {'mode': True, 'id': "qwen/qwen-2.5-72b-instruct:free", 'name': "Qwen2.5 72B Instruct"},
        'Qwen2.5 7B Instruct': {'mode': True, 'id': "qwen/qwen-2.5-7b-instruct:free", 'name': "Qwen2.5 7B Instruct"},
        'Qwen2.5 Coder 32B Instruct': {'mode': True, 'id': "qwen/qwen-2.5-coder-32b-instruct:free", 'name': "Qwen2.5 Coder 32B Instruct"},
        'Qwen2.5 VL 32B Instruct': {'mode': True, 'id': "qwen/qwen2.5-vl-32b-instruct:free", 'name': "Qwen2.5 VL 32B Instruct"},
        'Qwen2.5 VL 3B Instruct': {'mode': True, 'id': "qwen/qwen2.5-vl-3b-instruct:free", 'name': "Qwen2.5 VL 3B Instruct"},
        'Qwen2.5 VL 72B Instruct': {'mode': True, 'id': "qwen/qwen2.5-vl-72b-instruct:free", 'name': "Qwen2.5 VL 72B Instruct"},
        'Qwen2.5-VL 7B Instruct': {'mode': True, 'id': "qwen/qwen-2.5-vl-7b-instruct:free", 'name': "Qwen2.5-VL 7B Instruct"},
        'Qwerky 72B': {'mode': True, 'id': "featherless/qwerky-72b:free", 'name': "Qwerky 72B"},
        'QwQ 32B': {'mode': True, 'id': "qwen/qwq-32b:free", 'name': "QwQ 32B"},
        'QwQ 32B Preview': {'mode': True, 'id': "qwen/qwq-32b-preview:free", 'name': "QwQ 32B Preview"},
        'QwQ 32B RpR v1': {'mode': True, 'id': "arliai/qwq-32b-arliai-rpr-v1:free", 'name': "QwQ 32B RpR v1"},
        'R1': {'mode': True, 'id': "deepseek/deepseek-r1:free", 'name': "R1"}, # Matches DeepSeek-R1
        'R1 Distill Llama 70B': {'mode': True, 'id': "deepseek/deepseek-r1-distill-llama-70b:free", 'name': "R1 Distill Llama 70B"},
        'R1 Distill Qwen 14B': {'mode': True, 'id': "deepseek/deepseek-r1-distill-qwen-14b:free", 'name': "R1 Distill Qwen 14B"},
        'R1 Distill Qwen 32B': {'mode': True, 'id': "deepseek/deepseek-r1-distill-qwen-32b:free", 'name': "R1 Distill Qwen 32B"},
        # Default models from the new list
        'Claude Opus 4': {'mode': True, 'id': "anthropic/claude-opus-4", 'name': "Claude Opus 4"},
        'Claude Sonnet 4': {'mode': True, 'id': "anthropic/claude-sonnet-4", 'name': "Claude Sonnet 4"},
        'Claude-sonnet-3.7': {'mode': True, 'id': "Claude-sonnet-3.7", 'name': "Claude-sonnet-3.7"},
        'Claude-sonnet-3.5': {'mode': True, 'id': "Claude-sonnet-3.5", 'name': "Claude-sonnet-3.5"},
        'Grok 3': {'mode': True, 'id': "x-ai/grok-3-beta", 'name': "Grok 3"},
        'Gemini 2.5 Pro': {'mode': True, 'id': "google/gemini-2.5-pro-preview-03-25", 'name': "Gemini 2.5 Pro"},
        'UI-TARS 72B': {'mode': True, 'id': "bytedance-research/ui-tars-72b:free", 'name': "UI-TARS 72B"},
        'DeepSeek-R1': {'mode': True, 'id': "deepseek-reasoner", 'name': "DeepSeek-R1"}, 
        'Mistral-Small-24B-Instruct-2501': {'mode': True, 'id': "mistralai/Mistral-Small-24B-Instruct-2501", 'name': "Mistral-Small-24B-Instruct-2501"},
        # Add default_model if it's not covered and has an agent mode
        default_model: {'mode': True, 'id': "openai/gpt-4.1", 'name': default_model},
        'o3-mini': {'mode': True, 'id': "o3-mini", 'name': "o3-mini"}, 
        'gpt-4.1-nano': {'mode': True, 'id': "gpt-4.1-nano", 'name': "gpt-4.1-nano"}, 
        'gpt-4.1-mini': {'mode': True, 'id': "gpt-4.1-mini", 'name': "gpt-4.1-mini"},
    }

    # Trending agent modes
    trendingAgentMode = {
        'Python Agent': {'mode': True, 'id': "python"},
        'HTML Agent': {'mode': True, 'id': "html"},
        'Builder Agent': {'mode': True, 'id': "builder"},
        'Java Agent': {'mode': True, 'id': "java"},
        'JavaScript Agent': {'mode': True, 'id': "javascript"},
        'React Agent': {'mode': True, 'id': "react"},
        'Android Agent': {'mode': True, 'id': "android"},
        'Flutter Agent': {'mode': True, 'id': "flutter"},
        'Next.js Agent': {'mode': True, 'id': "next.js"},
        'AngularJS Agent': {'mode': True, 'id': "angularjs"},
        'Swift Agent': {'mode': True, 'id': "swift"},
        'MongoDB Agent': {'mode': True, 'id': "mongodb"},
        'PyTorch Agent': {'mode': True, 'id': "pytorch"},
        'Xcode Agent': {'mode': True, 'id': "xcode"},
        'Azure Agent': {'mode': True, 'id': "azure"},
        'Bitbucket Agent': {'mode': True, 'id': "bitbucket"},
        'DigitalOcean Agent': {'mode': True, 'id': "digitalocean"},
        'Docker Agent': {'mode': True, 'id': "docker"},
        'Electron Agent': {'mode': True, 'id': "electron"},
        'Erlang Agent': {'mode': True, 'id': "erlang"},
        'FastAPI Agent': {'mode': True, 'id': "fastapi"},
        'Firebase Agent': {'mode': True, 'id': "firebase"},
        'Flask Agent': {'mode': True, 'id': "flask"},
        'Git Agent': {'mode': True, 'id': "git"},
        'Gitlab Agent': {'mode': True, 'id': "gitlab"},
        'Go Agent': {'mode': True, 'id': "go"},
        'Godot Agent': {'mode': True, 'id': "godot"},
        'Google Cloud Agent': {'mode': True, 'id': "googlecloud"},
        'Heroku Agent': {'mode': True, 'id': "heroku"},
    }

    # Create AVAILABLE_MODELS as a list with just the model aliases (no "BLACKBOXAI/" prefix)
    AVAILABLE_MODELS = list(models)


    def __init__(
        self
    ):
        """
        Initialize the BlackboxAI provider with OpenAI compatibility.
        """
        # Initialize session
        self.session = requests.Session()
        self.session.proxies = {}

        # Set headers based on GitHub reference
        self.headers = {
            'Accept': 'text/event-stream',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9,en-IN;q=0.8',
            'Content-Type': 'application/json',
            'DNT': '1',
            'Origin': 'https://www.blackbox.ai',
            'Referer': 'https://www.blackbox.ai/',
            'Sec-CH-UA': '"Not)A;Brand";v="99", "Microsoft Edge";v="127", "Chromium";v="127"',
            'Sec-CH-UA-Mobile': '?0',
            'Sec-CH-UA-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': agent.random(),
        }

        # Set cookies for the session
        self.cookies = {
            'cfzs_amplitude': self.generate_id(32),
            'cfz_amplitude': self.generate_id(32),
            '__cf_bm': self.generate_id(32),
        }

        # Initialize chat interface with completions
        self.chat = Chat(self)

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()


    @classmethod
    def get_model(cls, model: str) -> str:
        """Return the model name, removing BLACKBOXAI/ prefix if present, or default_model."""
        if model.startswith("BLACKBOXAI/"):
            model = model[len("BLACKBOXAI/"):]
        if model in cls.AVAILABLE_MODELS:
            return model
        return cls.default_model

    @classmethod
    def generate_random_string(cls, length: int = 8) -> str:
        """Generate a random string of specified length."""
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

    @classmethod
    def generate_id(cls, length: int = 7) -> str:
        """Generate a random ID of specified length."""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

    @classmethod
    def generate_session(cls, email: str, id_length: int = 21, days_ahead: int = 30) -> dict:
        """
        Generate a dynamic session with proper ID and expiry format using a specific email.

        Args:
            email: The email to use for this session
            id_length: Length of the numeric ID (default: 21)
            days_ahead: Number of days ahead for expiry (default: 30)

        Returns:
            dict: A session dictionary with user information and expiry
        """
        # Generate a random name
        first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery", "Quinn", "Skyler", "Dakota"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia", "Rodriguez", "Wilson"]
        name = f"{random.choice(first_names)} {random.choice(last_names)}"

        # Generate numeric ID - using Google-like ID format
        numeric_id = ''.join(random.choice('0123456789') for _ in range(id_length))

        # Generate future expiry date
        future_date = datetime.now() + timedelta(days=days_ahead)
        expiry = future_date.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

        # Generate random image ID for the new URL format
        chars = string.ascii_letters + string.digits + "-"
        random_img_id = ''.join(random.choice(chars) for _ in range(48))
        image_url = f"https://lh3.googleusercontent.com/a/ACg8oc{random_img_id}=s96-c"

        return {
            "user": {
                "name": name,
                "email": email,
                "image": image_url,
                "id": numeric_id
            },
            "expires": expiry,
            "isNewUser": False
        }

    def create_request_payload(
        self,
        messages: List[Dict[str, Any]],
        chat_id: str,
        system_message: str,
        max_tokens: int,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        session_data: Dict[str, Any] = None,
        model: str = None
    ) -> Dict[str, Any]:
        """Create the full request payload for the BlackboxAI API."""
        # Get the correct model ID and agent mode
        model_name = self.get_model(model or self.default_model)
        agent_mode = self.agentMode.get(model_name, {})

        # Generate a random customer ID for the subscription
        customer_id = "cus_" + ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(14))

        # Create the full request payload
        return {
            "messages": messages,
            "agentMode": agent_mode,
            "id": chat_id,
            "previewToken": None,
            "userId": None,
            "codeModelMode": True,
            "trendingAgentMode": {},
            "isMicMode": False,
            "userSystemPrompt": system_message,
            "maxTokens": max_tokens,
            "playgroundTopP": top_p,
            "playgroundTemperature": temperature,
            "isChromeExt": False,
            "githubToken": "",
            "clickedAnswer2": False,
            "clickedAnswer3": False,
            "clickedForceWebSearch": False,
            "visitFromDelta": False,
            "isMemoryEnabled": False,
            "mobileClient": False,
            "userSelectedModel": model_name if model_name in self.userSelectedModel else None,
            "validated": "00f37b34-a166-4efb-bce5-1312d87f2f94",
            "imageGenerationMode": False,
            "webSearchModePrompt": False,
            "deepSearchMode": False,
            "designerMode": False,
            "domains": None,
            "vscodeClient": False,
            "codeInterpreterMode": False,
            "customProfile": {
                "name": "",
                "occupation": "",
                "traits": [],
                "additionalInfo": "",
                "enableNewChats": False
            },
            "webSearchModeOption": {
                "autoMode": True,
                "webMode": False,
                "offlineMode": False
            },
            "session": session_data,
            "isPremium": True,
            "subscriptionCache": {
                "status": "PREMIUM",
                "customerId": customer_id,
                "expiryTimestamp": int((datetime.now() + timedelta(days=30)).timestamp()),
                "lastChecked": int(datetime.now().timestamp() * 1000),
                "isTrialSubscription": True
            },
            "beastMode": False,
            "reasoningMode": False,
            "designerMode": False,
            "workspaceId": ""
        }
if __name__ == "__main__":
    # Example usage
    client = BLACKBOXAI()
    response = client.chat.completions.create(
        model="GPT-4.1",
        messages=[{"role": "user", "content": "Tell me about india in points"}],
        stream=True
    )
    for chunk in response:
        print(chunk.choices[0].delta.content, end='', flush=True)
