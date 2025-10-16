<div align="center">
  <a href="https://github.com/pyscout/Webscout">
    <img src="https://img.shields.io/badge/WebScout-OpenAI%20Compatible%20Providers-4285F4?style=for-the-badge&logo=openai&logoColor=white" alt="WebScout OpenAI Compatible Providers">
  </a>
  <br/>
  <h1>WebScout OpenAI-Compatible Providers</h1>
  <p><strong>Seamlessly integrate with various AI providers using OpenAI-compatible interfaces</strong></p>

  <p>
    <img src="https://img.shields.io/badge/Python-3.7+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.7+">
    <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License: MIT">
    <img src="https://img.shields.io/badge/PRs-Welcome-brightgreen?style=flat-square" alt="PRs Welcome">
  </p>

  <p>
    Access multiple AI providers through a standardized OpenAI-compatible interface, making it easy to switch between providers without changing your code.
  </p>
</div>

## 🚀 Overview

The WebScout OpenAI-Compatible Providers module offers a standardized way to interact with various AI providers using the familiar OpenAI API structure. This makes it easy to:

- Use the same code structure across different AI providers
- Switch between providers without major code changes
- Leverage the OpenAI ecosystem of tools and libraries with alternative AI providers

## ⚙️ Available Providers

Currently, the following providers are implemented with OpenAI-compatible interfaces:

- DeepInfra
- Glider
- ChatGPTClone
- X0GPT
- WiseCat
- Venice
- ExaAI
- TypeGPT
- SciraChat
- LLMChatCo
- YEPCHAT
- HeckAI
- SonusAI
- ExaChat
- Netwrck
- StandardInput
- Writecream
- toolbaz
- UncovrAI
- OPKFC
- TextPollinations
- E2B
- MultiChatAI
- AI4Chat
- MCPCore
- TypefullyAI
- Flowith
- ChatSandbox
- Cloudflare
- NEMOTRON
- BLACKBOXAI
- Copilot
- TwoAI
- oivscode
- Qwen3
- TogetherAI
- PiAI
- FalconH1
- XenAI
- GeminiProxy
- MonoChat
- Friendli
- MiniMax
- QodoAI
- Kimi
- GptOss
## 💻 Usage Examples

Here are examples of how to use the OpenAI-compatible providers in your code.

### Basic Usage with DeepInfra

```python
from webscout.client import DeepInfra

# Initialize the client
client = DeepInfra()

# Create a completion (non-streaming)
response = client.chat.completions.create(
    model="meta-llama/Meta-Llama-3.1-8B-Instruct",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about Python programming."}
    ],
    temperature=0.7,
    max_tokens=500
)

# Print the response
print(response.choices[0].message.content)
```

### Basic Usage with Glider

```python
from webscout.client import Glider

# Initialize the client
client = Glider()

# Create a completion (non-streaming)
response = client.chat.completions.create(
    model="chat-llama-3-1-70b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about Python programming."}
    ],
    max_tokens=500
)

# Print the response
print(response.choices[0].message.content)
```

### Streaming Responses (Example with DeepInfra)

```python
from webscout.client import DeepInfra

# Initialize the client
client = DeepInfra()

# Create a streaming completion
stream = client.chat.completions.create(
    model="meta-llama/Meta-Llama-3.1-8B-Instruct",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a short poem about programming."}
    ],
    stream=True,
    temperature=0.7
)

# Process the streaming response
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add a newline at the end
```

### Streaming with Glider

```python
from webscout.client import Glider

# Initialize the client
client = Glider()

# Create a streaming completion
stream = client.chat.completions.create(
    model="chat-llama-3-1-70b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a short poem about programming."}
    ],
    stream=True
)

# Process the streaming response
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add a newline at the end
```

### Basic Usage with ChatGPTClone

```python
from webscout.client import ChatGPTClone

# Initialize the client
client = ChatGPTClone()

# Create a completion (non-streaming)
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about Python programming."}
    ],
    temperature=0.7
)

# Print the response
print(response.choices[0].message.content)
```

### Streaming with ChatGPTClone

```python
from webscout.client import ChatGPTClone

# Initialize the client
client = ChatGPTClone()

# Create a streaming completion
stream = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a short poem about programming."}
    ],
    stream=True
)

# Process the streaming response
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add a newline at the end
```

