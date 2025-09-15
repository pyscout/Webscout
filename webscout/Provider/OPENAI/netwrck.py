import time
import uuid
import requests
import json
from typing import List, Dict, Optional, Union, Generator, Any

from webscout.litagent import LitAgent
from webscout.Provider.OPENAI.base import BaseChat, BaseCompletions, OpenAICompatibleProvider
from webscout.Provider.OPENAI.utils import (
    ChatCompletion,
    ChatCompletionChunk,
    Choice,
    ChatCompletionMessage,
    ChoiceDelta,
    CompletionUsage,
    format_prompt,
    get_system_prompt,
    count_tokens
)

# ANSI escape codes for formatting
BOLD = "\033[1m"
RED = "\033[91m"
RESET = "\033[0m"

class Completions(BaseCompletions):
    def __init__(self, client: 'Netwrck'):
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
        timeout: Optional[int] = None,
        proxies: Optional[Dict[str, str]] = None,
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Creates a model response for the given chat conversation.
        Mimics openai.chat.completions.create
        """
        # Format the messages using the format_prompt utility
        # This creates a conversation in the format: "User: message\nAssistant: response\nUser: message\nAssistant:"
        formatted_prompt = format_prompt(messages, add_special_tokens=True, do_continue=True)
        
       
        # Prepare the payload for Netwrck API
        payload = {
            "query": formatted_prompt,
            "context": get_system_prompt(messages),
            "examples": [],
            "model_name": self._client.convert_model_name(model),
            "greeting": self._client.greeting
        }

        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())

        if stream:
            return self._create_stream(request_id, created_time, model, payload, timeout, proxies)
        else:
            return self._create_non_stream(request_id, created_time, model, payload, timeout, proxies)

    def _create_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any], timeout: Optional[int] = None, proxies: Optional[Dict[str, str]] = None
    ) -> Generator[ChatCompletionChunk, None, None]:
        try:
            response = self._client.session.post(
                "https://netwrck.com/api/chatpred_or",
                json=payload,
                headers=self._client.headers,
                timeout=timeout or self._client.timeout,
                proxies=proxies or getattr(self._client, "proxies", None),
                stream=True
            )
            response.raise_for_status()

            # Track token usage across chunks
            completion_tokens = 0
            streaming_text = ""

            for line in response.iter_lines():
                if not line:
                    continue
                
                try:
                    decoded_line = line.decode('utf-8').strip('"')
                    if decoded_line:
                        # Format the decoded line using the client's formatter
                        formatted_content = self._client.format_text(decoded_line)
                        streaming_text += formatted_content
                        completion_tokens += count_tokens(formatted_content)
                        
                        # Create a delta object for this chunk
                        delta = ChoiceDelta(content=formatted_content)
                        choice = Choice(index=0, delta=delta, finish_reason=None)
                        
                        chunk = ChatCompletionChunk(
                            id=request_id,
                            choices=[choice],
                            created=created_time,
                            model=model,
                        )
                        
                        yield chunk
                except Exception:
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
            print(f"{RED}Error during Netwrck stream request: {e}{RESET}")
            raise IOError(f"Netwrck request failed: {e}") from e

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str, payload: Dict[str, Any], timeout: Optional[int] = None, proxies: Optional[Dict[str, str]] = None
    ) -> ChatCompletion:
        try:
            response = self._client.session.post(
                "https://netwrck.com/api/chatpred_or",
                json=payload,
                headers=self._client.headers,
                timeout=timeout or self._client.timeout,
                proxies=proxies or getattr(self._client, "proxies", None)
            )
            response.raise_for_status()
            
            # Process the response
            raw_response = response.text.strip('"')
            # Format the full response using the client's formatter
            full_response = self._client.format_text(raw_response)

            # Create usage statistics using count_tokens
            prompt_tokens = count_tokens(payload.get("query", ""))
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
            print(f"{RED}Error during Netwrck non-stream request: {e}{RESET}")
            raise IOError(f"Netwrck request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'Netwrck'):
        self.completions = Completions(client)

class Netwrck(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for Netwrck API.

    Usage:
        client = Netwrck()
        response = client.chat.completions.create(
            model="anthropic/claude-3-7-sonnet-20250219",
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print(response.choices[0].message.content)
    """

    AVAILABLE_MODELS = [
        "thedrummer/valkyrie-49b-v1",
        "thedrummer/skyfall-36b-v2",
        "sao10k/l3-euryale-70b",
        "deepseek/deepseek-chat",
        "deepseek/deepseek-r1",
        "gryphe/mythomax-l2-13b",
        "nvidia/llama-3.1-nemotron-70b-instruct",
    ]

    # Default greeting used by Netwrck
    greeting = """Hello! I'm a helpful assistant. How can I help you today?"""

    def __init__(
        self,
        timeout: int = 30,
        temperature: float = 0.7,
        top_p: float = 0.8,
        system_prompt: str = "You are a helpful assistant."
    ):
        """
        Initialize the Netwrck client.

        Args:
            timeout: Request timeout in seconds.
            temperature: Temperature for response generation.
            top_p: Top-p sampling parameter.
            system_prompt: System prompt to use for the conversation.
        """
        self.timeout = timeout
        self.temperature = temperature
        self.top_p = top_p
        self.system_prompt = system_prompt
        
        # Initialize LitAgent for user agent generation
        agent = LitAgent()
        
        self.headers = {
            'authority': 'netwrck.com',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://netwrck.com',
            'referer': 'https://netwrck.com/',
            'user-agent': agent.random()
        }
        
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Initialize the chat interface
        self.chat = Chat(self)

    def format_text(self, text: str) -> str:
        """
        Format text by replacing escaped newlines with actual newlines.

        Args:
            text: Text to format

        Returns:
            Formatted text
        """
        # Use a more comprehensive approach to handle all escape sequences
        try:
            # First handle double backslashes to avoid issues
            text = text.replace('\\\\', '\\')

            # Handle common escape sequences
            text = text.replace('\\n', '\n')
            text = text.replace('\\r', '\r')
            text = text.replace('\\t', '\t')
            text = text.replace('\\"', '"')
            text = text.replace("\\'", "'")

            # Handle any remaining escape sequences using JSON decoding
            # This is a fallback in case there are other escape sequences
            try:
                # Add quotes to make it a valid JSON string
                json_str = f'"{text}"'
                # Use json module to decode all escape sequences
                decoded = json.loads(json_str)
                return decoded
            except json.JSONDecodeError:
                # If JSON decoding fails, return the text with the replacements we've already done
                return text
        except Exception as e:
            # If any error occurs, return the original text
            print(f"Warning: Error formatting text: {e}")
            return text

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
        
        # Default to DeepSeek if no match
        print(f"{BOLD}Warning: Model '{model}' not found, using default model 'deepseek/deepseek-r1'{RESET}")
        return "deepseek/deepseek-r1"

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()

# Simple test if run directly
if __name__ == "__main__":
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)

    # Test a subset of models to avoid excessive API calls
    test_models = [
        "deepseek/deepseek-r1",
        "deepseek/deepseek-chat",
        "gryphe/mythomax-l2-13b"
    ]

    for model in test_models:
        try:
            client = Netwrck(timeout=60)
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
