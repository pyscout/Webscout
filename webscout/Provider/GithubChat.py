from curl_cffi import CurlError
from curl_cffi.requests import Session
import json
import time
from typing import Any, Dict, Optional, Union, Generator
from webscout.AIutel import Conversation
from webscout.AIutel import Optimizers
from webscout.AIutel import AwesomePrompts, sanitize_stream # Import sanitize_stream
from webscout.AIbase import Provider 
from webscout import exceptions
from webscout.litagent import LitAgent

class GithubChat(Provider):
    """
    A class to interact with the GitHub Copilot Chat API.
    Uses cookies for authentication and supports streaming responses.
    """
    required_auth = True
    # Available models
    AVAILABLE_MODELS = [
        "gpt-4o",
        "gpt-5",
        "gpt-5-mini",
        "o3-mini", 
        "o1", 
        "claude-3.5-sonnet",
        "claude-3.7-sonnet",
        "claude-3.7-sonnet-thought",
        "claude-sonnet-4",
        "claude-sonnet-4.5",
        "gemini-2.0-flash-001",
        "gemini-2.5-pro",
        "gpt-4.1",
        "o4-mini"

    ]
    
    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 2000,
        timeout: int = 60,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "gpt-4o",
        cookie_path: str = "cookies.json"
    ):
        """Initialize the GithubChat client."""
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {', '.join(self.AVAILABLE_MODELS)}")
            
        self.url = "https://github.com/copilot"
        self.api_url = "https://api.individual.githubcopilot.com"
        self.cookie_path = cookie_path
        self.session = Session() # Use curl_cffi Session
        self.session.proxies.update(proxies)
        
        # Load cookies for authentication
        self.cookies = self.load_cookies()
        
        # Set up headers for all requests
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": LitAgent().random(),
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.5",
            "Origin": "https://github.com",
            "Referer": "https://github.com/copilot",
            "GitHub-Verified-Fetch": "true",
            "X-Requested-With": "XMLHttpRequest",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        
        # Apply cookies to session
        if self.cookies:
            self.session.cookies.update(self.cookies)
        
        # Set default model
        self.model = model
        
        # Provider settings
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = {}
        
        # Available optimizers
        self.__available_optimizers = (
            method
            for method in dir(Optimizers)
            if callable(getattr(Optimizers, method)) and not method.startswith("__")
        )
        
        # Set up conversation
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
        
        # Store conversation data
        self._conversation_id = None
        self._access_token = None

    def load_cookies(self):
        """Load cookies from a JSON file"""
        try:
            with open(self.cookie_path, 'r') as f:
                cookies_data = json.load(f)
                
            # Convert the cookie list to a dictionary format for requests
            cookies = {}
            for cookie in cookies_data:
                # Only include cookies that are not expired and have a name and value
                if 'name' in cookie and 'value':
                    # Check if the cookie hasn't expired
                    if 'expirationDate' not in cookie or cookie['expirationDate'] > time.time():
                        cookies[cookie['name']] = cookie['value']
            
            return cookies
        except Exception:
            return {}

    def get_access_token(self):
        """Get GitHub Copilot access token."""
        if self._access_token:
            return self._access_token
            
        url = "https://github.com/github-copilot/chat/token"
        
        try:
            response = self.session.post(url, headers=self.headers)
            
            if response.status_code == 401:
                raise exceptions.AuthenticationError("Authentication failed. Please check your cookies.")
                
            if response.status_code != 200:
                raise exceptions.FailedToGenerateResponseError(f"Failed to get access token: {response.status_code}")
                
            data = response.json()
            self._access_token = data.get("token")
            
            if not self._access_token:
                raise exceptions.FailedToGenerateResponseError("Failed to extract access token from response")
                
            return self._access_token
            
        except:
            pass

    @staticmethod
    def _github_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        """Extracts content from GitHub Copilot stream JSON objects."""
        if isinstance(chunk, dict) and chunk.get("type") == "content":
            return chunk.get("body")
        return None

    def create_conversation(self):
        """Create a new conversation with GitHub Copilot."""
        if self._conversation_id:
            return self._conversation_id
            
        access_token = self.get_access_token()
        url = f"{self.api_url}/github/chat/threads"
        
        headers = self.headers.copy()
        headers["Authorization"] = f"GitHub-Bearer {access_token}"
        
        try:
            response = self.session.post(
                url, headers=headers,
                impersonate="chrome120" # Add impersonate
            )
            
            if response.status_code == 401:
                # Token might be expired, try refreshing
                self._access_token = None
                access_token = self.get_access_token()
                headers["Authorization"] = f"GitHub-Bearer {access_token}"
                response = self.session.post(url, headers=headers)
            
            # Check status after potential retry
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            if response.status_code not in [200, 201]:
                raise exceptions.FailedToGenerateResponseError(f"Failed to create conversation: {response.status_code}")
                
            data = response.json()
            self._conversation_id = data.get("thread_id")
            
            if not self._conversation_id:
                raise exceptions.FailedToGenerateResponseError("Failed to extract conversation ID from response")
                
            return self._conversation_id
        except (CurlError, exceptions.FailedToGenerateResponseError, Exception) as e: # Catch CurlError and others
            raise exceptions.FailedToGenerateResponseError(f"Failed to create conversation: {str(e)}")
    
    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator]:
        """Send a message to the GitHub Copilot Chat API"""
        
        # Apply optimizers if specified
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise Exception(f"Optimizer is not one of {self.__available_optimizers}")
        
        # Make sure we have a conversation ID
        try:
            conversation_id = self.create_conversation()
        except exceptions.FailedToGenerateResponseError as e:
            raise exceptions.FailedToGenerateResponseError(f"Failed to create conversation: {e}")
            
        access_token = self.get_access_token()
        
        url = f"{self.api_url}/github/chat/threads/{conversation_id}/messages"
        
        # Update headers for this specific request
        headers = self.headers.copy()
        headers["Authorization"] = f"GitHub-Bearer {access_token}"
        
        # Prepare the request payload
        request_data = {
            "content": conversation_prompt,
            "intent": "conversation",
            "references": [],
            "context": [],
            "currentURL": f"https://github.com/copilot/c/{conversation_id}",
            "streaming": True,
            "confirmations": [],
            "customInstructions": [],
            "model": self.model,
            "mode": "immersive"
        }
        
        streaming_text = "" # Initialize for history update
        def for_stream():
            nonlocal streaming_text # Allow modification of outer scope variable
            try:
                response = self.session.post(
                    url, 
                    json=request_data,
                    headers=headers, # Use updated headers with Authorization
                    stream=True,
                    timeout=self.timeout
                )
                
                if response.status_code == 401:
                    # Token might be expired, try refreshing
                    self._access_token = None
                    access_token = self.get_access_token()
                    headers["Authorization"] = f"GitHub-Bearer {access_token}"
                    response = self.session.post(
                        url,
                        json=request_data, # Use original payload
                        headers=headers,
                        stream=True,
                        timeout=self.timeout
                    )
                
                # If still not successful, raise exception
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                
                # Process the streaming response
                # Use sanitize_stream
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None), # Pass byte iterator
                    intro_value="data:",
                    to_json=True,     # Stream sends JSON
                    skip_markers=["[DONE]"],
                    content_extractor=self._github_extractor, # Use the specific extractor
                    yield_raw_on_error=False # Skip non-JSON lines or lines where extractor fails
                )

                for content_chunk in processed_stream:
                    # content_chunk is the string extracted by _github_extractor
                    if content_chunk and isinstance(content_chunk, str):
                        streaming_text += content_chunk
                        resp = {"text": content_chunk}
                        yield resp if not raw else content_chunk
                
            except Exception as e:
                if isinstance(e, CurlError): # Check for CurlError
                    if hasattr(e, 'response') and e.response is not None:
                        status_code = e.response.status_code 
                        if status_code == 401:
                            raise exceptions.AuthenticationError("Authentication failed. Please check your cookies.")
                
                # If anything else fails
                raise exceptions.FailedToGenerateResponseError(f"Request failed: {str(e)}")
            finally:
                # Update history after stream finishes or fails (if text was generated)
                if streaming_text:
                    self.last_response = {"text": streaming_text}
                    self.conversation.update_chat_history(prompt, streaming_text)

        def for_non_stream():
            response_text = ""
            for response in for_stream():
                if "text" in response:
                    response_text += response["text"]
            # self.last_response and history are updated in for_stream's finally block
            return self.last_response

        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[str, Generator]:
        """Generate a response to a prompt"""
        def for_stream():
            for response in self.ask(
                prompt, True, optimizer=optimizer, conversationally=conversationally
            ):
                yield self.get_message(response)
                
        def for_non_stream():
            return self.get_message(
                self.ask(
                    prompt, False, optimizer=optimizer, conversationally=conversationally
                )
            )
            
        return for_stream() if stream else for_non_stream()

    def get_message(self, response: dict) -> str:
        """Extract message text from response"""
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response.get("text", "")

if __name__ == "__main__":
    # Simple test code
    from rich import print
    
    try:
        ai = GithubChat("cookies.json")
        response = ai.chat("Python code to count r in strawberry", stream=True)
        for chunk in response:
            print(chunk, end="", flush=True)
        print()
    except Exception as e:
        print(f"An error occurred: {e}")
