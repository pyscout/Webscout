import requests
import json
import time
import uuid
from typing import List, Dict, Optional, Union, Generator, Any

from webscout.Provider.OPENAI.base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from webscout.Provider.OPENAI.utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage,
    get_system_prompt,
    count_tokens,
    format_prompt
)
from webscout.litagent import LitAgent

def convert_openai_to_falcon_history(messages: List[Dict[str, str]]) -> list:
    """
    Converts a list of OpenAI-style chat messages to Falcon/Gradio chat history format.

    Args:
        messages (List[Dict[str, str]]):
            A list of message dictionaries, each with 'role' and 'content' keys, following the OpenAI API format.

    Returns:
        list: A single-turn Falcon/Gradio chat history in the format [[prompt, None]].
    """
    prompt = format_prompt(messages, add_special_tokens=False, do_continue=True, include_system=True)
    return [[prompt, None]]

class Completions(BaseCompletions):
    """
    Handles text completion requests for the FalconH1 provider, supporting both streaming and non-streaming modes.

    Attributes:
        _client (Any): Reference to the FalconH1 client instance.
        _last_yielded_content_stream (str): Tracks the last yielded content in streaming mode.
    """
    def __init__(self, client):
        """
        Initializes the Completions handler.

        Args:
            client: The FalconH1 client instance.
        """
        self._client = client
        self._last_yielded_content_stream = ""

    def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = 1024,
        stream: bool = False,
        temperature: Optional[float] = 0.1,
        top_p: Optional[float] = 1.0,
        timeout: Optional[int] = None,
        proxies: Optional[dict] = None,
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Creates a chat completion using the FalconH1 API, supporting both streaming and non-streaming responses.

        Args:
            model (str): The model identifier to use for completion.
            messages (List[Dict[str, str]]): List of chat messages in OpenAI format.
            max_tokens (Optional[int]): Maximum number of tokens to generate in the completion.
            stream (bool): Whether to stream the response as chunks.
            temperature (Optional[float]): Sampling temperature.
            top_p (Optional[float]): Nucleus sampling probability.
            timeout (Optional[int]): Request timeout in seconds.
            proxies (Optional[dict]): Optional proxy settings for the request.
            **kwargs: Additional keyword arguments for advanced options (e.g., top_k, repetition_penalty).

        Returns:
            Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]: The chat completion result or a generator yielding streamed chunks.
        """
        session_hash = str(uuid.uuid4()).replace('-', '')
        chat_history = convert_openai_to_falcon_history(messages)
        if not chat_history or chat_history[-1][0] is None:
            raise ValueError("Messages must contain at least one user message for Falcon API.")
        resolved_model_name = self._client.get_model(model)
        payload_data = [
            chat_history,
            resolved_model_name,
            temperature,
            max_tokens,
            top_p,
            kwargs.get("top_k", 20),
            kwargs.get("repetition_penalty", 1.2)
        ]
        payload = {
            "data": payload_data,
            "event_data": None,
            "fn_index": 5,
            "trigger_id": 12,
            "session_hash": session_hash
        }
        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())
        if stream:
            self._last_yielded_content_stream = ""
            return self._create_stream(request_id, created_time, resolved_model_name, payload, session_hash, timeout=timeout, proxies=proxies)
        else:
            return self._create_non_stream(request_id, created_time, resolved_model_name, payload, session_hash, timeout=timeout, proxies=proxies)

    def _create_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any], session_hash: str,
        timeout: Optional[int] = None, proxies: Optional[dict] = None
    ) -> Generator[ChatCompletionChunk, None, None]:
        """
        Internal method to handle streaming chat completions from the FalconH1 API.

        Args:
            request_id (str): Unique request identifier.
            created_time (int): Timestamp of request creation.
            model (str): Model identifier.
            payload (Dict[str, Any]): Request payload for the API.
            session_hash (str): Unique session hash for the request.
            timeout (Optional[int]): Request timeout in seconds.
            proxies (Optional[dict]): Optional proxy settings.

        Yields:
            ChatCompletionChunk: Chunks of the chat completion as they are received from the API.
        """
        original_proxies = self._client.session.proxies.copy()
        if proxies is not None:
            self._client.session.proxies = proxies
        else:
            self._client.session.proxies = {}
        try:
            session = self._client.session
            join_resp = session.post(
                self._client.api_join_endpoint,
                headers=self._client.headers,
                json=payload,
                timeout=timeout if timeout is not None else self._client.timeout
            )
            join_resp.raise_for_status()
            data_url = f"{self._client.api_data_endpoint}?session_hash={session_hash}"
            stream_resp = session.get(
                data_url,
                headers=self._client.stream_headers,
                stream=True,
                timeout=timeout if timeout is not None else self._client.timeout
            )
            stream_resp.raise_for_status()
            for line in stream_resp.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data: '):
                        try:
                            json_data = json.loads(decoded_line[6:])
                            msg_type = json_data.get('msg')
                            if msg_type == 'process_generating':
                                output_field = json_data.get('output', {})
                                data_field = output_field.get('data')
                                if data_field and isinstance(data_field, list) and len(data_field) > 0:
                                    inner_data = data_field[0]
                                    content_to_yield = None
                                    if isinstance(inner_data, list) and len(inner_data) > 0:
                                        if isinstance(inner_data[0], list) and len(inner_data[0]) == 3 and inner_data[0][0] == "append":
                                            content_to_yield = inner_data[0][2]
                                        elif isinstance(inner_data[0], list) and len(inner_data[0]) == 2 and \
                                             isinstance(inner_data[0][1], str):
                                            current_full_response = inner_data[0][1]
                                            if current_full_response.startswith(self._last_yielded_content_stream):
                                                content_to_yield = current_full_response[len(self._last_yielded_content_stream):]
                                            else:
                                                content_to_yield = current_full_response
                                            self._last_yielded_content_stream = current_full_response
                                    if content_to_yield:
                                        delta = ChoiceDelta(content=content_to_yield, role="assistant")
                                        yield ChatCompletionChunk(id=request_id, choices=[Choice(index=0, delta=delta)], created=created_time, model=model)
                            elif msg_type == 'process_completed' or msg_type == 'close_stream':
                                break
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            continue
        finally:
            self._client.session.proxies = original_proxies

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any], session_hash: str,
        timeout: Optional[int] = None, proxies: Optional[dict] = None
    ) -> ChatCompletion:
        """
        Internal method to handle non-streaming chat completions from the FalconH1 API.

        Args:
            request_id (str): Unique request identifier.
            created_time (int): Timestamp of request creation.
            model (str): Model identifier.
            payload (Dict[str, Any]): Request payload for the API.
            session_hash (str): Unique session hash for the request.
            timeout (Optional[int]): Request timeout in seconds.
            proxies (Optional[dict]): Optional proxy settings.

        Returns:
            ChatCompletion: The full chat completion result.
        """
        original_proxies = self._client.session.proxies.copy()
        if proxies is not None:
            self._client.session.proxies = proxies
        else:
            self._client.session.proxies = {}
        full_response_content = ""
        last_full_response_chunk_ns = ""
        response_parts = []
        try:
            session = self._client.session
            join_resp = session.post(
                self._client.api_join_endpoint, headers=self._client.headers, json=payload,
                timeout=timeout if timeout is not None else self._client.timeout
            )
            join_resp.raise_for_status()
            data_url = f"{self._client.api_data_endpoint}?session_hash={session_hash}"
            overall_start_time = time.time()
            effective_timeout = timeout if timeout is not None else self._client.timeout
            while True:
                if time.time() - overall_start_time > effective_timeout:
                    raise TimeoutError("Timeout waiting for non-stream response completion.")
                stream_resp = session.get(
                    data_url, headers=self._client.stream_headers, stream=True,
                    timeout=effective_timeout
                )
                stream_resp.raise_for_status()
                found_completion_message = False
                for line in stream_resp.iter_lines():
                    if time.time() - overall_start_time > effective_timeout:
                        raise TimeoutError("Timeout during non-stream response processing.")
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('data: '):
                            try:
                                json_data = json.loads(decoded_line[6:])
                                msg_type = json_data.get('msg')
                                if msg_type == 'process_generating':
                                    output_field = json_data.get('output', {})
                                    data_field = output_field.get('data')
                                    if data_field and isinstance(data_field, list) and len(data_field) > 0:
                                        inner_data = data_field[0]
                                        current_chunk_text = None
                                        if isinstance(inner_data, list) and len(inner_data) > 0:
                                            if isinstance(inner_data[0], list) and len(inner_data[0]) == 3 and inner_data[0][0] == "append":
                                                current_chunk_text = inner_data[0][2]
                                            elif isinstance(inner_data[0], list) and len(inner_data[0]) == 2 and isinstance(inner_data[0][1], str):
                                                current_full_response = inner_data[0][1]
                                                if current_full_response.startswith(last_full_response_chunk_ns):
                                                    current_chunk_text = current_full_response[len(last_full_response_chunk_ns):]
                                                else:
                                                    current_chunk_text = current_full_response
                                                last_full_response_chunk_ns = current_full_response
                                        if current_chunk_text:
                                            response_parts.append(current_chunk_text)
                                elif msg_type == 'process_completed' or msg_type == 'close_stream':
                                    if msg_type == 'process_completed':
                                        output_field = json_data.get('output', {})
                                        data_field = output_field.get('data')
                                        if data_field and isinstance(data_field, list) and len(data_field) > 0:
                                            inner_data = data_field[0]
                                            if isinstance(inner_data, list) and len(inner_data) > 0 and \
                                               isinstance(inner_data[0], list) and len(inner_data[0]) == 2 and \
                                               isinstance(inner_data[0][1], str):
                                                final_full_response = inner_data[0][1]
                                                if final_full_response != last_full_response_chunk_ns:
                                                    if final_full_response.startswith(last_full_response_chunk_ns):
                                                        response_parts.append(final_full_response[len(last_full_response_chunk_ns):])
                                                    else:
                                                        response_parts = [final_full_response]
                                                    last_full_response_chunk_ns = final_full_response
                                    found_completion_message = True
                                    break
                            except json.JSONDecodeError:
                                continue
                            except Exception as e:
                                raise e
                if found_completion_message:
                    break
            full_response_content = "".join(response_parts)
            message = ChatCompletionMessage(role="assistant", content=full_response_content)
            choice = Choice(index=0, message=message, finish_reason="stop")
            
            # Simplified token counting without history iteration
            chat_history = payload['data'][0]
            prompt = chat_history[0][0] if chat_history and chat_history[0] and chat_history[0][0] else ""
            prompt_tokens = count_tokens(prompt)
            completion_tokens = count_tokens(full_response_content)
            usage = CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
            )
            return ChatCompletion(
                id=request_id, choices=[choice], created=created_time,
                model=model, usage=usage
            )
        finally:
            self._client.session.proxies = original_proxies

class Chat(BaseChat):
    """
    Provides a chat interface for the FalconH1 provider, exposing the completions API.

    Attributes:
        completions (Completions): The completions handler for chat requests.
    """
    def __init__(self, client):
        """
        Initializes the Chat interface for FalconH1.

        Args:
            client: The FalconH1 client instance.
        """
        self.completions = Completions(client)

class FalconH1(OpenAICompatibleProvider):
    """
    FalconH1 provider implementation compatible with the OpenAI API interface.
    Handles chat completions using FalconH1 models via the Hugging Face Spaces API.

    Attributes:
        base_url (str): Base URL for the FalconH1 API.
        api_join_endpoint (str): Endpoint for joining the chat queue.
        api_data_endpoint (str): Endpoint for retrieving chat data.
        AVAILABLE_MODELS (List[str]): List of supported FalconH1 model identifiers.
        timeout (int): Default request timeout in seconds.
        session (requests.Session): HTTP session for API requests.
        headers (dict): Default HTTP headers for requests.
        stream_headers (dict): HTTP headers for streaming requests.
        chat (Chat): Chat interface for completions.
    """
    base_url = "https://tiiuae-falcon-h1-playground.hf.space"
    api_join_endpoint = f"{base_url}/gradio_api/queue/join?__theme=dark"
    api_data_endpoint = f"{base_url}/gradio_api/queue/data"
    AVAILABLE_MODELS = [
        "Falcon-H1-34B-Instruct",
        "Falcon-H1-7B-Instruct",
        "Falcon-H1-3B-Instruct",
        "Falcon-H1-1.5B-Deep-Instruct",
        "Falcon-H1-1.5B-Instruct",
        "Falcon-H1-0.5B-Instruct",
    ]
    def __init__(self, timeout: int = 120, proxies: Optional[dict] = None):
        """
        Initializes the FalconH1 provider with optional timeout and proxy settings.

        Args:
            timeout (int): Default request timeout in seconds (default: 120).
            proxies (Optional[dict]): Optional proxy settings for HTTP requests.
        """
        super().__init__(proxies=proxies)
        self.timeout = timeout
        self.headers = {
            'User-Agent': LitAgent().random(),
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9,en-IN;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Referer': f'{self.base_url}/?__theme=dark',
            'Content-Type': 'application/json',
            'Origin': self.base_url,
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'DNT': '1',
            'Sec-GPC': '1',
        }
        self.stream_headers = {
            'Accept': 'text/event-stream',
            'Accept-Language': self.headers['Accept-Language'],
            'Referer': self.headers['Referer'],
            'User-Agent': self.headers['User-Agent'],
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
        }
        self.session.headers.update(self.headers)
        self.chat = Chat(self)
    def get_model(self, model_identifier: str) -> str:
        """
        Returns the resolved model name for the given identifier.

        Args:
            model_identifier (str): The model identifier string.

        Returns:
            str: The resolved model name (currently returns the identifier as-is).
        """
        return model_identifier
    @property
    def models(self):
        """
        Returns a list-like object containing available FalconH1 models.

        Returns:
            ModelList: An object with a .list() method returning model data objects.
        """
        class ModelData:
            def __init__(self, id_str):
                self.id = id_str
        class ModelList:
            def __init__(self, models_available):
                self.data = [ModelData(m) for m in models_available]
            def list(self):
                return self.data
        return ModelList(self.AVAILABLE_MODELS)

if __name__ == "__main__":
    """
    Example usage of the FalconH1 provider for both non-streaming and streaming chat completions.
    """
    print("FalconH1 Provider Example")
    client = FalconH1()
    print("\n--- Non-Streaming Example ---")
    try:
        response = client.chat.completions.create(
            model="Falcon-H1-34B-Instruct",
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant named Falcon."},
                {"role": "user", "content": "Hello, what is your name and what can you do?"}
            ]
        )
        print(f"ID: {response.id}")
        print(f"Model: {response.model}")
        if response.choices:
            print(f"Response: {response.choices[0].message.content}")
        if response.usage:
            print(f"Usage: {response.usage}")
    except Exception as e:
        print(f"Error in non-streaming example: {e}")
    print("\n--- Streaming Example ---")
    try:
        stream_response = client.chat.completions.create(
            model="Falcon-H1-34B-Instruct",
            messages=[
                {"role": "user", "content": "Tell me a short story about a brave falcon."}
            ],
            stream=True,
            max_tokens=150
        )
        print("Streaming response:")
        full_streamed_content = ""
        for chunk in stream_response:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                content_piece = chunk.choices[0].delta.content
                print(content_piece, end="", flush=True)
                full_streamed_content += content_piece
        print("\n--- End of Stream ---")
    except Exception as e:
        print(f"Error in streaming example: {e}")