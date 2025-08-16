# This file marks the directory as a Python package.
from .deepinfra import *
## glider import removed
from .chatgptclone import *
from .x0gpt import *
from .wisecat import *
from .venice import *
from .exaai import *
from .scirachat import *
from .llmchatco import *
from .yep import * # Add YEPCHAT
from .heckai import *
from .sonus import *
from .exachat import *
from .netwrck import *
from .standardinput import *
from .writecream import *
from .toolbaz import *
from .opkfc import *
from .chatgpt import *
from .textpollinations import *
from .typefully import * # Add TypefullyAI
from .e2b import *
from .multichat import * # Add MultiChatAI
from .ai4chat import * # Add AI4Chat
from .mcpcore import *
from .flowith import *
from .chatsandbox import *
from .flowith import *
from .Cloudflare import *
from .NEMOTRON import *
from .BLACKBOXAI import *
from .copilot import * # Add Microsoft Copilot
from .TwoAI import *
from .oivscode import * # Add OnRender provider
from .Qwen3 import *
from .FalconH1 import *
from .PI import *  # Add PI.ai provider
from .TogetherAI import *  # Add TogetherAI provider
from .xenai import *  # Add XenAI provider
from .GeminiProxy import *  # Add GeminiProxy provider
from .friendli import *
from .monochat import *
from .MiniMax import *  # Add MiniMaxAI provider
from .qodo import *  # Add QodoAI provider
from .kimi import *  # Add Kimi provider
from .gptoss import *  # Add GPT-OSS provider
from .refact import *  # Add Refact provider
# Export auto-proxy functionality
from .autoproxy import (
    get_auto_proxy,
    get_proxy_dict,
    get_working_proxy,
    test_proxy,
    get_proxy_stats,
    refresh_proxy_cache,
    set_proxy_cache_duration,
    ProxyAutoMeta
)