### Basic Usage with X0GPT

```python
from webscout.client import X0GPT

# Initialize the client
client = X0GPT()

# Create a completion (non-streaming)
response = client.chat.completions.create(
    model="gpt-4",  # Model name doesn't matter for X0GPT
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about Python programming."}
    ]
)

# Print the response
print(response.choices[0].message.content)
```

### Streaming with X0GPT

```python
from webscout.client import X0GPT

# Initialize the client
client = X0GPT()

# Create a streaming completion
stream = client.chat.completions.create(
    model="gpt-4",  # Model name doesn't matter for X0GPT
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a short poem about programming."}
    ],
    stream=True
)

# Process the streaming response
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add a newline at the end
```

### Basic Usage with WiseCat

```python
from webscout.client import WiseCat

# Initialize the client
client = WiseCat()

# Create a completion (non-streaming)
response = client.chat.completions.create(
    model="chat-model-small",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about Python programming."}
    ]
)

# Print the response
print(response.choices[0].message.content)
```

### Streaming with WiseCat

```python
from webscout.client import WiseCat

# Initialize the client
client = WiseCat()

# Create a streaming completion
stream = client.chat.completions.create(
    model="chat-model-small",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a short poem about programming."}
    ],
    stream=True
)

# Process the streaming response
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add a newline at the end
```

### Basic Usage with Venice

```python
from webscout.client import Venice

# Initialize the client
client = Venice(temperature=0.7, top_p=0.9)

# Create a completion (non-streaming)
response = client.chat.completions.create(
    model="mistral-31-24b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about Python programming."}
    ]
)

# Print the response
print(response.choices[0].message.content)
```

### Streaming with Venice

```python
from webscout.client import Venice

# Initialize the client
client = Venice()

# Create a streaming completion
stream = client.chat.completions.create(
    model="mistral-31-24b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a short poem about programming."}
    ],
    stream=True
)

# Process the streaming response
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add a newline at the end
```

### Basic Usage with ExaAI

```python
from webscout.client import ExaAI

# Initialize the client
client = ExaAI()

# Create a completion (non-streaming)
response = client.chat.completions.create(
    model="O3-Mini",
    messages=[
        # Note: ExaAI does not support system messages (they will be removed)
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi there! How can I help you today?"},
        {"role": "user", "content": "Tell me about Python programming."}
    ]
)

# Print the response
print(response.choices[0].message.content)
```

### Basic Usage with HeckAI

```python
from webscout.client import HeckAI

# Initialize the client
client = HeckAI(language="English")

# Create a completion (non-streaming)
response = client.chat.completions.create(
    model="google/gemini-2.0-flash-001",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about Python programming."}
    ]
)

# Print the response
print(response.choices[0].message.content)
```

### Streaming with HeckAI

```python
from webscout.client import HeckAI

# Initialize the client
client = HeckAI()

# Create a streaming completion
stream = client.chat.completions.create(
    model="google/gemini-2.0-flash-001",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a short poem about programming."}
    ],
    stream=True
)

# Process the streaming response
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add a newline at the end
```

### Streaming with ExaAI

```python
from webscout.client import ExaAI

# Initialize the client
client = ExaAI()

# Create a streaming completion
stream = client.chat.completions.create(
    model="O3-Mini",
    messages=[
        # Note: ExaAI does not support system messages (they will be removed)
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi there! How can I help you today?"},
        {"role": "user", "content": "Write a short poem about programming."}
    ],
    stream=True
)

# Process the streaming response
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add a newline at the end
```

### Basic Usage with TypeGPT

```python
from webscout.client import TypeGPT

# Initialize the client
client = TypeGPT()

# Create a completion (non-streaming)
response = client.chat.completions.create(
    model="chatgpt-4o-latest",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a short poem about programming."}
    ]
)

# Print the response
print(response.choices[0].message.content)
```

### Streaming with TypeGPT

```python
from webscout.client import TypeGPT

# Initialize the client
client = TypeGPT()

# Create a streaming completion
stream = client.chat.completions.create(
    model="chatgpt-4o-latest",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a short poem about programming."}
    ],
    stream=True
)

# Process the streaming response
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add a newline at the end
```

