import time
import uuid
import requests
import json
import random
import base64
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union, Generator, Any

# Import base classes and utility structures
from webscout.Provider.OPENAI.base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from webscout.Provider.OPENAI.utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage, count_tokens
)

# ANSI escape codes for formatting
BOLD = "\033[1m"
RED = "\033[91m"
RESET = "\033[0m"

class ChatGPTReversed:
    AVAILABLE_MODELS = [
        "auto", 
        "gpt-4o-mini", 
        "gpt-4o", 
        "o4-mini",
        "gpt-4-1",
        "gpt-4-1-mini",
        "o3",
        "o4-mini-high"



    ]
    csrf_token = None
    initialized = False

    _instance = None

    def __new__(cls, model="auto"):
        if cls._instance is None:
            cls._instance = super(ChatGPTReversed, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self, model="auto"):
        if self.initialized:
            # Already initialized, just update model if needed
            if model not in self.AVAILABLE_MODELS:
                raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")
            self.model = model
            return

        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        self.model = model
        self.initialize()

    def initialize(self):
        ChatGPTReversed.initialized = True

    def random_ip(self):
        """Generate a random IP address."""
        return ".".join(str(random.randint(0, 255)) for _ in range(4))

    def random_uuid(self):
        """Generate a random UUID."""
        return str(uuid.uuid4())

    def random_float(self, min_val, max_val):
        """Generate a random float between min and max."""
        return round(random.uniform(min_val, max_val), 4)

    def simulate_bypass_headers(self, accept, spoof_address=False, pre_oai_uuid=None):
        """Simulate browser headers to bypass detection."""
        simulated = {
            "agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
            "platform": "Windows",
            "mobile": "?0",
            "ua": 'Not A(Brand";v="8", "Chromium";v="132", "Google Chrome";v="132'
        }

        ip = self.random_ip()
        uuid_val = pre_oai_uuid or self.random_uuid()

        headers = {
            "accept": accept,
            "Content-Type": "application/json",
            "cache-control": "no-cache",
            "Referer": "https://chatgpt.com/",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "oai-device-id": uuid_val,
            "User-Agent": simulated["agent"],
            "pragma": "no-cache",
            "priority": "u=1, i",
            "sec-ch-ua": f"{simulated['ua']}",
            "sec-ch-ua-mobile": simulated["mobile"],
            "sec-ch-ua-platform": f"{simulated['platform']}",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
        }

        if spoof_address:
            headers.update({
                "X-Forwarded-For": ip,
                "X-Originating-IP": ip,
                "X-Remote-IP": ip,
                "X-Remote-Addr": ip,
                "X-Host": ip,
                "X-Forwarded-Host": ip
            })

        return headers

    def solve_sentinel_challenge(self, seed, difficulty):
        """Solve the sentinel challenge for authentication."""
        cores = [8, 12, 16, 24]
        screens = [3000, 4000, 6000]
        core = random.choice(cores)
        screen = random.choice(screens)

        # Adjust time to match expected timezone
        now = datetime.now() - timedelta(hours=8)
        parse_time = now.strftime("%a, %d %b %Y %H:%M:%S GMT+0100 (Central European Time)")

        config = [core + screen, parse_time, 4294705152, 0,
                 "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"]

        diff_len = len(difficulty) // 2

        for i in range(100000):
            config[3] = i
            json_data = json.dumps(config)
            base = base64.b64encode(json_data.encode()).decode()
            hash_value = hashlib.sha3_512((seed + base).encode()).hexdigest()

            if hash_value[:diff_len] <= difficulty:
                result = "gAAAAAB" + base
                return result

        # Fallback
        fallback_base = base64.b64encode(seed.encode()).decode()
        return "gAAAAABwQ8Lk5FbGpA2NcR9dShT6gYjU7VxZ4D" + fallback_base

    def generate_fake_sentinel_token(self):
        """Generate a fake sentinel token for initial authentication."""
        prefix = "gAAAAAC"
        config = [
            random.randint(3000, 6000),
            datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT+0100 (Central European Time)"),
            4294705152, 0,
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
            "de", "de", 401, "mediaSession", "location", "scrollX",
            self.random_float(1000, 5000),
            str(uuid.uuid4()), "", 12, int(time.time() * 1000)
        ]

        base64_str = base64.b64encode(json.dumps(config).encode()).decode()
        return prefix + base64_str

    def parse_response(self, input_text):
        """Parse the response from ChatGPT.

        Args:
            input_text (str): The response text from ChatGPT.

        Returns:
            The complete response as a string.
        """
        parts = [part.strip() for part in input_text.split("\n") if part.strip()]

        for part in parts:
            try:
                if part.startswith("data: "):
                    json_data = json.loads(part[6:])
                    if (json_data.get("message") and
                        json_data["message"].get("status") == "finished_successfully" and
                        json_data["message"].get("metadata", {}).get("is_complete")):
                        return json_data["message"]["content"]["parts"][0]
            except:
                pass

        return input_text # Return raw text if parsing fails or no complete message found

    def rotate_session_data(self):
        """Rotate session data to maintain fresh authentication."""
        uuid_val = self.random_uuid()
        csrf_token = self.get_csrf_token(uuid_val)
        sentinel_token = self.get_sentinel_token(uuid_val, csrf_token)

        ChatGPTReversed.csrf_token = csrf_token

        return {
            "uuid": uuid_val,
            "csrf": csrf_token,
            "sentinel": sentinel_token
        }

    def get_csrf_token(self, uuid_val):
        """Get CSRF token for authentication."""
        if ChatGPTReversed.csrf_token is not None:
            return ChatGPTReversed.csrf_token

        headers = self.simulate_bypass_headers(
            accept="application/json",
            spoof_address=True,
            pre_oai_uuid=uuid_val
        )

        response = requests.get(
            "https://chatgpt.com/api/auth/csrf",
            headers=headers
        )

        data = response.json()
        if "csrfToken" not in data:
            raise Exception("Failed to fetch required CSRF token")

        return data["csrfToken"]

    def get_sentinel_token(self, uuid_val, csrf):
        """Get sentinel token for authentication."""
        headers = self.simulate_bypass_headers(
            accept="application/json",
            spoof_address=True,
            pre_oai_uuid=uuid_val
        )

        test = self.generate_fake_sentinel_token()

        response = requests.post(
            "https://chatgpt.com/backend-anon/sentinel/chat-requirements",
            json={"p": test},
            headers={
                **headers,
                "Cookie": f"__Host-next-auth.csrf-token={csrf}; oai-did={uuid_val}; oai-nav-state=1;"
            }
        )

        data = response.json()
        if "token" not in data or "proofofwork" not in data:
            raise Exception("Failed to fetch required sentinel token")

        oai_sc = None
        for cookie in response.cookies:
            if cookie.name == "oai-sc":
                oai_sc = cookie.value
                break

        if not oai_sc:
            raise Exception("Failed to fetch required oai-sc token")

        challenge_token = self.solve_sentinel_challenge(
            data["proofofwork"]["seed"],
            data["proofofwork"]["difficulty"]
        )

        return {
            "token": data["token"],
            "proof": challenge_token,
            "oaiSc": oai_sc
        }

    def complete(self, message, model=None):
        """Complete a message using ChatGPT.

        Args:
            message (str): The message to send to ChatGPT.
            model (str, optional): The model to use. If None, uses the model specified during initialization.
                                   Defaults to None.

        Returns:
            The complete response as a string.
        """
        if not ChatGPTReversed.initialized:
            raise Exception("ChatGPTReversed has not been initialized. Please initialize the instance before calling this method.")

        # Use the provided model or fall back to the instance model
        selected_model = model if model else self.model

        # Validate the model
        if selected_model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {selected_model}. Choose from: {self.AVAILABLE_MODELS}")

        session_data = self.rotate_session_data()

        headers = self.simulate_bypass_headers(
            accept="plain/text", # Changed accept header as we expect full response now
            spoof_address=True,
            pre_oai_uuid=session_data["uuid"]
        )

        headers.update({
            "Cookie": f"__Host-next-auth.csrf-token={session_data['csrf']}; oai-did={session_data['uuid']}; oai-nav-state=1; oai-sc={session_data['sentinel']['oaiSc']};",
            "openai-sentinel-chat-requirements-token": session_data["sentinel"]["token"],
            "openai-sentinel-proof-token": session_data["sentinel"]["proof"]
        })

        payload = {
            "action": "next",
            "messages": [{
                "id": self.random_uuid(),
                "author": {
                    "role": "user"
                },
                "content": {
                    "content_type": "text",
                    "parts": [message]
                },
                "metadata": {}
            }],
            "parent_message_id": self.random_uuid(),
            "model": selected_model,  # Use the selected model
            "timezone_offset_min": -120,
            "suggestions": [],
            "history_and_training_disabled": False,
            "conversation_mode": {
                "kind": "primary_assistant",
                "plugin_ids": None # Ensure web search is not used
            },
            "force_paragen": False,
            "force_paragen_model_slug": "",
            "force_nulligen": False,
            "force_rate_limit": False,
            "reset_rate_limits": False,
            "websocket_request_id": self.random_uuid(),
            "force_use_sse": True # Keep SSE for receiving the full response
        }

        response = requests.post(
            "https://chatgpt.com/backend-anon/conversation",
            json=payload,
            headers=headers
        )

        if response.status_code != 200:
            raise Exception(f"HTTP error! status: {response.status_code}")

        return self.parse_response(response.text)


