from curl_cffi.requests import Session
from curl_cffi import CurlError
from typing import Any, Dict, Optional, Generator, Union
import uuid
import json

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent

class QodoAI(Provider):
    """
    A class to interact with the Qodo AI API.
    """

    AVAILABLE_MODELS = [
        "gpt-4.1",
        "gpt-4o", 
        "o3",
        "o4-mini",
        "claude-4-sonnet",
        "gemini-2.5-pro",
        "grok-4"

    ]

    @staticmethod
    def _qodo_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        """Extracts content from Qodo stream JSON objects."""
        if isinstance(chunk, dict):
            data = chunk.get("data", {})
            if isinstance(data, dict):
                tool_args = data.get("tool_args", {})
                if isinstance(tool_args, dict):
                    return tool_args.get("content")
        return None

    def __init__(
        self,
        api_key: str = None,
        is_conversation: bool = True,
        max_tokens: int = 2049,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "claude-4-sonnet",
        browser: str = "chrome"
    ):
        """Initializes the Qodo AI API client."""
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")
            
        self.url = "https://api.cli.qodo.ai/v2/agentic/start-task"
        self.info_url = "https://api.cli.qodo.ai/v2/info/get-things"
        
        # Initialize LitAgent for user agent generation
        self.agent = LitAgent()
        self.fingerprint = self.agent.generate_fingerprint(browser)
        
        # Store API key
        self.api_key = api_key or "sk-dS7U-extxMWUxc8SbYYOuncqGUIE8-y2OY8oMCpu0eI-qnSUyH9CYWO_eAMpqwfMo7pXU3QNrclfZYMO0M6BJTM"
        
        # Generate session ID dynamically from API
        self.session_id = self._get_session_id()
        self.request_id = str(uuid.uuid4())
        
        # Use the fingerprint for headers
        self.headers = {
            "Accept": "text/plain",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": self.fingerprint["accept_language"],
            "Authorization": f"Bearer {self.api_key}",
            "Connection": "close",
            "Content-Type": "application/json",
            "host": "api.cli.qodo.ai",
            "Request-id": self.request_id,
            "User-Agent": self.fingerprint["user_agent"],
        }
        
        # Initialize curl_cffi Session
        self.session = Session()
        # Add Session-id to headers after getting it from API
        self.headers["Session-id"] = self.session_id
        self.session.headers.update(self.headers)
        self.session.proxies.update(proxies)

        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = {}
        self.model = model

        self.__available_optimizers = (
            method
            for method in dir(Optimizers)
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
        
        # Update headers with new fingerprint
        self.headers.update({
            "Accept-Language": self.fingerprint["accept_language"],
            "User-Agent": self.fingerprint["user_agent"],
        })
        
        # Update session headers
        for header, value in self.headers.items():
            self.session.headers[header] = value
        
        return self.fingerprint

    def _build_payload(self, prompt: str):
        """Build the payload for Qodo AI API."""
        return {
            "agent_type": "cli",
            "session_id": self.session_id,
            "user_data": {
                "extension_version": "0.7.2",
                "os_platform": "win32",
                "os_version": "v23.9.0",
                "editor_type": "cli"
            },
            "tools": {
                "web_search": [
                    {
                        "name": "web_search",
                        "description": "Searches the web and returns results based on the user's query (Powered by Nimble).",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "llm_description": {
                                    "default": "Searches the web and returns results based on the user's query.",
                                    "title": "Llm Description",
                                    "type": "string"
                                },
                                "query": {
                                    "description": "The search query to execute",
                                    "title": "Query",
                                    "type": "string"
                                }
                            },
                            "required": ["query"],
                            "title": "NimbleWebSearch"
                        },
                        "be_tool": True,
                        "autoApproved": True
                    },
                    {
                        "name": "web_fetch",
                        "description": "Fetches content from a given URL (Powered by Nimble).",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "llm_description": {
                                    "default": "Fetches content from a given URL.",
                                    "title": "Llm Description",
                                    "type": "string"
                                },
                                "url": {
                                    "description": "The URL to fetch content from",
                                    "title": "Url",
                                    "type": "string"
                                }
                            },
                            "required": ["url"],
                            "title": "NimbleWebFetch"
                        },
                        "be_tool": True,
                        "autoApproved": True
                    }
                ]
            },
            # "projects_root_path": ["C:\\Users\\koula"],
            # "cwd": "C:\\Users\\koula",
            "user_request": prompt,
            "execution_strategy": "act",
            "custom_model": self.model,
            "stream": True
        }

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator]:
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise Exception(f"Optimizer is not one of {self.__available_optimizers}")

        payload = self._build_payload(conversation_prompt)
        payload["stream"] = stream


        def for_stream():
            try:
                response = self.session.post(
                    self.url,
                    json=payload,
                    stream=True,
                    timeout=self.timeout,
                    impersonate=self.fingerprint.get("browser_type", "chrome110")
                )
                # Check for internal server error with session ID in the response
                if response.status_code == 500 and response.text and "Internal server error, session ID:" in response.text:
                    # Switch to continue-task endpoint and retry
                    self.url = "https://api.cli.qodo.ai/v2/agentic/continue-task"
                    response = self.session.post(
                        self.url,
                        json=payload,
                        stream=True,
                        timeout=self.timeout,
                        impersonate=self.fingerprint.get("browser_type", "chrome110")
                    )
                if response.status_code == 401:
                    raise exceptions.FailedToGenerateResponseError(
                        "Invalid API key. You need to provide your own API key.\n"
                        "Usage: QodoAI(api_key='your_api_key_here')\n"
                        "To get an API key, install Qodo CLI via: https://docs.qodo.ai/qodo-documentation/qodo-gen-cli/getting-started/setup-and-quickstart"
                    )
                elif response.status_code != 200:
                    raise exceptions.FailedToGenerateResponseError(f"HTTP {response.status_code}: {response.text}")

                streaming_text = ""
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None),
                    intro_value="",
                    to_json=True,
                    skip_markers=["[DONE]"],
                    content_extractor=self._qodo_extractor,
                    yield_raw_on_error=True,
                    raw=raw
                )
                for content_chunk in processed_stream:
                    if content_chunk:
                        yield content_chunk if raw else {"text": content_chunk}
                        if not raw:
                            streaming_text += content_chunk

                self.last_response = {"text": streaming_text}
                self.conversation.update_chat_history(prompt, streaming_text)
            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}")
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"An unexpected error occurred ({type(e).__name__}): {e}")

        def for_non_stream():
            try:
                payload["stream"] = False
                response = self.session.post(
                    self.url,
                    json=payload,
                    timeout=self.timeout,
                    impersonate=self.fingerprint.get("browser_type", "chrome110")
                )
                # Check for internal server error with session ID in the response
                if response.status_code == 500 and response.text and "Internal server error, session ID:" in response.text:
                    self.url = "https://api.cli.qodo.ai/v2/agentic/continue-task"
                    response = self.session.post(
                        self.url,
                        json=payload,
                        timeout=self.timeout,
                        impersonate=self.fingerprint.get("browser_type", "chrome110")
                    )
                if response.status_code == 401:
                    raise exceptions.FailedToGenerateResponseError(
                        "Invalid API key. You need to provide your own API key.\n"
                        "Usage: QodoAI(api_key='your_api_key_here')\n"
                        "To get an API key, install Qodo CLI via: https://docs.qodo.ai/qodo-documentation/qodo-gen-cli/getting-started/setup-and-quickstart"
                    )
                elif response.status_code != 200:
                    raise exceptions.FailedToGenerateResponseError(f"HTTP {response.status_code}: {response.text}")

                response_text = response.text
                processed_stream = sanitize_stream(
                    data=response_text.splitlines(),
                    intro_value=None,
                    to_json=True,
                    content_extractor=self._qodo_extractor,
                    yield_raw_on_error=True,
                    raw=raw
                )
                full_response = ""
                for content in processed_stream:
                    if content:
                        full_response += content

                self.last_response = {"text": full_response}
                self.conversation.update_chat_history(prompt, full_response)
                return {"text": full_response} if not raw else full_response
            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}")
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed ({type(e).__name__}): {e}")

        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        raw: bool = False,
    ) -> Union[str, Generator[str, None, None]]:
        def for_stream():
            for response in self.ask(
                prompt, True, raw=raw, optimizer=optimizer, conversationally=conversationally
            ):
                if raw:
                    yield response
                else:
                    yield response.get("text", "")

        def for_non_stream():
            result = self.ask(
                prompt, False, raw=raw, optimizer=optimizer, conversationally=conversationally
            )
            if raw:
                return result
            else:
                return self.get_message(result)

        return for_stream() if stream else for_non_stream()

    def get_message(self, response: dict) -> str:
        assert isinstance(response, dict), "Response should be of dict data-type only"
        text = response.get("text", "")
        return text.replace('\\n', '\n').replace('\\n\\n', '\n\n')

    def _get_session_id(self) -> str:
        """Get session ID from Qodo API."""
        try:
            # Create temporary session for the info request
            temp_session = Session()
            temp_headers = {
                "Accept": "text/plain",
                "Accept-Encoding": "gzip, deflate, br",
                "Authorization": f"Bearer {self.api_key}",
                "Connection": "close",
                "Content-Type": "application/json",
                "host": "api.cli.qodo.ai",
                "Request-id": str(uuid.uuid4()),
                "User-Agent": self.fingerprint["user_agent"] if hasattr(self, 'fingerprint') else "axios/1.10.0",
            }
            temp_session.headers.update(temp_headers)
            
            response = temp_session.get(
                self.info_url,
                timeout=self.timeout if hasattr(self, 'timeout') else 30,
                impersonate="chrome110"
            )
            
            if response.status_code == 200:
                data = response.json()
                session_id = data.get("session-id")
                if session_id:
                    return session_id
            elif response.status_code == 401:
                # API key is invalid
                raise exceptions.FailedToGenerateResponseError(
                    "Invalid API key. You need to provide your own API key.\n"
                    "Usage: QodoAI(api_key='your_api_key_here')\n"
                    "To get an API key, install Qodo CLI via: https://docs.qodo.ai/qodo-documentation/qodo-gen-cli/getting-started/setup-and-quickstart"
                )
            else:
                # Other HTTP errors
                raise exceptions.FailedToGenerateResponseError(
                    f"Failed to authenticate with Qodo API (HTTP {response.status_code}). "
                    "You may need to provide your own API key.\n"
                    "Usage: QodoAI(api_key='your_api_key_here')\n"
                    "To get an API key, install Qodo CLI via: https://docs.qodo.ai/qodo-documentation/qodo-gen-cli/getting-started/setup-and-quickstart"
                )
                    
            # Fallback to generated session ID if API call fails
            from datetime import datetime
            today = datetime.now().strftime("%Y%m%d")
            return f"{today}-{str(uuid.uuid4())}"
            
        except exceptions.FailedToGenerateResponseError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            # For other errors, show the API key message
            raise exceptions.FailedToGenerateResponseError(
                f"Failed to connect to Qodo API: {e}\n"
                "You may need to provide your own API key.\n"
                "Usage: QodoAI(api_key='your_api_key_here')\n"
                "To get an API key, install Qodo CLI via: https://docs.qodo.ai/qodo-documentation/qodo-gen-cli/getting-started/setup-and-quickstart"
            )

    def refresh_session(self):
        """
        Refreshes the session ID by calling the Qodo API.
        
        Returns:
            str: The new session ID
        """
        old_session_id = self.session_id
        self.session_id = self._get_session_id()
        
        # Update headers with new session ID
        self.headers["Session-id"] = self.session_id
        self.session.headers["Session-id"] = self.session_id
        
        return self.session_id

    def get_available_models(self) -> Dict[str, Any]:
        """
        Get available models and info from Qodo API.
        
        Returns:
            Dict containing models, default_model, version, and session info
        """
        try:
            response = self.session.get(
                self.info_url,
                timeout=self.timeout,
                impersonate=self.fingerprint.get("browser_type", "chrome110")
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                raise exceptions.FailedToGenerateResponseError(
                    "Invalid API key. You need to provide your own API key.\n"
                    "Usage: QodoAI(api_key='your_api_key_here')\n"
                    "To get an API key, install Qodo CLI via: https://docs.qodo.ai/qodo-documentation/qodo-gen-cli/getting-started/setup-and-quickstart"
                )
            else:
                raise exceptions.FailedToGenerateResponseError(f"Failed to get models: HTTP {response.status_code}")
                
        except CurlError as e:
            raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}")
        except Exception as e:
            raise exceptions.FailedToGenerateResponseError(f"Failed to get models ({type(e).__name__}): {e}")


if __name__ == "__main__":
    ai = QodoAI() # u will need to give your API key here to get api install qodo cli via https://docs.qodo.ai/qodo-documentation/qodo-gen-cli/getting-started/setup-and-quickstart
    response = ai.chat("write a poem about india", raw=False, stream=True) 
    for chunk in response:
        print(chunk, end='', flush=True)