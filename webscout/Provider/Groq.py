from typing import Any, AsyncGenerator, Dict, Optional, Callable, List, Union

import httpx
import json

# Import curl_cffi for improved request handling
from curl_cffi.requests import Session
from curl_cffi import CurlError

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts, sanitize_stream # Import sanitize_stream
from webscout.AIbase import Provider, AsyncProvider
from webscout import exceptions

class GROQ(Provider):
    """
    A class to interact with the GROQ AI API.
    """
    required_auth = True
    # Default models list (will be updated dynamically)
    AVAILABLE_MODELS = [
        "distil-whisper-large-v3-en",
        "gemma2-9b-it",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "llama-guard-3-8b",
        "llama3-70b-8192",
        "llama3-8b-8192",
        "whisper-large-v3",
        "whisper-large-v3-turbo",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "meta-llama/llama-4-maverick-17b-128e-instruct",
        "playai-tts",
        "playai-tts-arabic",
        "qwen-qwq-32b",
        "mistral-saba-24b",
        "qwen-2.5-coder-32b",
        "qwen-2.5-32b",
        "deepseek-r1-distill-qwen-32b",
        "deepseek-r1-distill-llama-70b",
        "llama-3.3-70b-specdec",
        "llama-3.2-1b-preview",
        "llama-3.2-3b-preview",
        "llama-3.2-11b-vision-preview",
        "llama-3.2-90b-vision-preview",
        "mixtral-8x7b-32768"
    ]
    
    @classmethod
    def get_models(cls, api_key: str = None):
        """Fetch available models from Groq API.
        
        Args:
            api_key (str, optional): Groq API key. If not provided, returns default models.
            
        Returns:
            list: List of available model IDs
        """
        if not api_key:
            return cls.AVAILABLE_MODELS
            
        try:
            # Use a temporary curl_cffi session for this class method
            temp_session = Session()
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            
            response = temp_session.get(
                "https://api.groq.com/openai/v1/models",
                headers=headers,
                impersonate="chrome110"  # Use impersonate for fetching
            )
            
            if response.status_code != 200:
                return cls.AVAILABLE_MODELS
                
            data = response.json()
            if "data" in data and isinstance(data["data"], list):
                return [model["id"] for model in data["data"]]
            return cls.AVAILABLE_MODELS
            
        except (CurlError, Exception):
            # Fallback to default models list if fetching fails
            return cls.AVAILABLE_MODELS

    def __init__(
        self,
        api_key: str,
        is_conversation: bool = True,
        max_tokens: int = 600,
        temperature: float = 1,
        presence_penalty: int = 0,
        frequency_penalty: int = 0,
        top_p: float = 1,
        model: str = "mixtral-8x7b-32768",
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        system_prompt: Optional[str] = None,
    ):
        """Instantiates GROQ

        Args:
            api_key (key): GROQ's API key.
            is_conversation (bool, optional): Flag for chatting conversationally. Defaults to True.
            max_tokens (int, optional): Maximum number of tokens to be generated upon completion. Defaults to 600.
            temperature (float, optional): Charge of the generated text's randomness. Defaults to 1.
            presence_penalty (int, optional): Chances of topic being repeated. Defaults to 0.
            frequency_penalty (int, optional): Chances of word being repeated. Defaults to 0.
            top_p (float, optional): Sampling threshold during inference time. Defaults to 0.999.
            model (str, optional): LLM model name. Defaults to "mixtral-8x7b-32768".
            timeout (int, optional): Http request timeout. Defaults to 30.
            intro (str, optional): Conversation introductory prompt. Defaults to None.
            filepath (str, optional): Path to file containing conversation history. Defaults to None.
            update_file (bool, optional): Add new prompts and responses to the file. Defaults to True.
            proxies (dict, optional): Http request proxies. Defaults to {}.
            history_offset (int, optional): Limit conversation history to this number of last texts. Defaults to 10250.
            act (str|int, optional): Awesome prompt key or index. (Used as intro). Defaults to None.
            system_prompt (str, optional): System prompt to guide the conversation. Defaults to None.
        """
        # Update available models from API
        self.update_available_models(api_key)
        
        # Validate model after updating available models
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        # Initialize curl_cffi Session
        self.session = Session()
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.presence_penalty = presence_penalty
        self.frequency_penalty = frequency_penalty
        self.top_p = top_p
        self.chat_endpoint = "https://api.groq.com/openai/v1/chat/completions" 
        self.stream_chunk_size = 64
        self.timeout = timeout
        self.last_response = {}
        self.system_prompt = system_prompt
        self.available_functions: Dict[str, Callable] = {}  # Store available functions
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        self.__available_optimizers = (
            method
            for method in dir(Optimizers)
            if callable(getattr(Optimizers, method)) and not method.startswith("__")
        )
        
        # Update curl_cffi session headers
        self.session.headers.update(self.headers)
        
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
        
        # Set proxies for curl_cffi session
        self.session.proxies = proxies
    
    @staticmethod
    def _groq_extractor(chunk: Union[str, Dict[str, Any]]) -> Optional[Dict]:
        """Extracts the 'delta' object from Groq stream JSON chunks."""
        if isinstance(chunk, dict):
            # Return the delta object itself, or None if not found
            return chunk.get("choices", [{}])[0].get("delta")
        return None

    @classmethod
    def update_available_models(cls, api_key=None):
        """Update the available models list from Groq API"""
        try:
            models = cls.get_models(api_key)
            if models and len(models) > 0:
                cls.AVAILABLE_MODELS = models
        except Exception:
            # Fallback to default models list if fetching fails
            pass

    def add_function(self, function_name: str, function: Callable):
        """Add a function to the available functions dictionary.

        Args:
            function_name (str): The name of the function to be used in the prompt.
            function (Callable): The function itself.
        """
        self.available_functions[function_name] = function

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,  # Add tools parameter
    ) -> dict:
        """Chat with AI

        Args:
            prompt (str): Prompt to be send.
            stream (bool, optional): Flag for streaming response. Defaults to False.
            raw (bool, optional): Stream back raw response as received. Defaults to False.
            optimizer (str, optional): Prompt optimizer name - `[code, shell_command]`. Defaults to None.
            conversationally (bool, optional): Chat conversationally when using optimizer. Defaults to False.
            tools (List[Dict[str, Any]], optional): List of tool definitions. See example in class docstring. Defaults to None.

        Returns:
           dict : {}
        """
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise Exception(
                    f"Optimizer is not one of {self.__available_optimizers}"
                )

        messages = [{"content": conversation_prompt, "role": "user"}]
        if self.system_prompt:
            messages.insert(0, {"role": "system", "content": self.system_prompt})

        self.session.headers.update(self.headers)
        payload = {
            "frequency_penalty": self.frequency_penalty,
            "messages": messages,
            "model": self.model,
            "presence_penalty": self.presence_penalty,
            "stream": stream,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "tools": tools  # Include tools in the payload
        }

        def for_stream():
            try:
                response = self.session.post(
                    self.chat_endpoint, 
                    json=payload, 
                    stream=True, 
                    timeout=self.timeout,
                    impersonate="chrome110"  # Use impersonate for better compatibility
                )
                if not response.status_code == 200:
                    raise exceptions.FailedToGenerateResponseError(
                        # Removed response.reason_phrase
                        f"Failed to generate response - ({response.status_code}) - {response.text}"
                    )

                streaming_text = ""
                # Use sanitize_stream
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None), # Pass byte iterator
                    intro_value="data:",
                    to_json=True,     # Stream sends JSON
                    content_extractor=self._groq_extractor, # Use the delta extractor
                    yield_raw_on_error=False # Skip non-JSON lines or lines where extractor fails
                )

                for delta in processed_stream:
                    # delta is the extracted 'delta' object or None
                    if delta and isinstance(delta, dict):
                        content = delta.get("content")
                        if content:
                            streaming_text += content
                            resp = {"text": content} # Yield only the new chunk text
                            self.last_response = {"choices": [{"delta": {"content": streaming_text}}]} # Update last_response structure
                            yield resp if not raw else content # Yield dict or raw string chunk
                        # Note: Tool calls in streaming delta are less common in OpenAI format, usually in final message

            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"CurlError: {str(e)}")
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"Error: {str(e)}")

            # Handle tool calls if any
            if 'tool_calls' in self.last_response.get('choices', [{}])[0].get('message', {}):
                tool_calls = self.last_response['choices'][0]['message']['tool_calls']
                for tool_call in tool_calls:
                    function_name = tool_call.get('function', {}).get('name')
                    arguments = json.loads(tool_call.get('function', {}).get('arguments', "{}"))
                    if function_name in self.available_functions:
                        tool_response = self.available_functions[function_name](**arguments)
                        messages.append({
                            "tool_call_id": tool_call['id'],
                            "role": "tool",
                            "name": function_name,
                            "content": tool_response
                        })
                        payload['messages'] = messages
                        # Make a second call to get the final response
                        try:
                            second_response = self.session.post(
                                self.chat_endpoint, 
                                json=payload, 
                                timeout=self.timeout,
                                impersonate="chrome110"  # Use impersonate for better compatibility
                            )
                            if second_response.status_code == 200:
                                self.last_response = second_response.json()
                            else:
                                raise exceptions.FailedToGenerateResponseError(
                                    f"Failed to execute tool - {second_response.text}"
                                )
                        except CurlError as e:
                            raise exceptions.FailedToGenerateResponseError(f"CurlError during tool execution: {str(e)}")
                        except Exception as e:
                            raise exceptions.FailedToGenerateResponseError(f"Error during tool execution: {str(e)}")

            self.conversation.update_chat_history(
                prompt, self.get_message(self.last_response)
            )

        def for_non_stream():
            try:
                response = self.session.post(
                    self.chat_endpoint, 
                    json=payload, 
                    stream=False, 
                    timeout=self.timeout,
                    impersonate="chrome110"  # Use impersonate for better compatibility
                )
                if (
                    not response.status_code == 200
                ):
                    raise exceptions.FailedToGenerateResponseError(
                         # Removed response.reason_phrase
                        f"Failed to generate response - ({response.status_code}) - {response.text}"
                    )
                
                response_text = response.text # Get raw text

                # Use sanitize_stream to parse the non-streaming JSON response
                processed_stream = sanitize_stream(
                    data=response_text,
                    to_json=True, # Parse the whole text as JSON
                    intro_value=None,
                    # Extractor for non-stream structure (returns the whole parsed dict)
                    content_extractor=lambda chunk: chunk if isinstance(chunk, dict) else None,
                    yield_raw_on_error=False
                )
                
                # Extract the single result (the parsed JSON dictionary)
                resp = next(processed_stream, None)
                if resp is None:
                    raise exceptions.FailedToGenerateResponseError("Failed to parse non-stream JSON response")

            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"CurlError: {str(e)}")
            except Exception as e:
                # Catch the original AttributeError here if it happens before the raise
                if isinstance(e, AttributeError) and 'reason_phrase' in str(e):
                     raise exceptions.FailedToGenerateResponseError(
                        f"Failed to generate response - ({response.status_code}) - {response.text}"
                    )
                raise exceptions.FailedToGenerateResponseError(f"Error: {str(e)}")

            # Handle tool calls if any
            if 'tool_calls' in resp.get('choices', [{}])[0].get('message', {}):
                tool_calls = resp['choices'][0]['message']['tool_calls']
                for tool_call in tool_calls:
                    function_name = tool_call.get('function', {}).get('name')
                    arguments = json.loads(tool_call.get('function', {}).get('arguments', "{}"))
                    if function_name in self.available_functions:
                        tool_response = self.available_functions[function_name](**arguments)
                        messages.append({
                            "tool_call_id": tool_call['id'],
                            "role": "tool",
                            "name": function_name,
                            "content": tool_response
                        })
                        payload['messages'] = messages
                        # Make a second call to get the final response
                        try:
                            second_response = self.session.post(
                                self.chat_endpoint, 
                                json=payload, 
                                timeout=self.timeout,
                                impersonate="chrome110"  # Use impersonate for better compatibility
                            )
                            if second_response.status_code == 200:
                                resp = second_response.json()
                            else:
                                raise exceptions.FailedToGenerateResponseError(
                                    f"Failed to execute tool - {second_response.text}"
                                )
                        except CurlError as e:
                            raise exceptions.FailedToGenerateResponseError(f"CurlError during tool execution: {str(e)}")
                        except Exception as e:
                            raise exceptions.FailedToGenerateResponseError(f"Error during tool execution: {str(e)}")

            self.last_response.update(resp)
            self.conversation.update_chat_history(
                prompt, self.get_message(self.last_response)
            )
            return resp

        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Generate response `str`
        Args:
            prompt (str): Prompt to be send.
            stream (bool, optional): Flag for streaming response. Defaults to False.
            optimizer (str, optional): Prompt optimizer name - `[code, shell_command]`. Defaults to None.
            conversationally (bool, optional): Chat conversationally when using optimizer. Defaults to False.
            tools (List[Dict[str, Any]], optional): List of tool definitions. See example in class docstring. Defaults to None.
        Returns:
            str: Response generated
        """

        def for_stream():
            for response in self.ask(
                prompt, True, optimizer=optimizer, conversationally=conversationally, tools=tools
            ):
                yield self.get_message(response)

        def for_non_stream():
            return self.get_message(
                self.ask(
                    prompt,
                    False,
                    optimizer=optimizer,
                    conversationally=conversationally,
                    tools=tools
                )
            )

        return for_stream() if stream else for_non_stream()

    def get_message(self, response: dict) -> str:
        """Retrieves message only from response

        Args:
            response (dict): Response generated by `self.ask`

        Returns:
            str: Message extracted
        """
        assert isinstance(response, dict), "Response should be of dict data-type only"
        try:
            # Check delta first for streaming
            if response.get("choices") and response["choices"][0].get("delta") and response["choices"][0]["delta"].get("content"):
                return response["choices"][0]["delta"]["content"]
            # Check message content for non-streaming or final message
            if response.get("choices") and response["choices"][0].get("message") and response["choices"][0]["message"].get("content"):
                return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            # Handle cases where the structure might be different or content is null/missing
            pass
        return "" # Return empty string if no content found


class AsyncGROQ(AsyncProvider):
    """
    An asynchronous class to interact with the GROQ AI API.
    """

    # Use the same model list as the synchronous class
    AVAILABLE_MODELS = GROQ.AVAILABLE_MODELS

    def __init__(
        self,
        api_key: str,
        is_conversation: bool = True,
        max_tokens: int = 600,
        temperature: float = 1,
        presence_penalty: int = 0,
        frequency_penalty: int = 0,
        top_p: float = 1,
        model: str = "mixtral-8x7b-32768",
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        system_prompt: Optional[str] = None,
    ):
        """Instantiates AsyncGROQ

        Args:
            api_key (key): GROQ's API key.
            is_conversation (bool, optional): Flag for chatting conversationally. Defaults to True.
            max_tokens (int, optional): Maximum number of tokens to be generated upon completion. Defaults to 600.
            temperature (float, optional): Charge of the generated text's randomness. Defaults to 1.
            presence_penalty (int, optional): Chances of topic being repeated. Defaults to 0.
            frequency_penalty (int, optional): Chances of word being repeated. Defaults to 0.
            top_p (float, optional): Sampling threshold during inference time. Defaults to 0.999.
            model (str, optional): LLM model name. Defaults to "gpt-3.5-turbo".
            timeout (int, optional): Http request timeout. Defaults to 30.
            intro (str, optional): Conversation introductory prompt. Defaults to None.
            filepath (str, optional): Path to file containing conversation history. Defaults to None.
            update_file (bool, optional): Add new prompts and responses to the file. Defaults to True.
            proxies (dict, optional): Http request proxies. Defaults to {}.
            history_offset (int, optional): Limit conversation history to this number of last texts. Defaults to 10250.
            act (str|int, optional): Awesome prompt key or index. (Used as intro). Defaults to None.
            system_prompt (str, optional): System prompt to guide the conversation. Defaults to None.
        """
        # Update available models from API
        GROQ.update_available_models(api_key)
        
        # Validate model after updating available models
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.presence_penalty = presence_penalty
        self.frequency_penalty = frequency_penalty
        self.top_p = top_p
        self.chat_endpoint = "https://api.groq.com/openai/v1/chat/completions"
        self.stream_chunk_size = 64
        self.timeout = timeout
        self.last_response = {}
        self.system_prompt = system_prompt
        self.available_functions: Dict[str, Callable] = {}  # Store available functions
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

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
        self.session = httpx.AsyncClient(headers=self.headers, proxies=proxies)

    def add_function(self, function_name: str, function: Callable):
        """Add a function to the available functions dictionary.

        Args:
            function_name (str): The name of the function to be used in the prompt.
            function (Callable): The function itself.
        """
        self.available_functions[function_name] = function

    async def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Union[dict, AsyncGenerator]:
        """Chat with AI asynchronously.

        Args:
            prompt (str): Prompt to be send.
            stream (bool, optional): Flag for streaming response. Defaults to False.
            raw (bool, optional): Stream back raw response as received. Defaults to False.
            optimizer (str, optional): Prompt optimizer name - `[code, shell_command]`. Defaults to None.
            conversationally (bool, optional): Chat conversationally when using optimizer. Defaults to False.
            tools (List[Dict[str, Any]], optional): List of tool definitions. See example in class docstring. Defaults to None.
        Returns:
           dict|AsyncGenerator : ai content
        """
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise Exception(
                    f"Optimizer is not one of {self.__available_optimizers}"
                )

        messages = [{"content": conversation_prompt, "role": "user"}]
        if self.system_prompt:
            messages.insert(0, {"role": "system", "content": self.system_prompt})

        payload = {
            "frequency_penalty": self.frequency_penalty,
            "messages": messages,
            "model": self.model,
            "presence_penalty": self.presence_penalty,
            "stream": stream,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "tools": tools
        }

        async def for_stream():
            async with self.session.stream(
                "POST", self.chat_endpoint, json=payload, timeout=self.timeout
            ) as response:
                if not response.is_success:
                    raise exceptions.FailedToGenerateResponseError(
                        # Removed response.reason_phrase (not available in httpx response)
                        f"Failed to generate response - ({response.status_code})"
                    )

                message_load = ""
                intro_value = "data:"
                async for value in response.aiter_lines():
                    try:
                        if value.startswith(intro_value):
                            value = value[len(intro_value) :]
                        resp = json.loads(value)
                        incomplete_message = await self.get_message(resp)
                        if incomplete_message:
                            message_load += incomplete_message
                            resp["choices"][0]["delta"]["content"] = message_load
                            self.last_response.update(resp)
                            yield value if raw else resp
                        elif raw:
                            yield value
                    except json.decoder.JSONDecodeError:
                        pass

                # Handle tool calls if any (in streaming mode)
                if 'tool_calls' in self.last_response.get('choices', [{}])[0].get('message', {}):
                    tool_calls = self.last_response['choices'][0]['message']['tool_calls']
                    for tool_call in tool_calls:
                        function_name = tool_call.get('function', {}).get('name')
                        arguments = json.loads(tool_call.get('function', {}).get('arguments', "{}"))
                        if function_name in self.available_functions:
                            tool_response = self.available_functions[function_name](**arguments)
                            messages.append({
                                "tool_call_id": tool_call['id'],
                                "role": "tool",
                                "name": function_name,
                                "content": tool_response
                            })
                            payload['messages'] = messages
                            # Make a second call to get the final response
                            second_response = await self.session.post(
                                self.chat_endpoint, json=payload, timeout=self.timeout
                            )
                            if second_response.is_success:
                                self.last_response = second_response.json()
                            else:
                                raise exceptions.FailedToGenerateResponseError(
                                    f"Failed to execute tool - {second_response.text}"
                                )

            self.conversation.update_chat_history(
                prompt, await self.get_message(self.last_response)
            )

        async def for_non_stream():
            response = await self.session.post(
                self.chat_endpoint, json=payload, timeout=self.timeout
            )
            if not response.is_success:
                raise exceptions.FailedToGenerateResponseError(
                    # Removed response.reason_phrase (not available in httpx response)
                    f"Failed to generate response - ({response.status_code})"
                )
            resp = response.json()

            # Handle tool calls if any (in non-streaming mode)
            if 'tool_calls' in resp.get('choices', [{}])[0].get('message', {}):
                tool_calls = resp['choices'][0]['message']['tool_calls']
                for tool_call in tool_calls:
                    function_name = tool_call.get('function', {}).get('name')
                    arguments = json.loads(tool_call.get('function', {}).get('arguments', "{}"))
                    if function_name in self.available_functions:
                        tool_response = self.available_functions[function_name](**arguments)
                        messages.append({
                            "tool_call_id": tool_call['id'],
                            "role": "tool",
                            "name": function_name,
                            "content": tool_response
                        })
                        payload['messages'] = messages
                        # Make a second call to get the final response
                        second_response = await self.session.post(
                            self.chat_endpoint, json=payload, timeout=self.timeout
                        )
                        if second_response.is_success:
                            resp = second_response.json()
                        else:
                            raise exceptions.FailedToGenerateResponseError(
                                f"Failed to execute tool - {second_response.text}"
                            )

            self.last_response.update(resp)
            self.conversation.update_chat_history(
                prompt, await self.get_message(self.last_response)
            )
            return resp

        return for_stream() if stream else await for_non_stream()

    async def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Union[str, AsyncGenerator]:
        """Generate response `str` asynchronously.
        Args:
            prompt (str): Prompt to be send.
            stream (bool, optional): Flag for streaming response. Defaults to False.
            optimizer (str, optional): Prompt optimizer name - `[code, shell_command]`. Defaults to None.
            conversationally (bool, optional): Chat conversationally when using optimizer. Defaults to False.
            tools (List[Dict[str, Any]], optional): List of tool definitions. See example in class docstring. Defaults to None.
        Returns:
            str|AsyncGenerator: Response generated
        """

        async def for_stream():
            async_ask = await self.ask(
                prompt, True, optimizer=optimizer, conversationally=conversationally, tools=tools
            )
            async for response in async_ask:
                yield await self.get_message(response)

        async def for_non_stream():
            return await self.get_message(
                await self.ask(
                    prompt,
                    False,
                    optimizer=optimizer,
                    conversationally=conversationally,
                    tools=tools
                )
            )

        return for_stream() if stream else await for_non_stream()

    async def get_message(self, response: dict) -> str:
        """Retrieves message only from response

        Args:
            response (dict): Response generated by `self.ask`

        Returns:
            str: Message extracted
        """
        assert isinstance(response, dict), "Response should be of dict data-type only"
        try:
            # Check delta first for streaming
            if response.get("choices") and response["choices"][0].get("delta") and response["choices"][0]["delta"].get("content"):
                return response["choices"][0]["delta"]["content"]
            # Check message content for non-streaming or final message
            if response.get("choices") and response["choices"][0].get("message") and response["choices"][0]["message"].get("content"):
                return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
             # Handle cases where the structure might be different or content is null/missing
            pass
        return "" # Return empty string if no content found
        
if __name__ == "__main__":
    # Example usage
    api_key = "gsk_*******************************"
    groq = GROQ(api_key=api_key, model="compound-beta")
    prompt = "What is the capital of France?"
    response = groq.chat(prompt)
    print(response)