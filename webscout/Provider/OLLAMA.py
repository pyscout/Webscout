from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts
from webscout.AIbase import Provider
from typing import AsyncGenerator, Dict, List, Optional, Union

try:
    from ollama import AsyncClient, Client, ResponseError
except ImportError as e:
    pass

class OLLAMA(Provider):
    required_auth = True
    def __init__(
        self,
        model: str = 'qwen2:0.5b',
        is_conversation: bool = True,
        max_tokens: int = 600,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
        system_prompt: str = "You are a helpful and friendly AI assistant.",
        host: str = 'http://localhost:11434',
        headers: Optional[Dict] = None,
    ):
        """Instantiates Ollama

        Args:
            model (str, optional): Model name. Defaults to 'qwen2:0.5b'.
            is_conversation (bool, optional): Flag for chatting conversationally. Defaults to True.
            max_tokens (int, optional): Maximum number of tokens to be generated upon completion. Defaults to 600.
            timeout (int, optional): Http request timeout. Defaults to 30.
            intro (str, optional): Conversation introductory prompt. Defaults to None.
            filepath (str, optional): Path to file containing conversation history. Defaults to None.
            update_file (bool, optional): Add new prompts and responses to the file. Defaults to True.
            proxies (dict, optional): Http request proxies. Defaults to {}.
            history_offset (int, optional): Limit conversation history to this number of last texts. Defaults to 10250.
            act (str|int, optional): Awesome prompt key or index. (Used as intro). Defaults to None.
            system_prompt (str, optional): System prompt for Ollama. Defaults to "You are a helpful and friendly AI assistant.".
            host (str, optional): Ollama host URL. Defaults to 'http://localhost:11434'.
            headers (dict, optional): Custom headers for requests. Defaults to None.
        """
        self.model = model
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = {}
        self.system_prompt = system_prompt
        self.client = Client(host=host, headers=headers)
        self.async_client = AsyncClient(host=host, headers=headers)

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

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        tools: Optional[List[Dict]] = None,
        images: Optional[List[str]] = None,
    ) -> Union[dict, AsyncGenerator]:
        """Chat with AI

        Args:
            prompt (str): Prompt to be send.
            stream (bool, optional): Flag for streaming response. Defaults to False.
            raw (bool, optional): Stream back raw response as received. Defaults to False.
            optimizer (str, optional): Prompt optimizer name - `[code, shell_command]`. Defaults to None.
            conversationally (bool, optional): Chat conversationally when using optimizer. Defaults to False.
            tools (List[Dict], optional): List of tools/functions to use. Defaults to None.
            images (List[str], optional): List of image paths or base64 encoded images. Defaults to None.
        Returns:
           Union[dict, AsyncGenerator] : ai content
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

        messages = [
            {'role': 'system', 'content': self.system_prompt},
            {'role': 'user', 'content': conversation_prompt}
        ]

        if images:
            messages[-1]['images'] = images

        try:
            def for_stream():
                stream = self.client.chat(
                    model=self.model,
                    messages=messages,
                    stream=True,
                    tools=tools
                )
                for chunk in stream:
                    yield chunk['message']['content'] if raw else dict(text=chunk['message']['content'])

            def for_non_stream():
                response = self.client.chat(
                    model=self.model,
                    messages=messages,
                    tools=tools
                )
                self.last_response.update(dict(text=response['message']['content']))
                self.conversation.update_chat_history(
                    prompt, self.get_message(self.last_response)
                )
                return self.last_response

            return for_stream() if stream else for_non_stream()
        except ResponseError as e:
            if e.status_code == 404:
                raise Exception(f"Model {self.model} not found. Please pull it first using `ollama pull {self.model}`")
            raise e

    async def aask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        tools: Optional[List[Dict]] = None,
        images: Optional[List[str]] = None,
    ) -> Union[dict, AsyncGenerator]:
        """Async version of ask method"""
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

        messages = [
            {'role': 'system', 'content': self.system_prompt},
            {'role': 'user', 'content': conversation_prompt}
        ]

        if images:
            messages[-1]['images'] = images

        try:
            async def for_stream():
                stream = await self.async_client.chat(
                    model=self.model,
                    messages=messages,
                    stream=True,
                    tools=tools
                )
                async for chunk in stream:
                    yield chunk['message']['content'] if raw else dict(text=chunk['message']['content'])

            async def for_non_stream():
                response = await self.async_client.chat(
                    model=self.model,
                    messages=messages,
                    tools=tools
                )
                self.last_response.update(dict(text=response['message']['content']))
                self.conversation.update_chat_history(
                    prompt, self.get_message(self.last_response)
                )
                return self.last_response

            return for_stream() if stream else for_non_stream()
        except ResponseError as e:
            if e.status_code == 404:
                raise Exception(f"Model {self.model} not found. Please pull it first using `ollama pull {self.model}`")
            raise e

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        tools: Optional[List[Dict]] = None,
        images: Optional[List[str]] = None,
    ) -> Union[str, AsyncGenerator]:
        """Generate response `str`
        Args:
            prompt (str): Prompt to be send.
            stream (bool, optional): Flag for streaming response. Defaults to False.
            optimizer (str, optional): Prompt optimizer name - `[code, shell_command]`. Defaults to None.
            conversationally (bool, optional): Chat conversationally when using optimizer. Defaults to False.
            tools (List[Dict], optional): List of tools/functions to use. Defaults to None.
            images (List[str], optional): List of image paths or base64 encoded images. Defaults to None.
        Returns:
            Union[str, AsyncGenerator]: Response generated
        """
        def for_stream():
            for response in self.ask(
                prompt, True, optimizer=optimizer, conversationally=conversationally,
                tools=tools, images=images
            ):
                yield self.get_message(response)

        def for_non_stream():
            return self.get_message(
                self.ask(
                    prompt,
                    False,
                    optimizer=optimizer,
                    conversationally=conversationally,
                    tools=tools,
                    images=images
                )
            )

        return for_stream() if stream else for_non_stream()

    async def achat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
        tools: Optional[List[Dict]] = None,
        images: Optional[List[str]] = None,
    ) -> Union[str, AsyncGenerator]:
        """Async version of chat method"""
        async def for_stream():
            async for response in await self.aask(
                prompt, True, optimizer=optimizer, conversationally=conversationally,
                tools=tools, images=images
            ):
                yield self.get_message(response)

        async def for_non_stream():
            return self.get_message(
                await self.aask(
                    prompt,
                    False,
                    optimizer=optimizer,
                    conversationally=conversationally,
                    tools=tools,
                    images=images
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
        return response["text"]

    def generate(
        self,
        prompt: str,
        stream: bool = False,
        **kwargs
    ) -> Union[dict, AsyncGenerator]:
        """Generate text using the model"""
        try:
            if stream:
                return self.client.generate(model=self.model, prompt=prompt, stream=True, **kwargs)
            return self.client.generate(model=self.model, prompt=prompt, **kwargs)
        except ResponseError as e:
            if e.status_code == 404:
                raise Exception(f"Model {self.model} not found. Please pull it first using `ollama pull {self.model}`")
            raise e

    async def agenerate(
        self,
        prompt: str,
        stream: bool = False,
        **kwargs
    ) -> Union[dict, AsyncGenerator]:
        """Async version of generate method"""
        try:
            if stream:
                return await self.async_client.generate(model=self.model, prompt=prompt, stream=True, **kwargs)
            return await self.async_client.generate(model=self.model, prompt=prompt, **kwargs)
        except ResponseError as e:
            if e.status_code == 404:
                raise Exception(f"Model {self.model} not found. Please pull it first using `ollama pull {self.model}`")
            raise e

    def list_models(self) -> List[dict]:
        """List all available models"""
        return self.client.list()

    def show_model(self, model: str = None) -> dict:
        """Show model details"""
        model = model or self.model
        return self.client.show(model)

    def pull_model(self, model: str = None) -> None:
        """Pull a model from Ollama"""
        model = model or self.model
        self.client.pull(model)

    def delete_model(self, model: str = None) -> None:
        """Delete a model"""
        model = model or self.model
        self.client.delete(model)

    def embed(
        self,
        input: Union[str, List[str]],
        model: str = None
    ) -> List[float]:
        """Generate embeddings for input text"""
        model = model or self.model
        return self.client.embed(model=model, input=input)

    async def aembed(
        self,
        input: Union[str, List[str]],
        model: str = None
    ) -> List[float]:
        """Async version of embed method"""
        model = model or self.model
        return await self.async_client.embed(model=model, input=input)

if __name__ == "__main__":
    # Example usage
    ai = OLLAMA(model="qwen2.5:0.5b")
    # ai.pull_model("qwen2.5:0.5b")
    # Basic chat
    response = ai.chat("write a poem about AI", stream=True)
    for chunk in response:
        print(chunk, end="", flush=True)
    
    # Vision example
    # response = ai.chat(
    #     "What's in this image?",
    #     images=["path/to/image.jpg"]
    # )
    # print(response)
    
    # Tools example
    def add_numbers(a: int, b: int) -> int:
        return a + b
    
    tools = [{
        'type': 'function',
        'function': {
            'name': 'add_numbers',
            'description': 'Add two numbers',
            'parameters': {
                'type': 'object',
                'properties': {
                    'a': {'type': 'integer'},
                    'b': {'type': 'integer'}
                },
                'required': ['a', 'b']
            }
        }
    }]
    
    response = ai.chat(
        "What is 5 plus 3?",
        tools=tools
    )
    print(response)