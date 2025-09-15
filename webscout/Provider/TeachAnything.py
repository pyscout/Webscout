from curl_cffi.requests import Session # Import Session
from curl_cffi import CurlError # Import CurlError
from typing import Union, Any, Dict
from webscout.AIbase import Provider # Import Provider base class
from webscout import exceptions # Import custom exceptions
from webscout.conversation import Conversation
from webscout.AIutel import Optimizers, sanitize_stream # Import sanitize_stream
from webscout.prompt_manager import AwesomePrompts
from webscout.litagent import LitAgent

# Inherit from Provider
class TeachAnything(Provider):
    """
    A class to interact with the Teach-Anything API.
    """
    # Add AVAILABLE_MODELS if applicable, otherwise remove model param
    # AVAILABLE_MODELS = ["default"] # Example
    required_auth = False

    def __init__(
        self,
        is_conversation: bool = True,
        max_tokens: int = 600, # Note: max_tokens is not used by this API
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        # model: str = "default" # Remove if not used
    ) -> None:
        """
        Initializes the Teach-Anything API with given parameters.

        Args:
            is_conversation (bool, optional): Flag for chatting conversationally. Defaults to True.
            max_tokens (int, optional): Maximum number of tokens to be generated upon completion. Defaults to 600.
            timeout (int, optional): Http request timeout. Defaults to 30.
            intro (str, optional): Conversation introductory prompt. Defaults to None.
            filepath (str, optional): Path to file containing conversation history. Defaults to None.
            update_file (bool, optional): Add new prompts and responses to the file. Defaults to True.
            proxies (dict, optional): Http request proxies. Defaults to {}.
            history_offset (int, optional): Limit conversation history to this number of last texts. Defaults to 10250.
            act (str|int, optional): Awesome prompt key or index. (Used as intro). Defaults to None.
            model (str, optional): AI model to use for text generation. Defaults to "gpt4".
        """


        # Initialize curl_cffi Session
        self.session = Session()
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.api_endpoint = "https://www.teach-anything.com/api/generate"
        self.timeout = timeout
        self.last_response = {}
        self.headers = {
            "authority": "www.teach-anything.com",
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9,en-IN;q=0.8",
            "content-type": "application/json",
            "origin": "https://www.teach-anything.com",
            "referer": "https://www.teach-anything.com/",
            "user-agent": LitAgent().random(),
            # Add sec-ch-ua headers if needed for impersonation consistency
        }
        self.__available_optimizers = (
            method
            for method in dir(Optimizers)
            if callable(getattr(Optimizers, method)) and not method.startswith("__")
        )
        # Update curl_cffi session headers and proxies
        self.session.headers.update(self.headers)
        self.session.proxies = proxies # Assign proxies directly
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
        stream: bool = False, # Keep stream param for interface, but API doesn't stream
        raw: bool = False, # Keep raw param for interface
        optimizer: str = None,
        conversationally: bool = False,
    ) -> dict:
        """Chat with AI

        Args:
            prompt (str): Prompt to be send.
            stream (bool, optional): Whether to stream the response. Defaults to False.
            raw (bool, optional): Whether to return the raw response. Defaults to False.
            optimizer (str, optional): The name of the optimizer to use. Defaults to None.
            conversationally (bool, optional): Whether to chat conversationally. Defaults to False.

        Returns:
            The response from the API.
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

        payload = {
            "prompt": conversation_prompt
        }

        # API does not stream, so implement non-stream logic directly
        try:
            # Use curl_cffi session post with impersonate
            response = self.session.post(
                self.api_endpoint, 
                # headers are set on the session
                json=payload, 
                timeout=self.timeout,
                impersonate="chrome110" # Use a common impersonation profile
            )
            response.raise_for_status() # Check for HTTP errors

            resp_text_raw = response.text # Get raw response text

            # Process the text using sanitize_stream (even though it's not streaming)
            # This keeps the pattern consistent, though it won't do much here
            processed_stream = sanitize_stream(
                data=resp_text_raw,
                intro_value=None, # No prefix
                to_json=False     # It's plain text
            )

            # Extract the single result from the generator
            resp_text = "".join(list(processed_stream)) # Aggregate potential chunks (should be one)

            self.last_response = {"text": resp_text}
            self.conversation.update_chat_history(prompt, resp_text)

            # Return dict or raw string based on raw flag
            return resp_text if raw else self.last_response

        except CurlError as e: # Catch CurlError
            raise exceptions.FailedToGenerateResponseError(f"Request failed (CurlError): {e}") from e
        except Exception as e: # Catch other potential exceptions (like HTTPError)
            err_text = getattr(e, 'response', None) and getattr(e.response, 'text', '')
            raise exceptions.FailedToGenerateResponseError(f"An unexpected error occurred ({type(e).__name__}): {e} - {err_text}") from e


    def chat(
        self,
        prompt: str,
        stream: bool = False, # Keep stream param for interface consistency
        optimizer: str = None,
        conversationally: bool = False,
        raw: bool = False,  # Added raw parameter
    ) -> Union[str, Any]:
        """Generate response `str` or yield for streaming compatibility
        Args:
            prompt (str): Prompt to be send.
            stream (bool, optional): Flag for streaming response. Defaults to False.
            optimizer (str, optional): Prompt optimizer name - `[code, shell_command]`. Defaults to None.
            conversationally (bool, optional): Chat conversationally when using optimizer. Defaults to False.
            raw (bool, optional): If True, return raw string output.
        Returns:
            str or generator: Response generated
        """
        response_data = self.ask(
            prompt, 
            stream=False, # Call ask in non-stream mode internally
            raw=raw, # Pass raw flag
            optimizer=optimizer, 
            conversationally=conversationally
        )
        if stream:
            def stream_wrapper():
                if raw:
                    yield response_data if isinstance(response_data, str) else self.get_message(response_data)
                else:
                    yield self.get_message(response_data)
            return stream_wrapper()
        else:
            if raw:
                return response_data if isinstance(response_data, str) else self.get_message(response_data)
            else:
                return self.get_message(response_data)

    def get_message(self, response: Union[dict, str]) -> str:
        """Retrieves message only from response

        Args:
            response (Union[dict, str]): Response generated by `self.ask`

        Returns:
            str: Message extracted
        """
        if isinstance(response, str):
            return response
        elif isinstance(response, dict):
            return response["text"]
        raise ValueError("Response must be either dict or str")


if __name__ == '__main__':
    # Ensure curl_cffi is installed
    from rich import print
    try: # Add try-except block for testing
        ai = TeachAnything(timeout=60)
        print("[bold blue]Testing Chat (Non-Stream Simulation):[/bold blue]")
        # Test non-stream first as API doesn't truly stream
        response_non_stream = ai.chat("hi", stream=False)
        print(response_non_stream)
        print("[bold green]Non-Stream Test Complete.[/bold green]\n")

        # Test stream interface (will yield the full response at once)
        print("[bold blue]Testing Chat (Stream Simulation):[/bold blue]")
        response_stream = ai.chat("hello again", stream=True)
        full_stream_response = ""
        for chunk in response_stream:
            print(chunk, end="", flush=True)
            full_stream_response += chunk
        print("\n[bold green]Stream Test Complete.[/bold green]")

    except exceptions.FailedToGenerateResponseError as e:
        print(f"\n[bold red]API Error:[/bold red] {e}")
    except Exception as e:
        print(f"\n[bold red]An unexpected error occurred:[/bold red] {e}")