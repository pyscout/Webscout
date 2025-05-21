import time
import uuid
import requests
import json
from typing import List, Dict, Optional, Union, Generator, Any

from webscout.litagent import LitAgent
from .base import BaseChat, BaseCompletions, OpenAICompatibleProvider
from .utils import (
    ChatCompletion,
    ChatCompletionChunk,
    Choice,
    ChatCompletionMessage,
    ChoiceDelta,
    CompletionUsage,
    format_prompt,
    count_tokens,
)

# ANSI escape codes for formatting
BOLD = "\033[1m"
RED = "\033[91m"
RESET = "\033[0m"

# Model configurations
MODEL_CONFIGS = {
    "exaanswer": {
        "endpoint": "https://ayle.chat/api/exaanswer",
        "models": ["exaanswer"],
    },
    "gemini": {
        "endpoint": "https://ayle.chat/api/gemini",
        "models": [
            "gemini-2.0-flash",
            "gemini-2.0-flash-exp-image-generation",
            "gemini-2.0-flash-thinking-exp-01-21",
            "gemini-2.5-pro-exp-03-25",
            "gemini-2.0-pro-exp-02-05",
            "gemini-2.5-flash-preview-04-17",

        
        ],
    },
    "openrouter": {
        "endpoint": "https://ayle.chat/api/openrouter",
        "models": [
            "mistralai/mistral-small-3.1-24b-instruct:free",
            "deepseek/deepseek-r1:free",
            "deepseek/deepseek-chat-v3-0324:free",
            "google/gemma-3-27b-it:free",
            "meta-llama/llama-4-maverick:free",           
        ],
    },
    "groq": {
        "endpoint": "https://ayle.chat/api/groq",
        "models": [
            "deepseek-r1-distill-llama-70b",
            "deepseek-r1-distill-qwen-32b",
            "gemma2-9b-it",
            "llama-3.1-8b-instant",
            "llama-3.2-1b-preview",
            "llama-3.2-3b-preview",
            "llama-3.2-90b-vision-preview",
            "llama-3.3-70b-specdec",
            "llama-3.3-70b-versatile",
            "llama3-70b-8192",
            "llama3-8b-8192",
            "qwen-2.5-32b",
            "qwen-2.5-coder-32b",
            "qwen-qwq-32b",
            "meta-llama/llama-4-scout-17b-16e-instruct"
        ],
    },
    "cerebras": {
        "endpoint": "https://ayle.chat/api/cerebras",
        "models": [
            "llama3.1-8b",
            "llama-3.3-70b"
        ],
    },
    "xai": {
        "endpoint": "https://ayle.chat/api/xai",
        "models": [
            "grok-3-mini-beta"
        ],
    },
}