### Basic Usage with SciraChat

```python
from webscout.client import SciraChat

# Initialize the client
client = SciraChat()

# Create a completion (non-streaming)
response = client.chat.completions.create(
    model="scira-default",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about Python programming."}
    ]
)

# Print the response
print(response.choices[0].message.content)
```

### Streaming with SciraChat

```python
from webscout.client import SciraChat

# Initialize the client
client = SciraChat()

# Create a streaming completion
stream = client.chat.completions.create(
    model="scira-default",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a short poem about programming."}
    ],
    stream=True
)

# Process the streaming response
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add a newline at the end
```

### Basic Usage with FreeAIChat

```python
from webscout.client import FreeAIChat

# Initialize the client
client = FreeAIChat()

# Create a completion (non-streaming)
response = client.chat.completions.create(
    model="GPT 4o",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about Python programming."}
    ]
)

# Print the response
print(response.choices[0].message.content)
```

### Streaming with FreeAIChat

```python
from webscout.client import FreeAIChat

# Initialize the client
client = FreeAIChat()

# Create a streaming completion
stream = client.chat.completions.create(
    model="GPT 4o",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a short poem about programming."}
    ],
    stream=True
)

# Process the streaming response
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add a newline at the end
```

### Basic Usage with LLMChatCo

```python
from webscout.client import LLMChatCo

# Initialize the client
client = LLMChatCo()

# Create a completion (non-streaming)
response = client.chat.completions.create(
    model="gemini-flash-2.0",  # Default model
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about Python programming."}
    ],
    temperature=0.7
)

# Print the response
print(response.choices[0].message.content)
```

### Streaming with LLMChatCo

```python
from webscout.client import LLMChatCo

# Initialize the client
client = LLMChatCo()

# Create a streaming completion
stream = client.chat.completions.create(
    model="gemini-flash-2.0",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a short poem about programming."}
    ],
    stream=True
)

# Process the streaming response
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add a newline at the end
```

### Basic Usage with YEPCHAT

```python
from webscout.client import YEPCHAT

# Initialize the client
client = YEPCHAT()

# Create a completion (non-streaming)
response = client.chat.completions.create(
    model="DeepSeek-R1-Distill-Qwen-32B",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about Python programming."}
    ],
    temperature=0.7
)

# Print the response
print(response.choices[0].message.content)
```

### Basic Usage with SonusAI

```python
from webscout.client import SonusAI

# Initialize the client
client = SonusAI()

# Create a completion (non-streaming)
response = client.chat.completions.create(
    model="pro",  # Choose from 'pro', 'air', or 'mini'
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about Python programming."}
    ],
    reasoning=True  # Optional: Enable reasoning mode
)

# Print the response
print(response.choices[0].message.content)
```

### Streaming with YEPCHAT

```python
from webscout.client import YEPCHAT

# Initialize the client
client = YEPCHAT()

# Create a streaming completion
stream = client.chat.completions.create(
    model="Mixtral-8x7B-Instruct-v0.1",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a short poem about programming."}
    ],
    stream=True
)

# Process the streaming response
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add a newline at the end
```

### Streaming with SonusAI

```python
from webscout.client import SonusAI

# Initialize the client
client = SonusAI(timeout=60)

# Create a streaming completion
stream = client.chat.completions.create(
    model="air",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a short poem about programming."}
    ],
    stream=True
)

# Process the streaming response
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add a newline at the end
```

### Basic Usage with ExaChat

```python
from webscout.client import ExaChat

# Initialize the client
client = ExaChat()

# Create a completion (non-streaming)
response = client.chat.completions.create(
    model="exaanswer",  # Choose from many available models
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about Python programming."}
    ]
)

# Print the response
print(response.choices[0].message.content)
```

### Using Different ExaChat Providers

```python
from webscout.client import ExaChat

# Initialize the client
client = ExaChat(timeout=60)

# Use a Gemini model
gemini_response = client.chat.completions.create(
    model="gemini-2.0-flash",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain quantum computing in simple terms."}
    ]
)

# Use a Groq model
groq_response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[
        {"role": "user", "content": "Tell me about Python programming."}
    ]
)

# Print the response
print(response.choices[0].message.content)
```

