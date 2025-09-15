from typing import List, Dict, Optional, Union, Generator, Any
import time
import json
from webscout.litagent import LitAgent
from webscout.Provider.OPENAI.base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from webscout.Provider.OPENAI.utils import (
    ChatCompletion,
    ChatCompletionChunk,
    Choice,
    ChatCompletionMessage,
    ChoiceDelta,
    CompletionUsage,
    format_prompt,
    count_tokens
)
from curl_cffi.requests import Session
from curl_cffi.const import CurlHttpVersion
from webscout.AIutel import sanitize_stream
from webscout import exceptions

# ANSI escape codes for formatting
BOLD = "\033[1m"
RED = "\033[91m"
RESET = "\033[0m"

class Completions(BaseCompletions):
    def __init__(self, client: 'ChatSandbox'):
        self._client = client

    @staticmethod
    def _chatsandbox_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        """Extracts content from the chatsandbox stream format."""
        if isinstance(chunk, str):
            try:
                data = json.loads(chunk)
                if isinstance(data, dict) and "reasoning_content" in data:
                    return data["reasoning_content"]
                return chunk
            except json.JSONDecodeError:
                return chunk
        return None

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
        OpenAI-compatible chat/completions endpoint for ChatSandbox.
        """
        # Use model name conversion for compatibility
        model = self._client.convert_model_name(model)
        # Compose the conversation prompt using format_prompt
        question = format_prompt(messages, add_special_tokens=False, do_continue=True)
        payload = {
            "messages": [question],
            "character": model
        }
        request_id = f"chatcmpl-{int(time.time() * 1000)}"
        created_time = int(time.time())
        url = "https://chatsandbox.com/api/chat"
        agent = LitAgent()
        headers = {
            'authority': 'chatsandbox.com',
            'accept': '*/*',
            'accept-encoding': 'gzip, deflate, br',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://chatsandbox.com',
            'referer': f'https://chatsandbox.com/chat/{model}',
            'sec-ch-ua': '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': agent.random(),
            'dnt': '1',
            'sec-gpc': '1',
        }
        session = Session()
        session.headers.update(headers)
        session.proxies = proxies if proxies is not None else {}
        
        def for_stream():
            try:
                response = session.post(
                    url,
                    json=payload,
                    stream=True,
                    timeout=timeout if timeout is not None else 30,
                    impersonate="chrome120",
                    http_version=CurlHttpVersion.V1_1
                )
                if not response.ok:
                    raise exceptions.FailedToGenerateResponseError(
                        f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                    )
                
                streaming_text = ""
                # Use sanitize_stream with the custom extractor
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None),  # Pass byte iterator
                    intro_value=None,  # No simple prefix to remove here
                    to_json=False,     # Content is not JSON
                    content_extractor=self._chatsandbox_extractor  # Use the specific extractor
                )

                for content_chunk in processed_stream:
                    if content_chunk and isinstance(content_chunk, str):
                        streaming_text += content_chunk
                        delta = ChoiceDelta(content=content_chunk)
                        choice = Choice(index=0, delta=delta, finish_reason=None)
                        chunk_obj = ChatCompletionChunk(
                            id=request_id,
                            choices=[choice],
                            created=created_time,
                            model=model,
                        )
                        yield chunk_obj

                # Final chunk
                delta = ChoiceDelta(content=None)
                choice = Choice(index=0, delta=delta, finish_reason="stop")
                chunk_obj = ChatCompletionChunk(
                    id=request_id,
                    choices=[choice],
                    created=created_time,
                    model=model,
                )
                yield chunk_obj
            except Exception as e:
                raise RuntimeError(f"ChatSandbox streaming request failed: {e}")
        def for_non_stream():
            streaming_text = ""
            for chunk_obj in for_stream():
                if chunk_obj.choices[0].delta.content:
                    streaming_text += chunk_obj.choices[0].delta.content
            prompt_tokens = count_tokens(question)
            completion_tokens = count_tokens(streaming_text)
            total_tokens = prompt_tokens + completion_tokens
            usage = CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )
            message = ChatCompletionMessage(role="assistant", content=streaming_text)
            choice = Choice(index=0, message=message, finish_reason="stop")
            completion = ChatCompletion(
                id=request_id,
                choices=[choice],
                created=created_time,
                model=model,
                usage=usage,
            )
            return completion
        return for_stream() if stream else for_non_stream()

class Chat(BaseChat):
    def __init__(self, client: 'ChatSandbox'):
        self.completions = Completions(client)

class ChatSandbox(OpenAICompatibleProvider):
    AVAILABLE_MODELS = ["openai", "deepseek", "llama", "gemini", "mistral-large", "deepseek-r1", "deepseek-r1-full", "gemini-thinking", "openai-o1-mini", "llama", "mistral", "gemma-3"]
    chat: Chat
    def __init__(self):
        self.chat = Chat(self)
    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()
    def convert_model_name(self, model: str) -> str:
        if model in self.AVAILABLE_MODELS:
            return model
        for available_model in self.AVAILABLE_MODELS:
            if model.lower() in available_model.lower():
                return available_model
        # Default to openai if no match
        print(f"{RED}{BOLD}Warning: Model '{model}' not found, using default model 'openai'{RESET}")
        return "openai"

if __name__ == "__main__":
    client = ChatSandbox()
    response = client.chat.completions.create(
        model="openai",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Explain the theory of relativity in simple terms."}
        ],
        stream=False
    )
    print(response.choices[0].message.content)
