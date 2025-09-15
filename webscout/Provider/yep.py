import uuid
from curl_cffi import CurlError
from curl_cffi.requests import Session

from typing import Any, Dict, Optional, Generator, Union, List, TypeVar
from webscout.AIutel import Optimizers
from webscout.AIutel import AwesomePrompts, sanitize_stream # Import sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent
from webscout.conversation import Conversation, Fn

T = TypeVar('T')


class YEPCHAT(Provider):
    """
    YEPCHAT is a provider class for interacting with the Yep API.

    Attributes:
        AVAILABLE_MODELS (list): List of available models for the provider.
    """

    required_auth = False
    AVAILABLE_MODELS = ["DeepSeek-R1-Distill-Qwen-32B", "Mixtral-8x7B-Instruct-v0.1"]

    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 1280,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "DeepSeek-R1-Distill-Qwen-32B",
        temperature: float = 0.6,
        top_p: float = 0.7,
        browser: str = "chrome",
        tools: Optional[List[Fn]] = None
    ):
        """
        Initializes the YEPCHAT provider with the specified parameters.

        Examples:
            >>> ai = YEPCHAT()
            >>> ai.ask("What's the weather today?")
            Sends a prompt to the Yep API and returns the response.

            >>> ai.chat("Tell me a joke", stream=True)
            Initiates a chat with the Yep API using the provided prompt.
            
            >>> weather_tool = Fn(name="get_weather", description="Get the current weather", parameters={"location": "string"})
            >>> ai = YEPCHAT(tools=[weather_tool])
            >>> ai.chat("What's the weather in New York?")
            Uses the weather tool to provide weather information.
        """
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(
                f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}"
            )

        # Initialize curl_cffi Session instead of cloudscraper
        self.session = Session() 
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.chat_endpoint = "https://api.yep.com/v1/chat/completions"
        self.stream_chunk_size = 64
        self.timeout = timeout
        self.last_response = {}
        self.model = model
        self.temperature = temperature
        self.top_p = top_p

        # Initialize LitAgent for user agent generation
        self.agent = LitAgent()
        # Use fingerprinting to create a consistent browser identity
        self.fingerprint = self.agent.generate_fingerprint(browser)

        # Use the fingerprint for headers
        self.headers = {
            "Accept": self.fingerprint["accept"],
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": self.fingerprint["accept_language"],
            "Content-Type": "application/json; charset=utf-8",
            "DNT": "1",
            "Origin": "https://yep.com",
            "Referer": "https://yep.com/",
            "Sec-CH-UA": self.fingerprint["sec_ch_ua"] or '"Not)A;Brand";v="99", "Microsoft Edge";v="127", "Chromium";v="127"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": f'"{self.fingerprint["platform"]}"',
            "User-Agent": self.fingerprint["user_agent"],
        }
        
        # Create session cookies with unique identifiers
        self.cookies = {"__Host-session": uuid.uuid4().hex, '__cf_bm': uuid.uuid4().hex}

        self.__available_optimizers = (
            method
            for method in dir(Optimizers)
            if callable(getattr(Optimizers, method))
            and not method.startswith("__")
        )
        Conversation.intro = (
            AwesomePrompts().get_act(act, raise_not_found=True, default=None, case_insensitive=True)
            if act
            else intro or Conversation.intro
        )
        self.conversation = Conversation(
            is_conversation, self.max_tokens_to_sample, filepath, update_file, tools=tools
        )
        self.conversation.history_offset = history_offset
        # Set consistent headers and proxies for the curl_cffi session
        self.session.headers.update(self.headers)
        self.session.proxies = proxies
        # Note: curl_cffi handles cookies differently, passed directly in requests

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
            "Accept": self.fingerprint["accept"],
            "Accept-Language": self.fingerprint["accept_language"],
            "Sec-CH-UA": self.fingerprint["sec_ch_ua"] or self.headers["Sec-CH-UA"],
            "Sec-CH-UA-Platform": f'"{self.fingerprint["platform"]}"',
            "User-Agent": self.fingerprint["user_agent"],
        })
        
        # Update session headers
        self.session.headers.update(self.headers)
        
        # Generate new cookies (will be passed in requests)
        self.cookies = {"__Host-session": uuid.uuid4().hex, '__cf_bm': uuid.uuid4().hex}
        
        return self.fingerprint

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict[str, Any], Generator]:
        """
        Sends a prompt to the Yep API and returns the response.
        Now supports tool calling functionality.

        Examples:
            >>> ai = YEPCHAT()
            >>> ai.ask("What's the weather today?")
            Returns the response from the Yep API.

            >>> ai.ask("Tell me a joke", stream=True)
            Streams the response from the Yep API.
            
            >>> weather_tool = Fn(name="get_weather", description="Get the current weather", parameters={"location": "string"})
            >>> ai = YEPCHAT(tools=[weather_tool])
            >>> ai.ask("What's the weather in New York?")
            Will use the weather tool to provide response.
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

        data = {
            "stream": stream,
            "max_tokens": self.max_tokens_to_sample,
            "top_p": self.top_p,
            "temperature": self.temperature,
            "messages": [{"content": conversation_prompt, "role": "user"}],
            "model": self.model,
        }

        def for_stream():
            try:
                response = self.session.post(self.chat_endpoint, headers=self.headers, cookies=self.cookies, json=data, stream=True, timeout=self.timeout, impersonate=self.fingerprint.get("browser_type", "chrome110"))
                if not response.ok:
                    if response.status_code in [403, 429]:
                        self.refresh_identity()
                        retry_response = self.session.post(self.chat_endpoint, headers=self.headers, cookies=self.cookies, json=data, stream=True, timeout=self.timeout, impersonate=self.fingerprint.get("browser_type", "chrome110"))
                        if not retry_response.ok:
                            raise exceptions.FailedToGenerateResponseError(
                                f"Failed to generate response after identity refresh - ({retry_response.status_code}, {retry_response.reason}) - {retry_response.text}"
                            )
                        response = retry_response
                    else:
                        raise exceptions.FailedToGenerateResponseError(
                            f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                        )
                streaming_text = ""
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None),
                    intro_value="data:",
                    to_json=True,
                    skip_markers=["[DONE]"],
                    yield_raw_on_error=False,
                    content_extractor=lambda chunk: chunk.get('choices', [{}])[0].get('delta', {}).get('content') if isinstance(chunk, dict) else None,
                    raw=raw
                )
                for content_chunk in processed_stream:
                    # Always yield as string, even in raw mode
                    if isinstance(content_chunk, bytes):
                        content_chunk = content_chunk.decode('utf-8', errors='ignore')
                    if raw:
                        yield content_chunk
                    else:
                        if content_chunk and isinstance(content_chunk, str):
                            streaming_text += content_chunk
                            yield dict(text=content_chunk)
                if not raw:
                    response_data = self.conversation.handle_tool_response(streaming_text)
                    if response_data["is_tool_call"]:
                        if response_data["success"]:
                            for tool_call in response_data.get("tool_calls", []):
                                tool_name = tool_call.get("name", "unknown_tool")
                                result = response_data["result"]
                                self.conversation.update_chat_history_with_tool(prompt, tool_name, result)
                        else:
                            self.conversation.update_chat_history(prompt, f"Error executing tool call: {response_data['result']}")
                    else:
                        self.conversation.update_chat_history(prompt, streaming_text)
            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}")
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed: {e}")

        def for_non_stream():
            try:
                response = self.session.post(self.chat_endpoint, headers=self.headers, cookies=self.cookies, json=data, timeout=self.timeout, impersonate=self.fingerprint.get("browser_type", "chrome110"))
                if not response.ok:
                    if response.status_code in [403, 429]:
                        self.refresh_identity()
                        response = self.session.post(self.chat_endpoint, headers=self.headers, cookies=self.cookies, json=data, timeout=self.timeout, impersonate=self.fingerprint.get("browser_type", "chrome110"))
                        if not response.ok:
                            raise exceptions.FailedToGenerateResponseError(
                                f"Failed to generate response after identity refresh - ({response.status_code}, {response.reason}) - {response.text}"
                            )
                    else:
                        raise exceptions.FailedToGenerateResponseError(
                            f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                        )
                if raw:
                    return response.text
                response_data = response.json()
                if 'choices' in response_data and len(response_data['choices']) > 0:
                    content = response_data['choices'][0].get('message', {}).get('content', '')
                    tool_response = self.conversation.handle_tool_response(content)
                    if tool_response["is_tool_call"]:
                        if tool_response["success"]:
                            if "tool_calls" in tool_response and len(tool_response["tool_calls"]) > 0:
                                tool_call = tool_response["tool_calls"][0]
                                tool_name = tool_call.get("name", "unknown_tool")
                                tool_result = tool_response["result"]
                                self.conversation.update_chat_history_with_tool(prompt, tool_name, tool_result)
                                return {"text": tool_result, "is_tool_call": True, "tool_name": tool_name}
                        return {"text": tool_response["result"], "is_tool_call": True, "error": True}
                    else:
                        self.conversation.update_chat_history(prompt, content)
                        return {"text": content}
                else:
                    raise exceptions.FailedToGenerateResponseError("No response content found")
            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}")
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed: {e}")

        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        raw: bool = False,  # Added raw parameter
    ) -> Union[str, Generator[str, None, None]]:
        """
        Initiates a chat with the Yep API using the provided prompt.

        Examples:
            >>> ai = YEPCHAT()
            >>> ai.chat("Tell me a joke")
            Returns the chat response from the Yep API.

            >>> ai.chat("What's the weather today?", stream=True)
            Streams the chat response from the Yep API.
        """
        def for_stream():
            for response in self.ask(
                prompt, True, raw=raw, optimizer=optimizer, conversationally=conversationally
            ):
                if raw:
                    yield response
                else:
                    yield self.get_message(response)

        def for_non_stream():
            result = self.ask(
                prompt,
                False,
                raw=raw,
                optimizer=optimizer,
                conversationally=conversationally,
            )
            if raw:
                return result
            else:
                return self.get_message(result)

        return for_stream() if stream else for_non_stream()

    def get_message(self, response: dict) -> str:
        """
        Extracts the message content from the API response.

        Examples:
            >>> ai = YEPCHAT()
            >>> response = ai.ask("Tell me a joke")
            >>> ai.get_message(response)
            Extracts and returns the message content from the response.
        """
        if isinstance(response, dict):
            return response["text"]
        elif isinstance(response, (str, bytes)):
            return response
        else:
            raise TypeError(f"Unexpected response type: {type(response)}")


if __name__ == "__main__":
    # print("-" * 80)
    # print(f"{'Model':<50} {'Status':<10} {'Response'}")
    # print("-" * 80)

    # for model in YEPCHAT.AVAILABLE_MODELS:
    #     try:
    #         test_ai = YEPCHAT(model=model, timeout=60)
    #         response = test_ai.chat("Say 'Hello' in one word")
    #         response_text = response
            
    #         if response_text and len(response_text.strip()) > 0:
    #             status = "✓"
    #             # Truncate response if too long
    #             display_text = response_text.strip()[:50] + "..." if len(response_text.strip()) > 50 else response_text.strip()
    #         else:
    #             status = "✗"
    #             display_text = "Empty or invalid response"
    #         print(f"{model:<50} {status:<10} {display_text}")
    #     except Exception as e:
    #         print(f"{model:<50} {'✗':<10} {str(e)}")
    ai = YEPCHAT(model="DeepSeek-R1-Distill-Qwen-32B", timeout=60)
    response = ai.chat("Say 'Hello' in one word", raw=False, stream=True)
    for chunk in response:

        print(chunk, end='', flush=True)