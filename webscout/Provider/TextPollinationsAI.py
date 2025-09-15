from curl_cffi.requests import Session
from curl_cffi import CurlError
import json
from typing import Union, Any, Dict, Generator, Optional, List

import requests
from webscout.AIutel import Optimizers, Conversation, AwesomePrompts, sanitize_stream # Import sanitize_stream
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent as Lit

class TextPollinationsAI(Provider):
    """
    A class to interact with the Pollinations AI API.
    """

    required_auth = False
    AVAILABLE_MODELS = [
        "deepseek-reasoning",
        "gemini",
        "mistral",
        "nova-fast",
        "openai",
        "openai-audio",
        "openai-fast",
        "openai-reasoning",
        "qwen-coder",
        "roblox-rp",
        "bidara",
        "evil",
        "midijourney",
        "mirexa",
        "rtist",
        "unity",
    ]
    _models_url = "https://text.pollinations.ai/models"

    def __init__(self,
        is_conversation: bool = True,
        max_tokens: int = 8096, # Note: max_tokens is not directly used by this API endpoint
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        model: str = "openai-large",
        system_prompt: str = "You are a helpful AI assistant.",
    ):
        """Initializes the TextPollinationsAI API client."""
        self.session = Session()
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.api_endpoint = "https://text.pollinations.ai/openai"
        self.stream_chunk_size = 64
        self.timeout = timeout
        self.last_response = {}
        self.model = model
        self.system_prompt = system_prompt

        # Validate against the hardcoded list
        if model not in self.AVAILABLE_MODELS:
            raise ValueError(f"Invalid model: {model}. Choose from: {self.AVAILABLE_MODELS}")

        self.headers = {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'User-Agent': Lit().random(),
            'Content-Type': 'application/json',
            # Add sec-ch-ua headers if needed for impersonation consistency
        }

        # Update curl_cffi session headers and proxies
        self.session.headers.update(self.headers)
        self.session.proxies = proxies # Assign proxies directly

        self.__available_optimizers = (
            method for method in dir(Optimizers)
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


    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
    ) -> Union[Dict[str, Any], Generator[Any, None, None]]:
        """Chat with AI"""
        conversation_prompt = self.conversation.gen_complete_prompt(prompt)
        if optimizer:
            if optimizer in self.__available_optimizers:
                conversation_prompt = getattr(Optimizers, optimizer)(
                    conversation_prompt if conversationally else prompt
                )
            else:
                raise Exception(f"Optimizer is not one of {self.__available_optimizers}")

        payload = {
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": conversation_prompt}
            ],
            "model": self.model,
            "stream": stream,
        }

        # Add function calling parameters if provided
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

        def for_stream():
            try:
                response = self.session.post(
                    self.api_endpoint,
                    json=payload,
                    stream=True,
                    timeout=self.timeout,
                    impersonate="chrome120"
                )
                if not response.ok:
                    raise exceptions.FailedToGenerateResponseError(
                        f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                    )
                streaming_text = ""
                processed_stream = sanitize_stream(
                    data=response.iter_content(chunk_size=None),
                    intro_value="data:",
                    to_json=True,
                    skip_markers=["[DONE]"],
                    content_extractor=lambda chunk: chunk.get('choices', [{}])[0].get('delta') if isinstance(chunk, dict) else None,
                    yield_raw_on_error=False,
                    raw=raw
                )
                for delta in processed_stream:
                    if isinstance(delta, bytes):
                        delta = delta.decode('utf-8', errors='ignore')
                    if delta is None:
                        continue
                    if raw:
                        # Only yield content or tool_calls as string
                        if isinstance(delta, dict):
                            if 'content' in delta and delta['content'] is not None:
                                content = delta['content']
                                streaming_text += content
                                yield content
                            elif 'tool_calls' in delta:
                                tool_calls = delta['tool_calls']
                                yield json.dumps(tool_calls)
                        elif isinstance(delta, str):
                            streaming_text += delta
                            yield delta
                    else:
                        if isinstance(delta, dict):
                            if 'content' in delta and delta['content'] is not None:
                                content = delta['content']
                                streaming_text += content
                                yield dict(text=content)
                            elif 'tool_calls' in delta:
                                tool_calls = delta['tool_calls']
                                yield dict(tool_calls=tool_calls)
                self.last_response.update(dict(text=streaming_text))
                if streaming_text:
                    self.conversation.update_chat_history(
                        prompt, streaming_text
                    )
            except CurlError as e:
                raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}") from e
            except Exception as e:
                raise exceptions.FailedToGenerateResponseError(f"An unexpected error occurred ({type(e).__name__}): {e}") from e
        def for_non_stream():
            final_content = ""
            tool_calls_aggregated = None
            try:
                for chunk_data in for_stream():
                    if raw:
                        if isinstance(chunk_data, str):
                            final_content += chunk_data
                        elif isinstance(chunk_data, bytes):
                            final_content += chunk_data.decode('utf-8', errors='ignore')
                        elif isinstance(chunk_data, list):
                            if tool_calls_aggregated is None:
                                tool_calls_aggregated = []
                            tool_calls_aggregated.extend(chunk_data)
                    else:
                        if isinstance(chunk_data, dict):
                            if "text" in chunk_data:
                                final_content += chunk_data["text"]
                            elif "tool_calls" in chunk_data:
                                if tool_calls_aggregated is None:
                                    tool_calls_aggregated = []
                                tool_calls_aggregated.extend(chunk_data["tool_calls"])
                        elif isinstance(chunk_data, str):
                            final_content += chunk_data
            except Exception as e:
                if not final_content and not tool_calls_aggregated:
                    raise exceptions.FailedToGenerateResponseError(f"Failed to get non-stream response: {str(e)}") from e
            result = {}
            if final_content:
                result["text"] = final_content
            if tool_calls_aggregated:
                result["tool_calls"] = tool_calls_aggregated
            self.last_response = result
            return self.last_response if not raw else (final_content if final_content else json.dumps(tool_calls_aggregated) if tool_calls_aggregated else "")
        return for_stream() if stream else for_non_stream()

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
        raw: bool = False,  # Added raw parameter
    ) -> Union[str, Generator[str, None, None]]:
        """Generate response as a string"""
        def for_stream():
            for response in self.ask(
                prompt, True, raw=raw, optimizer=optimizer, conversationally=conversationally,
                tools=tools, tool_choice=tool_choice
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
                tools=tools,
                tool_choice=tool_choice,
            )
            if raw:
                return result if isinstance(result, str) else (result.get("text", "") if isinstance(result, dict) else str(result))
            else:
                return self.get_message(result)
        return for_stream() if stream else for_non_stream()

    def get_message(self, response: dict) -> str:
        """Retrieves message only from response"""
        assert isinstance(response, dict), "Response should be of dict data-type only"
        if "text" in response:
            return response["text"]
        elif "tool_calls" in response:
            # For tool calls, return a string representation
            return json.dumps(response["tool_calls"])
        return "" # Return empty string if neither text nor tool_calls found