### Streaming with Netwrck

```python
from webscout.client import Netwrck

# Initialize the client
client = Netwrck(timeout=60)

# Create a streaming completion
stream = client.chat.completions.create(
    model="openai/gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a short poem about programming."}
    ],
    stream=True
)

# Process the streaming response
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add a newline at the end
```

### Basic Usage with StandardInput

```python
from webscout.client import StandardInput

# Initialize the client
client = StandardInput()

# Create a completion (non-streaming)
response = client.chat.completions.create(
    model="standard-quick",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about Python programming."}
    ]
)

# Print the response
print(response.choices[0].message.content)
```

### Streaming with StandardInput

```python
from webscout.client import StandardInput

# Initialize the client
client = StandardInput()

# Create a streaming completion
stream = client.chat.completions.create(
    model="standard-reasoning",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Count from 1 to 5."}
    ],
    stream=True,
    enable_reasoning=True  # Enable reasoning capabilities
)

# Process the streaming response
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add a newline at the end
```

## 🔄 Response Format

All providers return responses that mimic the OpenAI API structure, ensuring compatibility with tools built for OpenAI.

### 📝 Non-streaming Response

```json
{
  "id": "chatcmpl-123abc",
  "object": "chat.completion",
  "created": 1677858242,
  "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
  "usage": {
    "prompt_tokens": 13,
    "completion_tokens": 7,
    "total_tokens": 20
  },
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "This is a response from the model."
      },
      "finish_reason": "stop",
      "index": 0
    }
  ]
}
```

### 📱 Streaming Response Chunks

```json
{
  "id": "chatcmpl-123abc",
  "object": "chat.completion.chunk",
  "created": 1677858242,
  "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
  "choices": [
    {
      "delta": {
        "content": "This "
      },
      "finish_reason": null,
      "index": 0
    }
  ]
}
```

## 🧩 Architecture

The OpenAI-compatible providers are built on a modular architecture:

- `base.py`: Contains abstract base classes that define the OpenAI-compatible interface
- `utils.py`: Provides data structures that mimic OpenAI's response format
- Provider-specific implementations (e.g., `deepinfra.py`): Implement the abstract interfaces for specific providers

This architecture makes it easy to add new providers while maintaining a consistent interface.

## 📝 Notes

- Some providers may require API keys for full functionality
- Not all OpenAI features are supported by all providers
- Response formats are standardized to match OpenAI's format, but the underlying content depends on the specific provider and model

## 🤝 Contributing

Want to add a new OpenAI-compatible provider? Follow these steps:

1.  Create a new file in the `webscout/Provider/OPENAI` directory
2.  Implement the `OpenAICompatibleProvider` interface
3.  Add appropriate tests
4.  Update this README with information about the new provider

## 📚 Related Documentation

- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [DeepInfra Documentation](https://deepinfra.com/docs)
- [Glider.so Website](https://glider.so/)
- [ChatGPT Clone Website](https://chatgpt-clone-ten-nu.vercel.app/)
- [X0GPT Website](https://x0-gpt.devwtf.in/)
- [WiseCat Website](https://wise-cat-groq.vercel.app/)
- [Venice AI Website](https://venice.ai/)
- [ExaAI Website](https://o3minichat.exa.ai/)
- [TypeGPT Website](https://chat.typegpt.net/)
- [SciraChat Website](https://scira.ai/)
- [FreeAIChat Website](https://freeaichatplayground.com/)
- [LLMChatCo Website](https://llmchat.co/)
- [Yep.com Website](https://yep.com/)
- [HeckAI Website](https://heck.ai/)
- [SonusAI Website](https://chat.sonus.ai/)
- [ExaChat Website](https://exa-chat.vercel.app/)
- [Netwrck Website](https://netwrck.com/)
- [StandardInput Website](https://chat.standard-input.com/)

<div align="center">
  <a href="https://t.me/PyscoutAI"><img alt="Telegram Group" src="https://img.shields.io/badge/Telegram%20Group-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white"></a>
  <a href="https://buymeacoffee.com/oevortex"><img alt="Buy Me A Coffee" src="https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buymeacoffee&logoColor=black"></a>
</div>
