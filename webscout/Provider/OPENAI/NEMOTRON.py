import time
import uuid
import requests
import json
import random
import datetime
import re
from typing import List, Dict, Optional, Union, Generator, Any
from webscout.Provider.OPENAI.base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from webscout.Provider.OPENAI.utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage, format_prompt, count_tokens
)
try:
    from webscout.litagent import LitAgent
except ImportError:
    class LitAgent:
        def random(self) -> str:
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
from webscout.AIutel import sanitize_stream
from webscout import exceptions


class Completions(BaseCompletions):
    def __init__(self, client: 'NEMOTRON'):
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
    ) -> ChatCompletion:
        nemotron_model_name = self._client.convert_model_name(model)
        prompt_content = format_prompt(messages, add_special_tokens=True, include_system=True, do_continue=True)
        payload = {
            "content": prompt_content,
            "imageSrc": "",
            "model": nemotron_model_name,
            "user": self._client._get_user_data(),
            "conversationId": kwargs.get("conversation_id", "")
        }
        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())
        # Always use non-stream mode, ignore 'stream' argument
        return self._create_non_stream(request_id, created_time, model, payload, timeout=timeout, proxies=proxies)

    def _create_stream(
        self, request_id: str, created_time: int, model_name: str, payload: Dict[str, Any],
        timeout: Optional[int] = None, proxies: Optional[dict] = None
    ) -> Generator[ChatCompletionChunk, None, None]:
        try:
            response_generator = self._client._internal_make_request(payload, stream=True, request_timeout=timeout, request_proxies=proxies)
            for text_chunk in response_generator:
                if text_chunk:
                    delta = ChoiceDelta(content=text_chunk, role="assistant")
                    choice = Choice(index=0, delta=delta, finish_reason=None)
                    chunk = ChatCompletionChunk(
                        id=request_id,
                        choices=[choice],
                        created=created_time,
                        model=model_name,
                    )
                    yield chunk
            final_delta = ChoiceDelta()
            final_choice = Choice(index=0, delta=final_delta, finish_reason="stop")
            final_chunk = ChatCompletionChunk(
                id=request_id,
                choices=[final_choice],
                created=created_time,
                model=model_name,
            )
            yield final_chunk
        except Exception as e:
            raise IOError(f"NEMOTRON request failed: {e}") from e

    def _create_non_stream(
        self, request_id: str, created_time: int, model_name: str, payload: Dict[str, Any],
        timeout: Optional[int] = None, proxies: Optional[dict] = None
    ) -> ChatCompletion:
        full_response_content = ""
        try:
            response_generator = self._client._internal_make_request(payload, stream=False, request_timeout=timeout, request_proxies=proxies)
            full_response_content = next(response_generator, "")
        except Exception as e:
            pass
        message = ChatCompletionMessage(role="assistant", content=full_response_content)
        choice = Choice(index=0, message=message, finish_reason="stop")
        prompt_tokens = count_tokens(payload.get("content", ""))
        completion_tokens = count_tokens(full_response_content)
        usage = CompletionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens
        )
        completion = ChatCompletion(
            id=request_id,
            choices=[choice],
            created=created_time,
            model=model_name,
            usage=usage,
        )
        return completion

class Chat(BaseChat):
    def __init__(self, client: 'NEMOTRON'):
        self.completions = Completions(client)

class NEMOTRON(OpenAICompatibleProvider):
    AVAILABLE_MODELS = [
        "gpt4o",
        "nemotron70b",
    ]
    
    API_BASE_URL = "https://nemotron.one/api/chat"
    def __init__(self, proxies: Optional[dict] = None):
        super().__init__(proxies=proxies)
        self.timeout = 30
        agent = LitAgent()
        user_agent = agent.random()
        self.base_headers = {
            "authority": "nemotron.one",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "content-type": "application/json",
            "origin": "https://nemotron.one",
            "sec-ch-ua": '"Chromium";v="136", "Not.A/Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "user-agent": user_agent
        }
        self.session.headers.update(self.base_headers)
        self.chat = Chat(self)

    def _generate_random_email(self) -> str:
        random_letter = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        random_string = ''.join(random.choice(random_letter) for _ in range(10))
        return f"{random_string}@gmail.com"

    def _generate_random_id(self) -> str:
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
        random_letter = "abcdefghijklmnopqrstuvwxyz0123456789"
        random_string = ''.join(random.choice(random_letter) for _ in range(8))
        return f"cm{random_string}{timestamp[:10]}"

    def _get_user_data(self) -> Dict[str, Any]:
        current_time = datetime.datetime.now().isoformat()
        return {
            "name": "user",
            "email": self._generate_random_email(),
            "image": "https://lh3.googleusercontent.com/a/default-user=s96-c",
            "id": self._generate_random_id(),
            "password": None,
            "emailVerified": None,
            "credits": 100000000000,
            "isPro": False,
            "createdAt": current_time,
            "updatedAt": current_time
        }

    def convert_model_name(self, model_alias: str) -> str:
        """
        Convert model names to ones supported by NEMOTRON API.
        
        Args:
            model_alias: Model name to convert
        
        Returns:
            NEMOTRON model name for API payload
        """
        # Accept only direct model names
        if model_alias in self.AVAILABLE_MODELS:
            return model_alias
        
        # Case-insensitive matching
        for m in self.AVAILABLE_MODELS:
            if m.lower() == model_alias.lower():
                return m
        
        # Default to gpt4o if no match
        print(f"Warning: Unknown model '{model_alias}'. Using 'gpt4o' instead.")
        return "gpt4o"

    def _internal_make_request(
        self,
        payload: Dict[str, Any],
        stream: bool = False,
        request_timeout: Optional[int] = None,
        request_proxies: Optional[dict] = None
    ) -> Generator[str, None, None]:
        request_headers = self.base_headers.copy()
        request_headers["referer"] = f"https://nemotron.one/chat/{payload['model']}"
        original_proxies = self.session.proxies.copy()
        if request_proxies is not None:
            self.session.proxies.update(request_proxies)
        elif not self.session.proxies:
            pass
        else:
            self.session.proxies = {}
        try:
            if stream:
                with self.session.post(
                    self.API_BASE_URL,
                    headers=request_headers,
                    json=payload,
                    stream=True,
                    timeout=request_timeout if request_timeout is not None else self.timeout
                ) as response:
                    response.raise_for_status()
                    yield from sanitize_stream(
                        response.iter_content(chunk_size=1024),
                        to_json=False,
                    )
            else:
                response = self.session.post(
                    self.API_BASE_URL,
                    headers=request_headers,
                    json=payload,
                    timeout=request_timeout if request_timeout is not None else self.timeout
                )
                response.raise_for_status()
                yield response.text
        except requests.exceptions.RequestException as e:
            raise exceptions.ProviderConnectionError(f"NEMOTRON API Connection error: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"NEMOTRON API request unexpected error: {str(e)}")
        finally:
            self.session.proxies = original_proxies
    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()