class Completions(BaseCompletions):
    def __init__(self, client: 'ChatGPT'):
        self._client = client
        self._chatgpt_reversed = None

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
        Create a chat completion with ChatGPT API.

        Args:
            model: The model to use (from AVAILABLE_MODELS)
            messages: List of message dictionaries with 'role' and 'content'
            max_tokens: Maximum number of tokens to generate
            stream: Whether to stream the response
            temperature: Sampling temperature (0-1)
            top_p: Nucleus sampling parameter (0-1)
            **kwargs: Additional parameters to pass to the API

        Returns:
            If stream=False, returns a ChatCompletion object
            If stream=True, returns a Generator yielding ChatCompletionChunk objects
        """
        # Initialize ChatGPTReversed if not already initialized
        if self._chatgpt_reversed is None:
            self._chatgpt_reversed = ChatGPTReversed(model=model)

        # Use streaming implementation if requested
        if stream:
            return self._create_streaming(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                timeout=timeout,
                proxies=proxies,
                **kwargs
            )
        
        # Otherwise use non-streaming implementation
        return self._create_non_streaming(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            timeout=timeout,
            proxies=proxies,
            **kwargs
        )

    def _create_streaming(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        timeout: Optional[int] = None,
        proxies: Optional[dict] = None,
        **kwargs: Any
    ) -> Generator[ChatCompletionChunk, None, None]:
        """Implementation for streaming chat completions."""
        try:
            # Generate request ID and timestamp
            request_id = str(uuid.uuid4())
            created_time = int(time.time())
            
            # Get the last user message
            last_user_message = None
            for msg in reversed(messages):
                if msg["role"] == "user":
                    last_user_message = msg["content"]
                    break
            
            if not last_user_message:
                raise ValueError("No user message found in the conversation")
            
            # Get the response from ChatGPT
            response = self._chatgpt_reversed.complete(last_user_message, model=model)
            
            # Split the response into chunks for streaming simulation
            chunk_size = 10  # Characters per chunk
            for i in range(0, len(response), chunk_size):
                chunk_text = response[i:i+chunk_size]
                
                # Create and yield a chunk
                delta = ChoiceDelta(content=chunk_text)
                choice = Choice(index=0, delta=delta, finish_reason=None)
                chunk = ChatCompletionChunk(
                    id=request_id,
                    choices=[choice],
                    created=created_time,
                    model=model
                )
                
                yield chunk
                
                # Add a small delay to simulate streaming
                time.sleep(0.05)
            
            # Final chunk with finish_reason
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
            print(f"{RED}Error during ChatGPT streaming request: {e}{RESET}")
            raise IOError(f"ChatGPT streaming request failed: {e}") from e

    def _create_non_streaming(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        timeout: Optional[int] = None,
        proxies: Optional[dict] = None,
        **kwargs: Any
    ) -> ChatCompletion:
        """Implementation for non-streaming chat completions."""
        try:
            # Generate request ID and timestamp
            request_id = str(uuid.uuid4())
            created_time = int(time.time())
            
            # Get the last user message
            last_user_message = None
            for msg in reversed(messages):
                if msg["role"] == "user":
                    last_user_message = msg["content"]
                    break
            
            if not last_user_message:
                raise ValueError("No user message found in the conversation")
            
            # Get the response from ChatGPT
            full_content = self._chatgpt_reversed.complete(last_user_message, model=model)
            
            # Create the completion message
            message = ChatCompletionMessage(
                role="assistant",
                content=full_content
            )
            
            # Create the choice
            choice = Choice(
                index=0,
                message=message,
                finish_reason="stop"
            )
            
            # Estimate token usage using count_tokens
            prompt_tokens = count_tokens([msg.get("content", "") for msg in messages])
            completion_tokens = count_tokens(full_content)
            usage = CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
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
            print(f"{RED}Error during ChatGPT non-stream request: {e}{RESET}")
            raise IOError(f"ChatGPT request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'ChatGPT'):
        self.completions = Completions(client)

class ChatGPT(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for ChatGPT API.

    Usage:
        client = ChatGPT()
        response = client.chat.completions.create(
            model="auto",
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print(response.choices[0].message.content)
    """

    def __init__(
        self,
        proxies: Optional[Dict[str, str]] = None
    ):
        """
        Initialize the ChatGPT client.
        
        Args:
            proxies: Optional proxy configuration dict, e.g. {"http": "http://proxy:8080", "https": "https://proxy:8080"}
        """
        super().__init__(proxies=proxies)
        # Initialize chat interface
        self.chat = Chat(self)

    @property
    def AVAILABLE_MODELS(self):
        return ChatGPTReversed.AVAILABLE_MODELS

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return ChatGPTReversed.AVAILABLE_MODELS
        return _ModelList()

if __name__ == "__main__":
    # Example usage
    client = ChatGPT()
    response = client.chat.completions.create(
        model="o4-mini-high",
        messages=[{"role": "user", "content": "How manr r in strawberry"}]
    )
    print(response.choices[0].message.content)
    print()