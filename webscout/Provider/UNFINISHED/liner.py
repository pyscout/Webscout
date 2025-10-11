import requests
import json
import time
import uuid
from copy import deepcopy
from typing import List, Dict, Optional, Union, Generator, Any

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


class Completions(BaseCompletions):
    def __init__(self, client: 'Liner'):
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
        proxies: Optional[Dict[str, str]] = None,
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Creates a model response for the given chat conversation.
        Mimics openai.chat.completions.create
        """
        # Extract last user message
        user_content = None
        for message in reversed(messages):
            if message.get("role") == "user":
                user_content = message.get("content")
                break
        
        if not user_content:
            raise ValueError("At least one user message is required")

        # Build payload
        payload = deepcopy(self._client.base_payload)
        payload["query"] = user_content
        payload["modelType"] = model
        
        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())

        if stream:
            return self._create_stream(request_id, created_time, model, payload, timeout, proxies)
        else:
            return self._create_non_stream(request_id, created_time, model, payload, timeout, proxies)

    def _create_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any],
        timeout: Optional[int] = None, proxies: Optional[Dict[str, str]] = None
    ) -> Generator[ChatCompletionChunk, None, None]:
        try:
            response = self._client.session.post(
                self._client.base_url,
                headers=self._client.headers,
                cookies=self._client.cookies,
                json=payload,
                stream=True,
                timeout=timeout or self._client.timeout,
                proxies=proxies
            )
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if not line.startswith("data:"):
                    continue
                
                data_str = line[6:].strip()
                if not data_str:
                    continue
                
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                
                chunk_content = event.get("answer")
                if chunk_content:
                    delta = ChoiceDelta(content=chunk_content, role="assistant")
                    choice = Choice(index=0, delta=delta, finish_reason=None)
                    
                    chunk = ChatCompletionChunk(
                        id=request_id,
                        object="chat.completion.chunk",
                        created=created_time,
                        model=model,
                        choices=[choice]
                    )
                    yield chunk
            
            # Send final chunk with finish_reason
            final_delta = ChoiceDelta(content=None)
            final_choice = Choice(index=0, delta=final_delta, finish_reason="stop")
            final_chunk = ChatCompletionChunk(
                id=request_id,
                object="chat.completion.chunk",
                created=created_time,
                model=model,
                choices=[final_choice]
            )
            yield final_chunk

        except requests.RequestException as e:
            raise IOError(f"Liner request failed: {str(e)}")

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any],
        timeout: Optional[int] = None, proxies: Optional[Dict[str, str]] = None
    ) -> ChatCompletion:
        try:
            response = self._client.session.post(
                self._client.base_url,
                headers=self._client.headers,
                cookies=self._client.cookies,
                json=payload,
                stream=True,
                timeout=timeout or self._client.timeout,
                proxies=proxies
            )
            response.raise_for_status()

            answer_parts: List[str] = []
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if not line.startswith("data:"):
                    continue
                
                data_str = line[6:].strip()
                if not data_str:
                    continue
                
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                
                chunk = event.get("answer")
                if chunk:
                    answer_parts.append(chunk)

            if not answer_parts:
                raise IOError("No answer content received from Liner")

            full_content = "".join(answer_parts)
            
            message = ChatCompletionMessage(role="assistant", content=full_content)
            choice = Choice(index=0, message=message, finish_reason="stop")
            usage = CompletionUsage(
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0
            )

            return ChatCompletion(
                id=request_id,
                object="chat.completion",
                created=created_time,
                model=model,
                choices=[choice],
                usage=usage
            )

        except requests.RequestException as e:
            raise IOError(f"Liner request failed: {str(e)}")


class Chat(BaseChat):
    def __init__(self, client: 'Liner'):
        self.completions = Completions(client)


class Liner(OpenAICompatibleProvider):
    """
    Liner AI provider for OpenAI-compatible API.
    Supports claude-4-5-sonnet and other models via Liner's search-enhanced AI.
    """
    
    AVAILABLE_MODELS = [
        "claude-4-5-sonnet",
        "gpt-4",
        "gpt-3.5-turbo"
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-4-5-sonnet",
        timeout: int = 60,
        proxies: Optional[dict] = None
    ):
        """
        Initialize the Liner provider.
        
        Args:
            api_key: Not used, kept for compatibility
            model: Model to use (default: claude-4-5-sonnet)
            timeout: Request timeout in seconds
            proxies: Optional proxy configuration
        """
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        self.api_key = api_key  # Not actually used
        self.model = model
        self.timeout = timeout
        self.proxies = proxies
        
        self.base_url = "https://getliner.com/lisa/v2/answer?lpv=250414"
        
        self.headers = {
            "accept": "text/event-stream",
            "accept-language": "en-US,en;q=0.9,en-IN;q=0.8",
            "baggage": "sentry-environment=main,sentry-release=711bc8d387f169a76656427872101800d2c7f3a6,sentry-public_key=b443aee6dcc5619cdc85c272632d87a9,sentry-trace_id=30690146d0014887896af7e513702e97,sentry-org_id=4509154898870272,sentry-transaction=%2Fsearch%2Fs%2F%5BspaceId%5D%2Ft%2F%5BthreadId%5D,sentry-sampled=false,sentry-sample_rand=0.6477520525552076,sentry-sample_rate=0.01",
            "content-type": "application/json",
            "origin": "https://getliner.com",
            "priority": "u=1, i",
            "referer": "https://getliner.com/search/s/17788115/t/89019415?msg-entry-type=main",
            "sec-ch-ua": '"Microsoft Edge";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "sec-gpc": "1",
            "sentry-trace": "30690146d0014887896af7e513702e97-92aa3c44e2ecea6b-0",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0",
        }
        
        self.cookies = {
            "_k_state": "MmRiY2RjYTgtYjExMi00NTY1LWI1NWQtZjZkZjQ4NjFkZTE3LS0wNzZmNjVmNC05MTIzLTQ1MmItODQzMC0yYmRlYmEyNTA3NjQ=",
            "__stripe_mid": "b3b3a7d0-d8a7-41b8-a75c-df41869803e0f06952",
            "COOKIE_NAME_STABLE_ID": "7c14bbc7-83a5-4a29-a1cb-d102427aa8f7",
            "EXPERIMENT_ID": "71",
            "AMP_MKTG_ac91207b66": "JTdCJTdE",
            "_ga": "GA1.1.1710132341.1760025657",
            "_tt_enable_cookie": "1",
            "_ttp": "01K74V8J3J5WA2DA4VQJJXWSBA_.tt.1",
            "airbridge_migration_metadata__<liner>": "%7B%22version%22%3A%221.10.78%22%7D",
            "ab180ClientId": "266cd8d0-314f-448e-ab4f-73b68c1588fa",
            "__stripe_sid": "543be03e-c8c9-4873-8e06-8ddea92d9b856e0d87",
            "_gcl_au": "1.1.807601105.1760025655.508947310.1760085500.1760085527",
            "connect.sid": "s%3AlsduEPljG-HTkAc6F7cd8K9GCACBtcqr.5fR5xnoCZl4tV3FIZ00TIGvGV4v0oeBgFBQAJluuDLI",
            "_ga_9RRDSJXHYC": "GS2.1.s1760085440$o2$g1$t1760085935$j54$l0$h0",
            "_rdt_uuid": "1760086131993.a39cd5bb-964c-459c-b7ab-47f6d0dcef5a",
            "_ga_67C29LFSEM": "GS2.1.s1760085442$o2$g1$t1760086132$j58$l0$h640428007",
            "ttcsid": "1760085443433::VvDfTD7ngJjKz5zWXlHS.2.1760086137397.0",
            "ttcsid_CSG94UJC77U8G0CRAVJ0": "1760085443431::zxCXzZtBM6bkv6O4-BSF.2.1760086137398.0",
            "_dd_s": "aid=c19eef5b-af5a-4b9a-97b1-5d4ef1bfeff4&rum=0&expire=1760087072218",
            "AMP_ac91207b66": "JTdCJTIyZGV2aWNlSWQlMjIlM0ElMjJiOTI5MzI0MC0wMTJmLTRlOTctYjUwYi03ZTdiNDIxM2RiZTAlMjIlMkMlMjJ1c2VySWQlMjIlM0ElMjI4NTI2MzE0JTIyJTJDJTIyc2Vzc2lvbklkJTIyJTNBMTc2MDA4NTQzOTg5NiUyQyUyMm9wdE91dCUyMiUzQWZhbHNlJTJDJTIybGFzdEV2ZW50VGltZSUyMiUzQTE3NjAwODYxNzIyMzclMkMlMjJsYXN0RXZlbnRJZCUyMiUzQTk3JTJDJTIycGFnZUNvdW50ZXIlMjIlM0E1JTdE",
        }
        
        self.base_payload = {
            "spaceId": 17788115,
            "threadId": 89019415,
            "userMessageId": 208047032,
            "userId": 19307130,
            "query": "hi",
            "agentId": "liner",
            "platform": "web",
            "regenerate": False,
            "showReferenceChunks": True,
            "mode": "general",
            "answerMode": "search",
            "experimentId": 60,
            "modelType": model,
            "experimentVariants": ["ref-14__treatment"],
            "isDeepResearchMode": False,
            "answerFormat": "auto",
        }
        
        self.session = requests.Session()
        self.chat = Chat(self)

    def list_models(self) -> List[str]:
        """List available models."""
        return self.AVAILABLE_MODELS

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()


if __name__ == "__main__":
    # Example usage
    client = Liner(model="claude-4-5-sonnet")
    
    # Non-streaming example
    response = client.chat.completions.create(
        model="claude-4-5-sonnet",
        messages=[
            {"role": "user", "content": "What is the capital of France?"}
        ],
        stream=False
    )
    print("Non-streaming response:")
    print(response.choices[0].message.content)
    
    # Streaming example
    print("\nStreaming response:")
    stream = client.chat.completions.create(
        model="claude-4-5-sonnet",
        messages=[
            {"role": "user", "content": "Tell me a short joke"}
        ],
        stream=True
    )
    for chunk in stream:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print()
