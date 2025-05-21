import time
import uuid
import requests
import json
import re
from typing import List, Dict, Optional, Union, Generator, Any

# Import base classes and utility structures
from .base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from .utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage,
    get_system_prompt, get_last_user_message, format_prompt, count_tokens
)

# Attempt to import LitAgent, fallback if not available
try:
    from webscout.litagent import LitAgent
except ImportError:
    # Define a dummy LitAgent if webscout is not installed or accessible
    class LitAgent:
        def generate_fingerprint(self, browser: str = "chrome") -> Dict[str, Any]:
            # Return minimal default headers if LitAgent is unavailable
            print("Warning: LitAgent not found. Using default minimal headers.")
            return {
                "accept": "*/*",
                "accept_language": "en-US,en;q=0.9",
                "platform": "Windows",
                "sec_ch_ua": '"Not/A)Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
                "browser_type": browser,
            }
        def random(self) -> str:
             # Return a default user agent if LitAgent is unavailable
             print("Warning: LitAgent not found. Using default user agent.")
             return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"


class Completions(BaseCompletions):
    def __init__(self, client: 'C4AI'):
        self._client = client

    def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = 2000,
        stream: bool = False,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """
        Creates a model response for the given chat conversation.
        Mimics openai.chat.completions.create
        """
        # Extract system prompt using utility function
        system_prompt = get_system_prompt(messages)
        if not system_prompt:
            system_prompt = "You are a helpful assistant."

        # Format the conversation history using format_prompt
        # Note: C4AI API might expect only the *last* user message here.
        # Sending the full history might cause issues.
        # We exclude the system prompt from format_prompt as it's sent separately.
        # We also set do_continue=True as C4AI adds its own assistant prompt implicitly.
        conversation_prompt = format_prompt(messages, include_system=False, do_continue=True)

        if not conversation_prompt:
             # Fallback to last user message if formatted prompt is empty
             last_user_message = get_last_user_message(messages)
             if not last_user_message:
                 raise ValueError("No user message found or formatted prompt is empty.")
             conversation_prompt = last_user_message

        # Create or get conversation ID
        if model not in self._client._conversation_data:
            conversation_id = self._client.create_conversation(model, system_prompt)
            if not conversation_id:
                raise IOError(f"Failed to create conversation with model {model}")
        else:
            conversation_id = self._client._conversation_data[model]["conversationId"]
            self._client._conversation_data[model]["messageId"] = self._client.fetch_message_id(conversation_id)

        request_id = f"chatcmpl-{uuid.uuid4()}"
        created_time = int(time.time())

        # Pass the formatted conversation prompt
        if stream:
            return self._create_stream(request_id, created_time, model, conversation_id, conversation_prompt, system_prompt)
        else:
            return self._create_non_stream(request_id, created_time, model, conversation_id, conversation_prompt, system_prompt)

    def _create_stream(
        self, request_id: str, created_time: int, model: str, conversation_id: str, prompt: str, system_prompt: str
    ) -> Generator[ChatCompletionChunk, None, None]:
        try:
            message_id = self._client._conversation_data[model]["messageId"]
            url = f"{self._client.url}/api/chat/message"
            payload = {
                "conversationId": conversation_id,
                "messageId": message_id,
                "model": model,
                "prompt": prompt, # Use the formatted conversation history as prompt
                "preprompt": system_prompt,
                "temperature": 0.7,
                "top_p": 1,
                "top_k": 50,
                "max_tokens": self._client.max_tokens_to_sample,
                "stop": [],
                "stream": True
            }

            response = self._client.session.post(
                url,
                headers=self._client.headers,
                json=payload,
                stream=True,
                timeout=self._client.timeout
            )
            response.raise_for_status()

            full_text = ""
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == "[DONE]":
                            break

                        try:
                            json_data = json.loads(data)
                            delta_text = json_data.get('text', '')
                            new_content = delta_text[len(full_text):]
                            full_text = delta_text
                            delta = ChoiceDelta(content=new_content)
                            choice = Choice(index=0, delta=delta, finish_reason=None)
                            chunk = ChatCompletionChunk(
                                id=request_id,
                                choices=[choice],
                                created=created_time,
                                model=model
                            )
                            yield chunk
                        except json.JSONDecodeError:
                            continue

            delta = ChoiceDelta(content=None)
            choice = Choice(index=0, delta=delta, finish_reason="stop")
            chunk = ChatCompletionChunk(
                id=request_id,
                choices=[choice],
                created=created_time,
                model=model
            )
            yield chunk

        except Exception as e:
            print(f"Error during C4AI stream request: {e}")
            raise IOError(f"C4AI request failed: {e}") from e

    def _create_non_stream(
        self, request_id: str, created_time: int, model: str, conversation_id: str, prompt: str, system_prompt: str
    ) -> ChatCompletion:
        try:
            message_id = self._client._conversation_data[model]["messageId"]
            url = f"{self._client.url}/api/chat/message"
            payload = {
                "conversationId": conversation_id,
                "messageId": message_id,
                "model": model,
                "prompt": prompt, # Use the formatted conversation history as prompt
                "preprompt": system_prompt,
                "temperature": 0.7,
                "top_p": 1,
                "top_k": 50,
                "max_tokens": self._client.max_tokens_to_sample,
                "stop": [],
                "stream": False
            }

            response = self._client.session.post(
                url,
                headers=self._client.headers,
                json=payload,
                timeout=self._client.timeout
            )
            response.raise_for_status()

            data = response.json()
            response_text = data.get('text', '')
            message = ChatCompletionMessage(role="assistant", content=response_text)
            choice = Choice(index=0, message=message, finish_reason="stop")
            # Estimate tokens based on the formatted prompt
            prompt_tokens = count_tokens(prompt)
            completion_tokens = count_tokens(response_text)
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

        except Exception as e:
            print(f"Error during C4AI non-stream request: {e}")
            raise IOError(f"C4AI request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'C4AI'):
        self.completions = Completions(client)

class C4AI(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for C4AI API.

    Usage:
        client = C4AI()
        response = client.chat.completions.create(
            model="command-a-03-2025",
            messages=[{"role": "user", "content": "Hello!"}]
        )
    """

    AVAILABLE_MODELS = [
        'command-a-03-2025',
        'command-r-plus-08-2024',
        'command-r-08-2024',
        'command-r-plus',
        'command-r',
        'command-r7b-12-2024',
        'command-r7b-arabic-02-2025'
    ]

    def __init__(
        self,
        timeout: Optional[int] = None,
        browser: str = "chrome"
    ):
        """
        Initialize the C4AI client.

        Args:
            timeout: Request timeout in seconds.
            browser: Browser name for LitAgent to generate User-Agent.
        """
        self.timeout = timeout
        self.url = "https://cohereforai-c4ai-command.hf.space"
        self.session = requests.Session()
        self.max_tokens_to_sample = 2000

        agent = LitAgent()
        fingerprint = agent.generate_fingerprint(browser)

        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": fingerprint["user_agent"],
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": fingerprint["accept_language"],
            "Origin": "https://cohereforai-c4ai-command.hf.space",
            "Referer": "https://cohereforai-c4ai-command.hf.space/",
            "Sec-Ch-Ua": fingerprint["sec_ch_ua"] or "\"Chromium\";v=\"120\"",
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": f"\"{fingerprint['platform']}\"",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "DNT": "1",
            "Priority": "u=1, i"
        }

        self._conversation_data = {}
        self.chat = Chat(self)
        self.update_available_models()

    def update_available_models(self):
        """Update the list of available models from the server."""
        try:
            response = requests.get("https://cohereforai-c4ai-command.hf.space/")
            text = response.text
            models_match = re.search(r'models:(\[.+?\]),oldModels:', text)

            if not models_match:
                return

            models_text = models_match.group(1)
            models_text = re.sub(r',parameters:{[^}]+?}', '', models_text)
            models_text = models_text.replace('void 0', 'null')

            def add_quotation_mark(match):
                return f'{match.group(1)}"{match.group(2)}":'

            models_text = re.sub(r'([{,])([A-Za-z0-9_]+?):', add_quotation_mark, models_text)

            models_data = json.loads(models_text)
            self.AVAILABLE_MODELS = [model["id"] for model in models_data]
        except Exception:
            pass

    def create_conversation(self, model: str, system_prompt: str):
        """Create a new conversation with the specified model."""
        url = f"{self.url}/api/conversation"
        payload = {
            "model": model,
            "preprompt": system_prompt,
        }

        try:
            response = self.session.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            conversation_id = data.get("conversationId")

            if conversation_id:
                self._conversation_data[model] = {
                    "conversationId": conversation_id,
                    "messageId": self.fetch_message_id(conversation_id)
                }
                return conversation_id

            return None

        except Exception as e:
            print(f"Error creating conversation: {e}")
            return None

    def fetch_message_id(self, conversation_id: str):
        """Fetch the latest message ID for a conversation."""
        url = f"{self.url}/api/conversation/{conversation_id}"

        try:
            response = self.session.get(
                url,
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()

            json_data = response.json()

            if json_data.get("nodes", []) and json_data["nodes"][-1].get("type") == "error":
                return str(uuid.uuid4())

            data = json_data["nodes"][1]["data"]
            keys = data[data[0]["messages"]]
            message_keys = data[keys[-1]]
            message_id = data[message_keys["id"]]

            return message_id

        except Exception:
            return str(uuid.uuid4())
    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()