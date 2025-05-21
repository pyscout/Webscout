import json
import time
import uuid
import re
import cloudscraper
from datetime import datetime
from typing import List, Dict, Optional, Union, Generator, Any


# Import base classes and utility structures
from .base import OpenAICompatibleProvider, BaseChat, BaseCompletions
from .utils import (
    ChatCompletionChunk, ChatCompletion, Choice, ChoiceDelta,
    ChatCompletionMessage, CompletionUsage,
    format_prompt, get_system_prompt, get_last_user_message, count_tokens
)

# Import LitAgent for browser fingerprinting
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

# --- StandardInput Client ---

class Completions(BaseCompletions):
    def __init__(self, client: 'StandardInput'):
        self._client = client

    def create(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        stream: bool = False,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        **kwargs: Any
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        """Create a chat completion."""
        # Validate model
        if model not in self._client.AVAILABLE_MODELS and model not in self._client.MODEL_MAPPING.values():
            raise ValueError(f"Model {model} not supported. Choose from: {list(self._client.AVAILABLE_MODELS)}")

        # Map model name if needed
        internal_model = self._client.MODEL_MAPPING.get(model, model)

        # Extract reasoning flag from kwargs
        enable_reasoning = kwargs.get("enable_reasoning", False)

        # Prepare request
        request_id = str(uuid.uuid4())
        created_time = int(time.time())

        # Extract system message and user message using utility functions
        system_content = get_system_prompt(messages)
        # Format the prompt for debugging purposes
        formatted_prompt = format_prompt(messages, add_special_tokens=True, do_continue=True)
        # Uncomment the line below for debugging
        # print(f"Formatted prompt:\n{formatted_prompt}")

        # Prepare the request payload
        payload = {
            "id": request_id,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": formatted_prompt, "parts": [{"type": "text", "text": formatted_prompt}]}
            ],
            "modelId": internal_model,
            "enabledFeatures": ["reasoning"] if enable_reasoning or "reasoning" in internal_model else []
        }

        # Handle streaming vs non-streaming
        if stream:
            return self._stream_request(request_id, created_time, model, payload)
        else:
            return self._non_stream_request(request_id, created_time, model, payload)

    def _non_stream_request(
        self,
        request_id: str,
        created_time: int,
        model: str,
        payload: Dict[str, Any]
    ) -> ChatCompletion:
        """Handle non-streaming request."""
        try:
            # Make the request
            response = self._client.session.post(
                self._client.api_endpoint,
                cookies=self._client.cookies,
                json=payload,
                timeout=self._client.timeout
            )

            # Check for errors
            if response.status_code != 200:
                # Try to get response content for better error messages
                try:
                    error_content = response.text
                except:
                    error_content = "<could not read response content>"

                if response.status_code in [403, 429]:
                    print(f"Received status code {response.status_code}, refreshing identity...")
                    self._client._refresh_identity()
                    response = self._client.session.post(
                        self._client.api_endpoint,
                        cookies=self._client.cookies,
                        json=payload,
                        timeout=self._client.timeout
                    )
                    if not response.ok:
                        raise IOError(f"Failed to generate response after identity refresh - ({response.status_code}, {response.reason}) - {error_content}")
                    print("Identity refreshed successfully.")
                else:
                    raise IOError(f"Request failed with status code {response.status_code}. Response: {error_content}")

            # Process the response
            full_response = ""

            # Process the streaming response to get the full text
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    try:
                        # Extract content from the response
                        match = re.search(r'0:"(.*?)"', line)
                        if match:
                            content = match.group(1)
                            # Format the content to handle escape sequences
                            content = self._client.format_text(content)
                            full_response += content
                    except:
                        pass

            # Create the response objects
            message = ChatCompletionMessage(
                role="assistant",
                content=full_response
            )

            choice = Choice(
                index=0,
                message=message,
                finish_reason="stop"
            )

            # Estimate token usage (very rough estimate)
            prompt_tokens = count_tokens(str(payload)) * 2
            completion_tokens = count_tokens(full_response) * 2
            total_tokens = prompt_tokens + completion_tokens

            usage = CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
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
            print(f"Error during StandardInput non-stream request: {e}")
            raise IOError(f"StandardInput request failed: {e}") from e

    def _stream_request(
        self,
        request_id: str,
        created_time: int,
        model: str,
        payload: Dict[str, Any]
    ) -> Generator[ChatCompletionChunk, None, None]:
        """Handle streaming request."""
        try:
            # Make the request
            response = self._client.session.post(
                self._client.api_endpoint,
                cookies=self._client.cookies,
                json=payload,
                stream=True,
                timeout=self._client.timeout
            )

            # Check for errors
            if response.status_code != 200:
                # Try to get response content for better error messages
                try:
                    error_content = response.text
                except:
                    error_content = "<could not read response content>"

                if response.status_code in [403, 429]:
                    print(f"Received status code {response.status_code}, refreshing identity...")
                    self._client._refresh_identity()
                    response = self._client.session.post(
                        self._client.api_endpoint,
                        cookies=self._client.cookies,
                        json=payload,
                        stream=True,
                        timeout=self._client.timeout
                    )
                    if not response.ok:
                        raise IOError(f"Failed to generate response after identity refresh - ({response.status_code}, {response.reason}) - {error_content}")
                    print("Identity refreshed successfully.")
                else:
                    raise IOError(f"Request failed with status code {response.status_code}. Response: {error_content}")

            # Process the streaming response
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    try:
                        # Extract content from the response
                        match = re.search(r'0:"(.*?)"', line)
                        if match:
                            content = match.group(1)

                            # Format the content to handle escape sequences
                            content = self._client.format_text(content)

                            # Create the delta object
                            delta = ChoiceDelta(content=content)

                            # Create the choice object
                            choice = Choice(
                                index=0,
                                delta=delta,
                                finish_reason=None
                            )

                            # Create the chunk object
                            chunk = ChatCompletionChunk(
                                id=request_id,
                                choices=[choice],
                                created=created_time,
                                model=model
                            )

                            yield chunk
                    except:
                        pass

            # Send the final chunk with finish_reason
            final_choice = Choice(
                index=0,
                delta=ChoiceDelta(content=None),
                finish_reason="stop"
            )

            final_chunk = ChatCompletionChunk(
                id=request_id,
                choices=[final_choice],
                created=created_time,
                model=model
            )

            yield final_chunk

        except Exception as e:
            print(f"Error during StandardInput stream request: {e}")
            raise IOError(f"StandardInput request failed: {e}") from e

