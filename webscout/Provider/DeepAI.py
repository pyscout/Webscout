from curl_cffi.requests import Session
from curl_cffi import CurlError
import json
from typing import Any, Dict, List, Optional, Union, Iterator

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent


class DeepAI(Provider):
    """
    DeepAI Chat Provider

    A provider for DeepAI's chat functionality, supporting both streaming and non-streaming responses.
    Structured similarly to other providers like DeepInfra and X0GPT.
    """
    required_auth = True
    AVAILABLE_MODELS = [
        "standard", 
        "genius", 
        "online",
        "supergenius",
        "onlinegenius",
        "deepseek-v3.2",
        "gemini-2.5-flash-lite",
        "qwen3-30b-a3b",
        "gpt-5-nano",
        "gpt-oss-120b",
        "gpt-5-chat-latest",
        "claude-opus-4-1",
        "llama-4-scout",
        "claude-4.5-sonnet",
        "deepseek-v3.1-terminus",
        "llama-3.3-70b-instruct",
        "grok-4",
        "claude-sonnet-4",
        "qwen3-coder",
        "gpt-5",
        "kimi-k2-0905",
        "claude-opus-4",
        "gpt-5-mini",
        "gemini-2.5-pro",
        "grok-code-fast-1",
        "gpt-4.1",

    ]

    def __init__(
        self,
        api_key: str = "tryit-53926507126-2c8a2543c7b5638ca6b92b6e53ef2d2b",
        timeout: int = 30,
        proxies: Optional[Dict[str, str]] = None,
        model: str = "standard",
        chat_style: str = "chat",
        enabled_tools: Optional[List[str]] = None,
        is_conversation: bool = True,
        max_tokens: int = 2048,
        intro: Optional[str] = None,
        filepath: Optional[str] = None,
        update_file: bool = True,
        history_offset: int = 10250,
        act: Optional[str] = None,
        system_prompt: str = "You are a helpful assistant.",
        browser: str = "chrome",
        **kwargs
    ):
        """
        Initialize the DeepAI provider.

        Args:
            api_key: API key for authentication (trial key provided by default)
            timeout: Request timeout in seconds
            proxies: Proxy configuration
            model: Model to use (default: "standard")
            chat_style: Chat style (default: "chat")
            enabled_tools: List of enabled tools (default: ["image_generator"])
            is_conversation: Whether to maintain conversation history
            max_tokens: Maximum tokens for conversation
            intro: Introduction prompt
            filepath: Path to conversation history file
            update_file: Whether to update history file
            history_offset: History offset for truncation
            act: Act prompt from AwesomePrompts
            system_prompt: System prompt for the AI
            browser: Browser type for fingerprinting
            **kwargs: Additional arguments
        """
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        self.url = "https://api.deepai.org/hacking_is_a_serious_crime"
        self.api_key = api_key
        self.proxies = proxies or {}
        self.model = model
        self.chat_style = chat_style
        self.enabled_tools = enabled_tools or ["image_generator"]
        self.system_prompt = system_prompt
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = {}

        # LitAgent for fingerprinting
        self.agent = LitAgent()
        self.fingerprint = self.agent.generate_fingerprint(browser)

        # Setup headers similar to other providers
        self.headers = {
            "User-Agent": self.fingerprint.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
            "Accept": "*/*",
            "Accept-Language": self.fingerprint.get("accept_language", "en-US,en;q=0.9"),
            "Origin": "https://deepai.org",
            "Referer": "https://deepai.org/",
            "Sec-CH-UA": self.fingerprint.get("sec_ch_ua", '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'),
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": f'"{self.fingerprint.get("platform", "Windows")}"',
            "api-key": self.api_key
        }

        # Setup session
        self.session = Session()
        self.session.headers.update(self.headers)
        self.session.proxies = self.proxies

        # Optimizers
        self.__available_optimizers = (
            method
            for method in dir(Optimizers)
            if callable(getattr(Optimizers, method)) and not method.startswith("__")
        )

        # Conversation setup similar to other providers
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

    def refresh_identity(self, browser: str = None):
        """
        Refreshes the browser identity fingerprint.

        Args:
            browser: Specific browser to use for the new fingerprint
        """
        browser = browser or self.fingerprint.get("browser_type", "chrome")
        self.fingerprint = self.agent.generate_fingerprint(browser)

        # Update relevant headers
        self.headers.update({
            "User-Agent": self.fingerprint.get("user_agent"),
            "Accept-Language": self.fingerprint.get("accept_language"),
            "Sec-CH-UA": self.fingerprint.get("sec_ch_ua"),
            "Sec-CH-UA-Platform": f'"{self.fingerprint.get("platform")}"',
        })

        self.session.headers.update(self.headers)
        return self.fingerprint

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: Optional[str] = None,
        conversationally: bool = False,
        **kwargs
    ) -> Union[Dict[str, Any], Iterator[Dict[str, Any]]]:
        """
        Send a prompt to DeepAI and get the response.

        Args:
            prompt: The prompt to send
            stream: Whether to stream the response (fake streaming: yields full response in one chunk)
            raw: Whether to return raw response
            optimizer: Optimizer to use
            conversationally: Whether to apply optimizer to full conversation
            **kwargs: Additional arguments

        Returns:
            Response dictionary with the AI response or generator for streaming
        """
        # Generate conversation prompt similar to other providers
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)

        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise Exception(f"Optimizer is not one of {list(self.__available_optimizers)}")

        # Prepare form data
        # Use conversation_prompt as user content in chatHistory
        chat_history = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": conversation_prompt}
        ]
        data = {
            "chat_style": self.chat_style,
            "chatHistory": json.dumps(chat_history),
            "model": self.model,
            "hacker_is_stinky": "very_stinky",
            "enabled_tools": json.dumps(self.enabled_tools)
        }

        # Always perform non-streaming request
        try:
            # Make request with curl_cffi
            response = self.session.post(
                self.url,
                data=data,
                timeout=self.timeout,
                impersonate="chrome110"
            )
            response.raise_for_status()

            # Get response text
            result = response.text.strip()

            # Update last response and conversation history
            self.last_response = {"text": result}
            self.conversation.update_chat_history(prompt, result)

            if stream:
                # Fake streaming: yield the full response in one chunk
                if raw:
                    yield result
                else:
                    yield self.last_response
            else:
                return self.last_response if not raw else result

        except CurlError as e:
            raise exceptions.FailedToGenerateResponseError(f"DeepAI API request failed (CurlError): {str(e)}")
        except Exception as e:
            raise exceptions.FailedToGenerateResponseError(f"DeepAI API request failed ({type(e).__name__}): {str(e)}")

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: Optional[str] = None,
        conversationally: bool = False,
        raw: bool = False,
        **kwargs
    ) -> Union[str, Iterator[str]]:
        """
        Send a chat message to DeepAI and get the response.

        Args:
            prompt: The prompt to send
            stream: Whether to stream the response (fake streaming: yields full response in one chunk)
            optimizer: Optimizer to use
            conversationally: Whether to apply optimizer to full conversation
            raw: Whether to return raw response
            **kwargs: Additional arguments

        Returns:
            The AI response as a string or generator for streaming
        """
        if stream:
            for resp in self.ask(
                prompt=prompt,
                stream=True,
                raw=raw,
                optimizer=optimizer,
                conversationally=conversationally,
                **kwargs
            ):
                if raw:
                    yield resp
                else:
                    yield self.get_message(resp)
        else:
            response = self.ask(
                prompt=prompt,
                stream=False,
                raw=raw,
                optimizer=optimizer,
                conversationally=conversationally,
                **kwargs
            )
            if raw:
                return response
            else:
                return self.get_message(response)

    def get_message(self, response: Union[Dict[str, Any], str]) -> str:
        """
        Extract the message from the response.

        Args:
            response: Response dictionary from ask method or str if raw

        Returns:
            The message text
        """
        if isinstance(response, dict):
            return response.get("text", "")
        elif isinstance(response, str):
            return response
        else:
            raise ValueError(f"Unexpected response type: {type(response)}")

    @classmethod
    def get_models(cls) -> List[str]:
        """
        Get available models.

        Returns:
            List of available model names
        """
        return cls.AVAILABLE_MODELS

    @classmethod
    def get_chat_styles(cls) -> List[str]:
        """
        Get available chat styles.

        Returns:
            List of available chat styles
        """
        return ["chat"]


if __name__ == "__main__":
    # Test similar to other providers, using stream=True for consistency
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)

    for model in DeepAI.AVAILABLE_MODELS:
        try:
            test_ai = DeepAI(model=model, timeout=60)
            response = test_ai.chat("Say 'Hello' in one word", stream=True)
            response_text = ""
            for chunk in response:
                response_text += chunk

            if response_text and len(response_text.strip()) > 0:
                status = "✓"
                # Clean and truncate response
                clean_text = response_text.strip().encode('utf-8', errors='ignore').decode('utf-8')
                display_text = clean_text[:50] + "..." if len(clean_text) > 50 else clean_text
            else:
                status = "✗"
                display_text = "Empty or invalid response"
            print(f"{model:<50} {status:<10} {display_text}")
        except Exception as e:
            print(f"{model:<50} {'✗':<10} {str(e)}")