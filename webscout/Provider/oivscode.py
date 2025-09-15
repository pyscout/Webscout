import secrets
import requests
import random
import string
from typing import Union, Any, Dict, Generator

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions


class oivscode(Provider):
    """
    A class to interact with a test API.
    """
    required_auth = False
    AVAILABLE_MODELS = [
        "*",
        "Qwen/Qwen2.5-72B-Instruct-Turbo",
        "Qwen/Qwen2.5-Coder-32B-Instruct",
        "claude-3-5-sonnet-20240620",
        "claude-3-5-sonnet-20241022",
        "claude-3-7-sonnet-20250219",
        "custom/blackbox-base",
        "custom/blackbox-pro",
        "custom/blackbox-pro-designer",
        "custom/blackbox-pro-plus",
        "deepseek-r1",
        "deepseek-v3",
        "deepseek/deepseek-chat",
        "gemini-2.5-pro-preview-03-25",
        "gpt-4o-mini",
        "grok-3-beta",
        "image-gen",
        "llama-4-maverick-17b-128e-instruct-fp8",
        "o1",
        "o3-mini",
        "o4-mini",
        "transcribe",
        "anthropic/claude-sonnet-4"
    ]


    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 1024,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "claude-3-5-sonnet-20240620",
        system_prompt: str = "You are a helpful AI assistant.",
        
    ):
        """
        Initializes the oivscode with given parameters.
        """
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")


        self.session = requests.Session()
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.api_endpoints = [
            "https://oi-vscode-server.onrender.com/v1/chat/completions",
            "https://oi-vscode-server-2.onrender.com/v1/chat/completions",
            "https://oi-vscode-server-5.onrender.com/v1/chat/completions",
            "https://oi-vscode-server-0501.onrender.com/v1/chat/completions"
        ]
        self.api_endpoint = random.choice(self.api_endpoints)
        self.timeout = timeout
        self.last_response = {}
        self.model = model
        self.system_prompt = system_prompt
        self.headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9,en-GB;q=0.8,en-IN;q=0.7",
            "cache-control": "no-cache",
            "content-type": "application/json",
            "pragma": "no-cache",
            "priority": "u=1, i",
            "sec-ch-ua": '"Not A(Brand";v="8", "Chromium";v="132", "Microsoft Edge";v="132"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
        }
        self.userid = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(21))
        self.headers["userid"] = self.userid


        self.__available_optimizers = (
            method
            for method in dir(Optimizers)
            if callable(getattr(Optimizers, method)) and not method.startswith("__")
        )
        self.session.headers.update(self.headers)
        Conversation.intro = (
            AwesomePrompts().get_act(
                act, raise_not_found=True, default=None, case_insensitive=True
            )
            if act
            else intro or Conversation.intro
        )
        self.conversation = Conversation(
            is_conversation, self.max_tokens_to_sample, filepath, update_file
        )
        self.conversation.history_offset = history_offset
        self.session.proxies = proxies

    def _post_with_failover(self, payload, stream, timeout):
        """Try all endpoints until one succeeds, else raise last error."""
        endpoints = self.api_endpoints.copy()
        random.shuffle(endpoints)
        last_exception = None
        for endpoint in endpoints:
            try:
                response = self.session.post(endpoint, json=payload, stream=stream, timeout=timeout)
                if not response.ok:
                    last_exception = exceptions.FailedToGenerateResponseError(
                        f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                    )
                    continue
                return response
            except Exception as e:
                last_exception = e
                continue
        if last_exception:
            raise last_exception
        raise exceptions.FailedToGenerateResponseError("All API endpoints failed.")

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator[Any, None, None]]:
        """Chat with AI (DeepInfra-style streaming and non-streaming)"""
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise Exception(
                    f"Optimizer is not one of {self.__available_optimizers}"
                )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": conversation_prompt},
            ],
            "stream": stream
        }

        def for_stream():
            streaming_text = ""
            try:
                response = self._post_with_failover(payload, stream=True, timeout=self.timeout)
                response.raise_for_status()
                # Use sanitize_stream for robust OpenAI-style streaming
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None),
                    intro_value="data:",
                    to_json=True,
                    skip_markers=["[DONE]"],
                    content_extractor=lambda chunk: chunk.get("choices", [{}])[0].get("delta", {}).get("content") if isinstance(chunk, dict) else None,
                    yield_raw_on_error=False
                )
                for content_chunk in processed_stream:
                    if content_chunk and isinstance(content_chunk, str):
                        streaming_text += content_chunk
                        resp = dict(text=content_chunk)
                        yield resp if not raw else content_chunk
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"Streaming request failed: {e}") from e
            finally:
                if streaming_text:
                    self.last_response = {"text": streaming_text}
                    self.conversation.update_chat_history(prompt, streaming_text)

        def for_non_stream():
            try:
                response = self._post_with_failover(payload, stream=False, timeout=self.timeout)
                response.raise_for_status()
                response_text = response.text
                processed_stream = sanitize_stream(
                    data=response_text,
                    to_json=True,
                    intro_value=None,
                    content_extractor=lambda chunk: chunk.get("choices", [{}])[0].get("message", {}).get("content") if isinstance(chunk, dict) else None,
                    yield_raw_on_error=False
                )
                content = next(processed_stream, None)
                content = content if isinstance(content, str) else ""
                self.last_response = {"text": content}
                self.conversation.update_chat_history(prompt, content)
                return self.last_response if not raw else content
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"Non-streaming request failed: {e}") from e

        return for_stream() if stream else for_non_stream()


    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[str, Generator[str, None, None]]:
        """Generate response `str`
        Args:
            prompt (str): Prompt to be send.
            stream (bool, optional): Flag for streaming response. Defaults to False.
            optimizer (str, optional): Prompt optimizer name - `[code, shell_command]`. Defaults to None.
            conversationally (bool, optional): Chat conversationally when using optimizer. Defaults to False.
        Returns:
            str: Response generated
        """
        def for_stream():
             for response in self.ask(
                prompt, True, optimizer=optimizer, conversationally=conversationally
            ):
                yield self.get_message(response)
        def for_non_stream():
            return self.get_message(
                self.ask(
                    prompt,
                    False,
                    optimizer=optimizer,
                    conversationally=conversationally,
                )
            )
        return for_stream() if stream else for_non_stream()

    def get_message(self, response: dict) -> str:
        """Retrieves message content from response, handling both streaming and non-streaming formats."""
        assert isinstance(response, dict), "Response should be of dict data-type only"
        # Streaming chunk: choices[0]["delta"]["content"]
        if "choices" in response and response["choices"]:
            choice = response["choices"][0]
            if "delta" in choice and "content" in choice["delta"]:
                return choice["delta"]["content"]
            if "message" in choice and "content" in choice["message"]:
                return choice["message"]["content"]
        # Fallback for non-standard or legacy responses
        if "text" in response:
            return response["text"]
        return ""

    def fetch_available_models(self):
        """Fetches available models from the /models endpoint of all API endpoints and prints models per endpoint."""
        endpoints = self.api_endpoints.copy()
        random.shuffle(endpoints)
        results = {}
        errors = []
        for endpoint in endpoints:
            models_url = endpoint.replace('/v1/chat/completions', '/v1/models')
            try:
                response = self.session.get(models_url, timeout=self.timeout)
                if response.ok:
                    data = response.json()
                    if isinstance(data, dict) and "data" in data:
                        models = [m["id"] if isinstance(m, dict) and "id" in m else m for m in data["data"]]
                    elif isinstance(data, list):
                        models = data
                    else:
                        models = list(data.keys()) if isinstance(data, dict) else []
                    results[models_url] = models
                else:
                    errors.append(f"Failed to fetch models from {models_url}: {response.status_code} {response.text}")
            except Exception as e:
                errors.append(f"Error fetching from {models_url}: {e}")
        if results:
            for url, models in results.items():
                print(f"Models from {url}:")
                if models:
                    for m in sorted(models):
                        print(f"  {m}")
                else:
                    print("  No models found.")
            return results
        else:
            print("No models found from any endpoint.")
            for err in errors:
                print(err)
            return {}

if __name__ == "__main__":
    from rich import print
    chatbot = oivscode()
    chatbot.fetch_available_models()
    response = chatbot.chat(input(">>> "), stream=True)
    for chunk in response:
        print(chunk, end="", flush=True)