if __name__ == "__main__":
    # Ensure curl_cffi is installed
    print("-" * 80)
    print(f"{'Model':<50} {'Status':<10} {'Response'}")
    print("-" * 80)

    # Test all available models
    working = 0
    total = len(TextPollinationsAI.AVAILABLE_MODELS)


    for model in TextPollinationsAI.AVAILABLE_MODELS:
        try:
            test_ai = TextPollinationsAI(model=model, timeout=60)
            # Test stream first
            response_stream = test_ai.chat("Say 'Hello' in one word", stream=True)
            response_text = ""
            print(f"\r{model:<50} {'Streaming...':<10}", end="", flush=True)
            for chunk in response_stream:
                response_text += chunk

            if response_text and len(response_text.strip()) > 0:
                status = "✓"
                # Clean and truncate response
                clean_text = response_text.strip()
                display_text = clean_text[:50] + "..." if len(clean_text) > 50 else clean_text
            else:
                status = "✗ (Stream)"
                display_text = "Empty or invalid stream response"
            print(f"\r{model:<50} {status:<10} {display_text}")

            # Optional: Add non-stream test if needed
            # print(f"\r{model:<50} {'Non-Stream...':<10}", end="", flush=True)
            # response_non_stream = test_ai.chat("Say 'Hi' again", stream=False)
            # if not response_non_stream or len(response_non_stream.strip()) == 0:
            #      print(f"\r{model:<50} {'✗ (Non-Stream)':<10} Empty non-stream response")

        except Exception as e:
            print(f"\r{model:<50} {'✗':<10} {str(e)}")