class Chat(BaseChat):
    def __init__(self, client: 'StandardInput'):
        self.completions = Completions(client)

class StandardInput(OpenAICompatibleProvider):
    """
    OpenAI-compatible client for StandardInput API.

    Usage:
        client = StandardInput()
        response = client.chat.completions.create(
            model="standard-quick",
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print(response.choices[0].message.content)
    """

    AVAILABLE_MODELS = [
        "standard-quick",
        "standard-reasoning",
    ]

    # Map external model names to internal model IDs
    MODEL_MAPPING = {
        "standard-quick": "quick",
        "standard-reasoning": "quick",  # Same model but with reasoning enabled
    }

    def __init__(
        self,
        timeout: int = 30,
        browser: str = "chrome"
    ):
        """
        Initialize the StandardInput client.

        Args:
            timeout: Request timeout in seconds.
            browser: Browser name for LitAgent to generate User-Agent.
        """
        self.timeout = timeout
        self.api_endpoint = "https://chat.standard-input.com/api/chat"

        # Initialize LitAgent for user agent generation
        self.agent = LitAgent()
        # Use fingerprinting to create a consistent browser identity
        self.fingerprint = self.agent.generate_fingerprint(browser)

        # Use the fingerprint for headers
        self.headers = {
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": self.fingerprint["accept_language"],
            "content-type": "application/json",
            "dnt": "1",
            "origin": "https://chat.standard-input.com",
            "referer": "https://chat.standard-input.com/",
            "sec-ch-ua": self.fingerprint["sec_ch_ua"] or '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": f'"{self.fingerprint["platform"]}"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "sec-gpc": "1",
            "user-agent": self.fingerprint["user_agent"],
        }

        # Default cookies - these should be updated for production use
        self.cookies = {
            "auth-chat": '''%7B%22user%22%3A%7B%22id%22%3A%2243a26ebd-7691-4a5a-8321-12aff017af86%22%2C%22email%22%3A%22iu511inmev%40illubd.com%22%2C%22accountId%22%3A%22057d78c9-06db-48eb-aeaa-0efdbaeb9446%22%2C%22provider%22%3A%22password%22%7D%2C%22tokens%22%3A%7B%22access%22%3A%22eyJhbGciOiJFUzI1NiIsImtpZCI6Ijg1NDhmZWY1LTk5MjYtNDk2Yi1hMjI2LTQ5OTExYjllYzU2NSIsInR5cCI6IkpXVCJ9.eyJtb2RlIjoiYWNjZXNzIiwidHlwZSI6InVzZXIiLCJwcm9wZXJ0aWVzIjp7ImlkIjoiNDNhMjZlYmQtNzY5MS00YTVhLTgzMzEtMTJhZmYwMTdhZjg2IiwiZW1haWwiOiJpdTUxMWlubWV2QGlsbHViZC5jb20iLCJhY2NvdW50SWQiOiIwNTdkNzhjOS0wNmRiLTQ4ZWItYWVhYS0wZWZkYmFlYjk0NDYiLCJwcm92aWRlciI6InBhc3N3b3JkIn0sImF1ZCI6InN0YW5kYXJkLWlucHV0LWlvcyIsImlzcyI6Imh0dHBzOi8vYXV0aC5zdGFuZGFyZC1pbnB1dC5jb20iLCJzdWIiOiJ1c2VyOjRmYWMzMTllZjA4MDRiZmMiLCJleHAiOjE3NDU0MDU5MDN9.d3VsEq-UCNsQWkiPlTVw7caS0wTXfCYe6yeFLeb4Ce6ZYTIFFn685SF-aKvLOxaYaq7Pyk4D2qr24riPVhxUWQ%22%2C%22refresh%22%3A%22user%3A4fac319ef0804bfc%3A3a757177-5507-4a36-9356-492f5ed06105%22%7D%7D''',
            "auth": '''%7B%22user%22%3A%7B%22id%22%3A%22c51e291f-8f44-439d-a38b-9ea147581a13%22%2C%22email%22%3A%22r6cigexlsb%40mrotzis.com%22%2C%22accountId%22%3A%22599fd4ce-04a2-40f6-a78f-d33d0059b77f%22%2C%22provider%22%3A%22password%22%7D%2C%22tokens%22%3A%7B%22access%22%3A%22eyJhbGciOiJFUzI1NiIsImtpZCI6Ijg1NDhmZWY1LTk5MjYtNDk2Yi1hMjI2LTQ5OTExYjllYzU2NSIsInR5cCI6IkpXVCJ9.eyJtb2RlIjoiYWNjZXNzIiwidHlwZSI6InVzZXIiLCJwcm9wZXJ0aWVzIjp7ImlkIjoiYzUxZTI5MWYtOGY0NC00MzlkLWEzOGItOWVhMTQ3NTgxYTEzIiwiZW1haWwiOiJyNmNpZ2V4bHNiQG1yb3R6aXMuY29tIiwiYWNjb3VudElkIjoiNTk5ZmQ0Y2UtMDRhMi00MGY2LWE3OGYtZDMzZDAwNTliNzdmIiwicHJvdmlkZXIiOiJwYXNzd29yZCJ9LCJhdWQiOiJzdGFuZGFyZC1pbnB1dC1pb3MiLCJpc3MiOiJodHRwczovL2F1dGguc3RhbmRhcmQtaW5wdXQuY29tIiwic3ViIjoidXNlcjo4Y2FmMjRkYzUxNDc4MmNkIiwiZXhwIjoxNzQ2NzI0MTU3fQ.a3970nBJkd8JoU-khRA2JlRMuYeJ7378QS4ZL446kOkDi35uTwuC4qGrWH9efk9GkFaVcWPtYeOJjRb7f2SeJA%22%2C%22refresh%22%3A%22user%3A8caf24dc514782cd%3A14e24386-8443-4df0-ae25-234ad59218ef%22%7D%7D''',
            "sidebar:state": "true",
            "ph_phc_f3wUUyCfmKlKtkc2pfT7OsdcW2mBEVGN2A87yEYbG3c_posthog": '''%7B%22distinct_id%22%3A%220195c7cc-ac8f-79ff-b901-e14a78fc2a67%22%2C%22%24sesid%22%3A%5B1744688627860%2C%220196377f-9f12-77e6-a9ea-0e9669423803%22%2C1744687832850%5D%2C%22%24initial_person_info%22%3A%7B%22r%22%3A%22%24direct%22%2C%22u%22%3A%22https%3A%2F%2Fstandard-input.com%2F%22%7D%7D'''
        }

        # Initialize session with cloudscraper for better handling of Cloudflare protection
        self.session = cloudscraper.create_scraper()
        self.session.headers.update(self.headers)

        # Initialize chat interface
        self.chat = Chat(self)

    def _refresh_identity(self, browser: str = None):
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
            "Sec-CH-UA": self.fingerprint["sec_ch_ua"] or self.headers["sec-ch-ua"],
            "Sec-CH-UA-Platform": f'"{self.fingerprint["platform"]}"',
            "User-Agent": self.fingerprint["user_agent"],
        })

        # Update session headers
        for header, value in self.headers.items():
            self.session.headers[header] = value

        return self.fingerprint

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

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()

