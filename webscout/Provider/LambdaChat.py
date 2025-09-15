from curl_cffi.requests import Session
from curl_cffi import CurlError
import json
import random
import uuid
from typing import Any, Dict, Optional, Union, Generator

from webscout.AIutel import Conversation, sanitize_stream
from webscout.AIbase import Provider # Import sanitize_stream
from webscout import exceptions
from webscout.litagent import LitAgent

class LambdaChat(Provider):
    """
    A class to interact with the Lambda Chat API.
    Supports streaming responses.
    """
    url = "https://lambda.chat"
    required_auth = False
    AVAILABLE_MODELS = [
        "deepseek-llama3.3-70b",
        "apriel-5b-instruct",
        "deepseek-r1",
        "deepseek-v3-0324",
        "deepseek-r1-0528",
        "hermes-3-llama-3.1-405b-fp8",
        "llama3.1-nemotron-70b-instruct",
        "lfm-40b",
        "llama3.3-70b-instruct-fp8",
        "qwen25-coder-32b-instruct",
        "qwen3-32b-fp8",
        "llama-4-maverick-70b-128e-instruct-fp8",
        "llama-4-scout-17b-16e-instruct"

    ]
    
    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 2000, # Note: max_tokens is not used by this API
        timeout: int = 60,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        model: str = "deepseek-llama3.3-70b",
        assistantId: str = None, # Note: assistantId is not used by this API
        system_prompt: str = "You are a helpful assistant. Please answer the following question.", # Note: system_prompt is not used by this API
    ):
        """Initialize the LambdaChat client."""
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")
            
        self.model = model
        # Initialize curl_cffi Session
        self.session = Session()
        self.assistantId = assistantId
        self.system_prompt = system_prompt
        
        # Set up headers for all requests
        self.headers = {
            "Content-Type": "application/json", # Keep Content-Type for JSON posts
            "Accept": "*/*", # Keep Accept
            # "User-Agent": LitAgent().random(), # Removed, handled by impersonate
            "Accept-Language": "en-US,en;q=0.9", # Keep Accept-Language
            "Origin": self.url, # Keep Origin
            "Referer": f"{self.url}/", # Keep Referer (will be updated per request)
            # "Sec-Ch-Ua": "\"Chromium\";v=\"120\"", # Removed, handled by impersonate
            # "Sec-Ch-Ua-Mobile": "?0", # Removed, handled by impersonate
            # "Sec-Ch-Ua-Platform": "\"Windows\"", # Removed, handled by impersonate
            "Sec-Fetch-Dest": "empty", # Keep Sec-Fetch-* headers
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "DNT": "1", # Keep DNT
            "Priority": "u=1, i" # Keep Priority
        }
        
        # Provider settings
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = {}

        # Initialize conversation history
        self.conversation = Conversation(is_conversation, max_tokens, filepath, update_file)
        
        # Store conversation data for different models
        self._conversation_data = {}

        # Update curl_cffi session headers and proxies
        self.session.headers.update(self.headers)
        self.session.proxies = proxies # Assign proxies directly

    def create_conversation(self, model: str):
        """Create a new conversation with the specified model, using updated headers and cookies."""
        url = f"{self.url}/conversation"
        payload = {
            "model": model,
            "preprompt": self.system_prompt
        }

        # Update headers for this specific request
        headers = self.headers.copy()
        headers["Referer"] = f"{self.url}/"
        # Add browser-like headers for best compatibility
        headers["Accept-Encoding"] = "gzip, deflate, br, zstd"
        headers["Accept-Language"] = "en-US,en;q=0.9,en-IN;q=0.8"
        headers["Sec-GPC"] = "1"
        headers["Sec-Ch-Ua"] = '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"'
        headers["Sec-Ch-Ua-Mobile"] = "?0"
        headers["Sec-Ch-Ua-Platform"] = '"Windows"'
        headers["User-Agent"] = LitAgent().random() # Use LitAgent for User-Agent
        headers["Origin"] = self.url
        # cookies are handled by curl_cffi session automatically

        try:
            response = self.session.post(
                url,
                json=payload,
                headers=headers,
                impersonate="chrome110"
            )
            if response.status_code == 401:
                raise exceptions.AuthenticationError("Authentication failed.")
            if response.status_code != 200:
                return None
            data = response.json()
            conversation_id = data.get("conversationId")
            if model not in self._conversation_data:
                self._conversation_data[model] = {
                    "conversationId": conversation_id,
                    "messageId": str(uuid.uuid4())
                }
            return conversation_id
        except CurlError:
            return None
        except Exception:
            return None
    
    def fetch_message_id(self, conversation_id: str) -> str:
        """Fetch the latest message ID for a conversation."""
        try:
            url = f"{self.url}/conversation/{conversation_id}/__data.json?x-sveltekit-invalidated=11"
            response = self.session.get(
                url, 
                headers=self.headers, # Use base headers
                impersonate="chrome110" # Use a common impersonation profile
            )
            response.raise_for_status()
            
            # Parse the JSON data from the response
            json_data = None
            for line in response.text.split('\n'):
                if line.strip():
                    try:
                        parsed = json.loads(line)
                        if isinstance(parsed, dict) and "nodes" in parsed:
                            json_data = parsed
                            break
                    except json.JSONDecodeError:
                        continue
            
            if not json_data:
                # Fall back to a UUID if we can't parse the response
                return str(uuid.uuid4())
            
            # Extract message ID using the same pattern as in the example
            if json_data.get("nodes", []) and json_data["nodes"][-1].get("type") == "error":
                return str(uuid.uuid4())
                
            data = json_data["nodes"][1]["data"]
            keys = data[data[0]["messages"]]
            message_keys = data[keys[-1]]
            message_id = data[message_keys["id"]]
            
            return message_id
            
        except CurlError: # Catch CurlError
            return str(uuid.uuid4()) # Fallback on CurlError
        except Exception: # Catch other potential exceptions
            # Fall back to a UUID if there's an error
            return str(uuid.uuid4())
    
    def generate_boundary(self):
        """Generate a random boundary for multipart/form-data requests"""
        boundary_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        boundary = "----WebKitFormBoundary"
        boundary += "".join(random.choice(boundary_chars) for _ in range(16))
        return boundary
    
    @staticmethod
    def _lambdachat_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[str]:
        """Extracts content from LambdaChat stream JSON objects."""
        if not isinstance(chunk, dict) or "type" not in chunk:
            return None

        reasoning_text = ""
        if chunk["type"] == "stream" and "token" in chunk:
            return chunk["token"].replace("\u0000", "")
        # elif chunk["type"] == "finalAnswer":
        #     return chunk.get("text")
        elif chunk["type"] == "reasoning" and chunk.get("subtype") == "stream" and "token" in chunk:
            # Prepend reasoning with <think> tags? Or handle separately? For now, just return token.
            return chunk["token"] # Or potentially format as f"<think>{chunk['token']}</think>"
        return None
    
    def ask(
        self,
        prompt: str,
        stream: bool = False, # API supports streaming
        raw: bool = False,
        optimizer: str = None, # Note: optimizer is not used by this API
        conversationally: bool = False, # Note: conversationally is not used by this API
        web_search: bool = False,
    ) -> Union[Dict[str, Any], Generator]:
        """Send a message to the Lambda Chat API"""
        model = self.model
        
        # Check if we have a conversation for this model
        if model not in self._conversation_data:
            conversation_id = self.create_conversation(model)
            if not conversation_id:
                raise exceptions.FailedToGenerateResponseError(f"Failed to create conversation with model {model}")
        else:
            conversation_id = self._conversation_data[model]["conversationId"]
            # Refresh message ID
            self._conversation_data[model]["messageId"] = self.fetch_message_id(conversation_id)
        
        url = f"{self.url}/conversation/{conversation_id}"
        message_id = self._conversation_data[model]["messageId"]
        
        # Data to send (tools should be empty list by default)
        request_data = {
            "inputs": prompt,
            "id": message_id,
            "is_retry": False,
            "is_continue": False,
            "web_search": web_search,
            "tools": []
        }

        # Update headers for this specific request
        headers = self.headers.copy()
        headers["Referer"] = f"{self.url}/conversation/{conversation_id}"
        headers["Accept-Encoding"] = "gzip, deflate, br, zstd"
        headers["Accept-Language"] = "en-US,en;q=0.9,en-IN;q=0.8"
        headers["Sec-GPC"] = "1"
        headers["Sec-Ch-Ua"] = '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"'
        headers["Sec-Ch-Ua-Mobile"] = "?0"
        headers["Sec-Ch-Ua-Platform"] = '"Windows"'
        headers["User-Agent"] = LitAgent().random() # Use LitAgent for User-Agent
        headers["Origin"] = self.url

        # Create multipart form data
        boundary = self.generate_boundary()
        multipart_headers = headers.copy()
        multipart_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"

        # Serialize the data to JSON
        data_json = json.dumps(request_data, separators=(',', ':'))

        # Create the multipart form data body
        body = f"--{boundary}\r\n"
        body += f'Content-Disposition: form-data; name="data"\r\n'
        body += f"\r\n"
        body += f"{data_json}\r\n"
        body += f"--{boundary}--\r\n"

        multipart_headers["Content-Length"] = str(len(body))
        
        def for_stream():
            streaming_text = "" # Initialize for history
            try:
                # Try with multipart/form-data first
                response = None
                try:
                    # Use curl_cffi session post with impersonate
                    response = self.session.post(
                        url, 
                        data=body,
                        headers=multipart_headers, # Use multipart headers
                        stream=True,
                        timeout=self.timeout,
                        impersonate="chrome110" # Use a common impersonation profile
                    )
                    response.raise_for_status() # Check status after potential error
                except (CurlError, exceptions.FailedToGenerateResponseError, Exception): # Catch potential errors
                    response = None # Ensure response is None if multipart fails

                # If multipart fails or returns error, try with regular JSON
                if not response or response.status_code != 200:
                    # Use curl_cffi session post with impersonate
                    response = self.session.post(
                        url, 
                        json=request_data, # Use JSON payload
                        headers=headers, # Use regular headers
                        stream=True,
                        timeout=self.timeout,
                        impersonate="chrome110" # Use a common impersonation profile
                    )
                
                response.raise_for_status() # Check status after potential fallback
                
                # Use sanitize_stream
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None), # Pass byte iterator
                    intro_value=None, # No prefix
                    to_json=True,     # Stream sends JSON lines
                    content_extractor=self._lambdachat_extractor, # Use the specific extractor
                    yield_raw_on_error=False # Skip non-JSON lines or lines where extractor fails
                )

                for content_chunk in processed_stream:
                    # content_chunk is the string extracted by _lambdachat_extractor
                    if content_chunk and isinstance(content_chunk, str):
                        streaming_text += content_chunk # Aggregate text for history
                        resp = {"text": content_chunk}
                        yield resp if not raw else content_chunk
                
            except (CurlError, exceptions.FailedToGenerateResponseError, Exception) as e: # Catch errors from both attempts
                # Handle specific exceptions if needed
                if isinstance(e, CurlError):
                     # Log or handle CurlError specifically
                     pass
                
                # Try another model if current one fails
                if len(self.AVAILABLE_MODELS) > 1:
                    current_model_index = self.AVAILABLE_MODELS.index(self.model) if self.model in self.AVAILABLE_MODELS else 0
                    next_model_index = (current_model_index + 1) % len(self.AVAILABLE_MODELS)
                    self.model = self.AVAILABLE_MODELS[next_model_index]
                    
                    # Create new conversation with the alternate model
                    conversation_id = self.create_conversation(self.model)
                    if conversation_id:
                        # Try again with the new model
                        yield from self.ask(prompt, stream=True, raw=raw, optimizer=optimizer, 
                                          conversationally=conversationally, web_search=web_search)
                        return
                
                # If we get here, all models failed
                raise exceptions.FailedToGenerateResponseError(f"Request failed after trying fallback: {str(e)}") from e

            # Update history after stream finishes
            if streaming_text and self.conversation.file:
                self.last_response = {"text": streaming_text}
                self.conversation.update_chat_history(prompt, streaming_text)

        def for_non_stream():
            # Aggregate the stream using the updated for_stream logic
            response_text = ""
            try:
                # Ensure raw=False so for_stream yields dicts
                for chunk_data in for_stream():
                    if isinstance(chunk_data, dict) and "text" in chunk_data:
                        response_text += chunk_data["text"]
                    # Handle raw string case if raw=True was passed
                    elif raw and isinstance(chunk_data, str):
                         response_text += chunk_data
            except Exception as e:
                 # If aggregation fails but some text was received, use it. Otherwise, re-raise.
                 if not response_text:
                     raise exceptions.FailedToGenerateResponseError(f"Failed to get non-stream response: {str(e)}") from e

            # last_response and history are updated within process_response called by for_stream
            # Return the final aggregated response dict or raw string
            return response_text if raw else {"text": response_text} # Return dict for consistency


        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None, # Note: optimizer is not used by this API
        conversationally: bool = False, # Note: conversationally is not used by this API
        web_search: bool = False
    ) -> Union[str, Generator]:
        """Generate a response to a prompt"""
        def for_stream_chat():
            # ask() yields dicts or strings when streaming
            gen = self.ask(
                prompt, stream=True, raw=False, # Ensure ask yields dicts
                optimizer=optimizer, conversationally=conversationally, web_search=web_search
            )
            for response_dict in gen:
                yield self.get_message(response_dict) # get_message expects dict
                
        def for_non_stream_chat():
            # ask() returns dict or str when not streaming
            response_data = self.ask(
                prompt, stream=False, raw=False, # Ensure ask returns dict
                optimizer=optimizer, conversationally=conversationally, web_search=web_search
            )
            return self.get_message(response_data) # get_message expects dict
            
        return for_stream_chat() if stream else for_non_stream_chat()

    def get_message(self, response: dict) -> str:
        """Extract message text from response"""
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response.get("text", "")

if __name__ == "__main__":
    # Ensure curl_cffi is installed
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)

    for model in LambdaChat.AVAILABLE_MODELS:
        try:
            test_ai = LambdaChat(model=model, timeout=60)
            response = test_ai.chat("Say 'Hello' in one word")
            response_text = response
            
            if response_text and len(response_text.strip()) > 0:
                status = "✓"
                # Truncate response if too long
                display_text = response_text.strip()[:50] + "..." if len(response_text.strip()) > 50 else response_text.strip()
            else:
                status = "✗"
                display_text = "Empty or invalid response"
            print(f"{model:<50} {status:<10} {display_text}")
        except Exception as e:
            print(f"{model:<50} {'✗':<10} {str(e)}")