class Completions(BaseCompletions):
    def __init__(self, client: 'ExaChat'):
        self._client = client

    def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,  # Not used directly but kept for compatibility
        stream: bool = False,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Creates a model response for the given chat conversation.
        Mimics openai.chat.completions.create
        """
        # Format the messages using the format_prompt utility
        # This creates a conversation in the format: "User: message\nAssistant: response\nUser: message\nAssistant:"
        question = format_prompt(messages, add_special_tokens=True, do_continue=True)
        
        # Determine the provider based on the model
        provider = self._client._get_provider_from_model(model)
        
        # Build the appropriate payload based on the provider
        if provider == "exaanswer":
            payload = {
                "query": question,
                "messages": []
            }
        elif provider in ["gemini", "cerebras"]:
            payload = {
                "query": question,
                "model": model,
                "messages": []
            }
        else:  # openrouter or groq
            payload = {
                "query": question + "\n",  # Add newline for openrouter and groq models
                "model": model,
                "messages": []
            }

        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())

        if stream:
            return self._create_stream(request_id, created_time, model, provider, payload)
        else:
            return self._create_non_stream(request_id, created_time, model, provider, payload)

    def _create_stream(
        self, request_id: str, created_time: int, model: str, provider: str, payload: Dict[str, Any]
    ) -> Generator[ChatCompletionChunk, None, None]:
        try:
            endpoint = self._client._get_endpoint(provider)
            response = self._client.session.post(
                endpoint,
                headers=self._client.headers,
                json=payload,
                stream=True,
                timeout=self._client.timeout
            )
            response.raise_for_status()

            # Track token usage across chunks
            completion_tokens = 0
            streaming_text = ""

            for line in response.iter_lines():
                if not line:
                    continue
                
                try:
                    data = json.loads(line.decode('utf-8'))
                    if 'choices' in data and len(data['choices']) > 0:
                        content = data['choices'][0].get('delta', {}).get('content', '')
                        if content:
                            streaming_text += content
                            completion_tokens += count_tokens(content)
                            
                            # Create a delta object for this chunk
                            delta = ChoiceDelta(content=content)
                            choice = Choice(index=0, delta=delta, finish_reason=None)
                            
                            chunk = ChatCompletionChunk(
                                id=request_id,
                                choices=[choice],
                                created=created_time,
                                model=model,
                            )
                            
                            yield chunk
                except json.JSONDecodeError:
                    continue

            # Final chunk with finish_reason
            delta = ChoiceDelta(content=None)
            choice = Choice(index=0, delta=delta, finish_reason="stop")
            
            chunk = ChatCompletionChunk(
                id=request_id,
                choices=[choice],
                created=created_time,
                model=model,
            )
            
            yield chunk

        except requests.exceptions.RequestException as e:
            print(f"{RED}Error during ExaChat stream request: {e}{RESET}")
            raise IOError(f"ExaChat request failed: {e}") from e

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str, provider: str, payload: Dict[str, Any]
    ) -> ChatCompletion:
        try:
            endpoint = self._client._get_endpoint(provider)
            response = self._client.session.post(
                endpoint,
                headers=self._client.headers,
                json=payload,
                timeout=self._client.timeout
            )
            response.raise_for_status()

            full_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode('utf-8'))
                        if 'choices' in data and len(data['choices']) > 0:
                            content = data['choices'][0].get('delta', {}).get('content', '')
                            if content:
                                full_response += content
                    except json.JSONDecodeError:
                        continue

            # Create usage statistics (estimated)
            prompt_tokens = count_tokens(payload["query"])
            completion_tokens = count_tokens(full_response)
            total_tokens = prompt_tokens + completion_tokens
            
            usage = CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )
            
            # Create the message object
            message = ChatCompletionMessage(
                role="assistant",
                content=full_response
            )
            
            # Create the choice object
            choice = Choice(
                index=0,
                message=message,
                finish_reason="stop"
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

        except Exception as e:
            print(f"{RED}Error during ExaChat non-stream request: {e}{RESET}")
            raise IOError(f"ExaChat request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'ExaChat'):
        self.completions = Completions(client)

class ExaChat(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for ExaChat API.

    Usage:
        client = ExaChat()
        response = client.chat.completions.create(
            model="exaanswer",
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print(response.choices[0].message.content)
    """

    AVAILABLE_MODELS = [
        # ExaAnswer Models
        "exaanswer",

        # XAI Models
        "grok-3-mini-beta",
        
        # Gemini Models
        "gemini-2.0-flash",
        "gemini-2.0-flash-exp-image-generation",
        "gemini-2.0-flash-thinking-exp-01-21",
        "gemini-2.5-pro-exp-03-25",
        "gemini-2.0-pro-exp-02-05",
        "gemini-2.5-flash-preview-04-17",
        
        # OpenRouter Models
        "mistralai/mistral-small-3.1-24b-instruct:free",
        "deepseek/deepseek-r1:free",
        "deepseek/deepseek-chat-v3-0324:free",
        "google/gemma-3-27b-it:free",
        "meta-llama/llama-4-maverick:free",
        
        # Groq Models
        "deepseek-r1-distill-llama-70b",
        "deepseek-r1-distill-qwen-32b",
        "gemma2-9b-it",
        "llama-3.1-8b-instant",
        "llama-3.2-1b-preview",
        "llama-3.2-3b-preview",
        "llama-3.2-90b-vision-preview",
        "llama-3.3-70b-specdec",
        "llama-3.3-70b-versatile",
        "llama3-70b-8192",
        "llama3-8b-8192",
        "qwen-2.5-32b",
        "qwen-2.5-coder-32b",
        "qwen-qwq-32b",
        "meta-llama/llama-4-scout-17b-16e-instruct",

        
        # Cerebras Models
        "llama3.1-8b",
        "llama-3.3-70b",

    ]

    def __init__(
        self,
        timeout: int = 30,
        temperature: float = 0.5,
        top_p: float = 1.0
    ):
        """
        Initialize the ExaChat client.

        Args:
            timeout: Request timeout in seconds.
            temperature: Temperature for response generation.
            top_p: Top-p sampling parameter.
        """
        self.timeout = timeout
        self.temperature = temperature
        self.top_p = top_p
        
        # Initialize LitAgent for user agent generation
        agent = LitAgent()
        
        self.headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "content-type": "application/json",
            "origin": "https://ayle.chat/",
            "referer": "https://ayle.chat//",
            "user-agent": agent.random(),
        }
        
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.session.cookies.update({"session": uuid.uuid4().hex})
        
        # Initialize the chat interface
        self.chat = Chat(self)

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()
    def _get_endpoint(self, provider: str) -> str:
        """Get the API endpoint for the specified provider."""
        return MODEL_CONFIGS[provider]["endpoint"]

    def _get_provider_from_model(self, model: str) -> str:
        """Determine the provider based on the model name."""
        for provider, config in MODEL_CONFIGS.items():
            if model in config["models"]:
                return provider
        
        # If model not found, use a default model
        print(f"{BOLD}Warning: Model '{model}' not found, using default model 'exaanswer'{RESET}")
        return "exaanswer"

    def convert_model_name(self, model: str) -> str:
        """
        Ensure the model name is in the correct format.
        """
        if model in self.AVAILABLE_MODELS:
            return model
        
        # Try to find a matching model
        for available_model in self.AVAILABLE_MODELS:
            if model.lower() in available_model.lower():
                return available_model
        
        # Default to exaanswer if no match
        print(f"{BOLD}Warning: Model '{model}' not found, using default model 'exaanswer'{RESET}")
        return "exaanswer"


# Simple test if run directly
if __name__ == "__main__":
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)

    # Test a subset of models to avoid excessive API calls
    test_models = [
        "exaanswer",
        "gemini-2.0-flash",
        "deepseek/deepseek-r1:free",
        "llama-3.1-8b-instant",
        "llama3.1-8b"
    ]

    for model in test_models:
        try:
            client = ExaChat(timeout=60)
            # Test with a simple conversation to demonstrate format_prompt usage
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Say 'Hello' in one word"},
                ],
                stream=False
            )
            
            if response and response.choices and response.choices[0].message.content:
                status = "✓"
                # Truncate response if too long
                display_text = response.choices[0].message.content.strip()
                display_text = display_text[:50] + "..." if len(display_text) > 50 else display_text
            else:
                status = "✗"
                display_text = "Empty or invalid response"
            print(f"{model:<50} {status:<10} {display_text}")
        except Exception as e:
            print(f"{model:<50} {'✗':<10} {str(e)}")
