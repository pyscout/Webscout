import requests
import random
import datetime
from typing import Any, Dict, Union, Generator
from webscout.AIutel import Optimizers, Conversation, AwesomePrompts
from webscout.AIbase import Provider
from webscout import exceptions

class NEMOTRON(Provider):
    """NEMOTRON provider for interacting with the nemotron.one API."""
    url = "https://nemotron.one/api/chat"
    required_auth = False
    AVAILABLE_MODELS = [
        "gpt4o",
        "nemotron70b",
    ]

    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 8000,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "gpt4o"
    ):
        """Initialize NEMOTRON with configuration options."""
        self.session = requests.Session()
        self.max_tokens = max_tokens
        self.is_conversation = is_conversation
        self.timeout = timeout
        self.last_response = {}
        self.model = self.get_model(model)

        self.headers = {
            "authority": "nemotron.one",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "content-type": "application/json",
            "origin": "https://nemotron.one",
            "referer": f"https://nemotron.one/chat/{self.model}",
            "sec-ch-ua": '"Chromium";v="136", "Not.A/Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        }

        self.__available_optimizers = (
            method for method in dir(Optimizers)
            if callable(getattr(Optimizers, method)) and not method.startswith("__")
        )

        Conversation.intro = (
            AwesomePrompts().get_act(
                act, raise_not_found=True, default=None, case_insensitive=True
            )
            if act
            else intro or Conversation.intro
        )
        
        self.conversation = Conversation(
            is_conversation, self.max_tokens, filepath, update_file
        )
        self.conversation.history_offset = history_offset
        self.session.proxies = proxies

    @staticmethod
    def _generate_random_email() -> str:
        """Generate a random email address."""
        random_letter = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        random_string = ''.join(random.choice(random_letter) for _ in range(10))
        return f"{random_string}@gmail.com"

    @staticmethod
    def _generate_random_id() -> str:
        """Generate a random user ID."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
        random_letter = "abcdefghijklmnopqrstuvwxyz0123456789"
        random_string = ''.join(random.choice(random_letter) for _ in range(8))
        return f"cm{random_string}{timestamp[:10]}"

    @classmethod
    def get_model(cls, model: str) -> str:
        """Resolve model name from alias."""
        if model in cls.AVAILABLE_MODELS:
            return model  # Simply return the model name if it's in the list
        raise ValueError(f"Unknown model: {model}. Available models: {', '.join(cls.AVAILABLE_MODELS)}")

    def _get_user_data(self) -> Dict[str, Any]:
        """Generate user data for the request."""
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

    def _make_request(
        self,
        message: str,
        stream: bool = False,
        raw: bool = False
    ) -> Generator[str, None, None]:
        """Make request to NEMOTRON API."""
        payload = {
            "content": message,
            "imageSrc": "",
            "model": self.model,
            "user": self._get_user_data(),
            "conversationId": ""
        }

        try:
            if stream:
                with self.session.post(
                    self.url,
                    headers=self.headers,
                    json=payload,
                    stream=True,
                    timeout=self.timeout
                ) as response:
                    response.raise_for_status()
                    buffer = ""
                    chunk_size = 32
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if not chunk:
                            continue
                        text = chunk.decode(errors="ignore")
                        buffer += text
                        while len(buffer) >= chunk_size:
                            out = buffer[:chunk_size]
                            buffer = buffer[chunk_size:]
                            if out.strip():
                                if raw:
                                    yield out
                                else:
                                    yield out
                    if buffer.strip():
                        if raw:
                            yield buffer
                        else:
                            yield buffer
            else:
                response = self.session.post(
                    self.url,
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()
                if raw:
                    yield response.text
                else:
                    yield response.text

        except requests.exceptions.RequestException as e:
            raise exceptions.ProviderConnectionError(f"Connection error: {str(e)}")

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, str], Generator[Dict[str, str], None, None]]:
        """Send a prompt to NEMOTRON API and return the response."""
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise ValueError(f"Optimizer is not one of {self.__available_optimizers}")

        def for_stream():
            for text in self._make_request(conversation_prompt, stream=True, raw=raw):
                if raw:
                    yield text
                else:
                    yield {"text": text}

        def for_non_stream():
            response_text = next(self._make_request(conversation_prompt, stream=False, raw=raw))
            if raw:
                self.last_response = response_text
                return response_text
            else:
                self.last_response = {"text": response_text}
                return self.last_response

        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[str, Generator[str, None, None]]:
        """Generate response as string."""
        def for_stream():
            for response in self.ask(
                prompt,
                stream=True,
                optimizer=optimizer,
                conversationally=conversationally
            ):
                yield self.get_message(response)

        def for_non_stream():
            return self.get_message(
                self.ask(
                    prompt,
                    stream=False,
                    optimizer=optimizer,
                    conversationally=conversationally,
                )
            )

        return for_stream() if stream else for_non_stream()

    def get_message(self, response: Dict[str, Any]) -> str:
        """Extract message from response dictionary."""
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response["text"]

if __name__ == "__main__":
    # Example usage
    nemotron = NEMOTRON()
    response = nemotron.chat("write me about humans in points", stream=True)
    for part in response:
        print(part, end="", flush=True)