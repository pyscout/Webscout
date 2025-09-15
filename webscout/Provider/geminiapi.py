"""
Install the Google AI Python SDK

$ pip install google-generativeai
"""

import os
import google.generativeai as genai

from google.generativeai.types import HarmCategory, HarmBlockThreshold
import requests
from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts
from webscout.AIbase import Provider


class GEMINIAPI(Provider):
    """
    A class to interact with the Gemini API using the google-generativeai library.
    """
    required_auth = True
    def __init__(
        self,
        api_key,
        model_name: str = "gemini-1.5-flash-latest",
        temperature: float = 1,
        top_p: float = 0.95,
        top_k: int = 64,
        max_output_tokens: int = 8192,
        is_conversation: bool = True,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        system_instruction: str = "You are a helpful and informative AI assistant.",
        safety_settings: dict = None,
    ):
        """
        Initializes the Gemini API with the given parameters.

        Args:
            api_key (str, optional): Your Gemini API key. If None, it will use the environment variable "GEMINI_API_KEY". 
                                      Defaults to None.
            model_name (str, optional): The name of the Gemini model to use. 
                                        Defaults to "gemini-1.5-flash-exp-0827".
            temperature (float, optional): The temperature parameter for the model. Defaults to 1.
            top_p (float, optional): The top_p parameter for the model. Defaults to 0.95.
            top_k (int, optional): The top_k parameter for the model. Defaults to 64.
            max_output_tokens (int, optional): The maximum number of output tokens. Defaults to 8192.
            is_conversation (bool, optional): Flag for chatting conversationally. Defaults to True.
            timeout (int, optional): Http request timeout. Defaults to 30.
            intro (str, optional): Conversation introductory prompt. Defaults to None.
            filepath (str, optional): Path to file containing conversation history. Defaults to None.
            update_file (bool, optional): Add new prompts and responses to the file. Defaults to True.
            proxies (dict, optional): Http request proxies. Defaults to {}.
            history_offset (int, optional): Limit conversation history to this number of last texts. Defaults to 10250.
            act (str|int, optional): Awesome prompt key or index. (Used as intro). Defaults to None.
            system_instruction (str, optional): System instruction to guide the AI's behavior. 
                                                Defaults to "You are a helpful and informative AI assistant.".
        """
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.max_output_tokens = max_output_tokens
        self.system_instruction = system_instruction
        self.safety_settings = safety_settings if safety_settings else {}
        self.session = requests.Session()  # Not directly used for Gemini API calls, but can be used for other requests
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_output_tokens
        self.timeout = timeout
        self.last_response = {}

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
        self.session.proxies = proxies

        # Configure the Gemini API
        genai.configure(api_key=self.api_key)

        # Create the model with generation config
        self.generation_config = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "max_output_tokens": self.max_output_tokens,
            "response_mime_type": "text/plain",
        }

        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=self.generation_config,
            safety_settings=self.safety_settings,
            system_instruction=self.system_instruction,
        )

        # Start the chat session
        self.chat_session = self.model.start_chat()

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> dict:
        """Chat with AI

        Args:
            prompt (str): Prompt to be send.
            stream (bool, optional): Not used for Gemini API. Defaults to False.
            raw (bool, optional): Not used for Gemini API. Defaults to False.
            optimizer (str, optional): Prompt optimizer name - `[code, shell_command]`. Defaults to None.
            conversationally (bool, optional): Chat conversationally when using optimizer. Defaults to False.
        Returns:
           dict : {}
        ```json
        {
           "text" : "How may I assist you today?"
        }
        ```
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

        # Send the message to the chat session and get the response
        response = self.chat_session.send_message(conversation_prompt)
        self.last_response.update(dict(text=response.text))
        self.conversation.update_chat_history(
            prompt, self.get_message(self.last_response)
        )
        return self.last_response 

    def chat(
        self,
        prompt: str,
        stream: bool = False,  # Streaming not supported by the current google-generativeai library
        optimizer: str = None,
        conversationally: bool = False,
    ) -> str:
        """Generate response `str`

        Args:
            prompt (str): Prompt to be send.
            stream (bool, optional): Not used for Gemini API. Defaults to False.
            optimizer (str, optional): Prompt optimizer name - `[code, shell_command]`. Defaults to None.
            conversationally (bool, optional): Chat conversationally when using optimizer. Defaults to False.
        Returns:
            str: Response generated
        """
        return self.get_message(
            self.ask(
                prompt,
                optimizer=optimizer,
                conversationally=conversationally,
            )
        )

    def get_message(self, response: dict) -> str:
        """Retrieves message only from response

        Args:
            response (dict): Response generated by `self.ask`

        Returns:
            str: Message extracted
        """
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response["text"]
if __name__ == "__main__":
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    ai = GEMINIAPI(api_key="" , safety_settings=safety_settings)
    res = ai.chat(input(">>> "))
    for r in res:
        print(r, end="", flush=True)
