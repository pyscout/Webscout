# webscout/__init__.py

from .webscout_search import WEBS
from .webscout_search_async import AsyncWEBS
from .version import __version__
from .DWEBS import *
from .tempid import *
from .Provider import *
from .Provider.TTI import *
from .Provider.TTS import *
from .Provider.AISEARCH import *
from .Extra import *
from .Litlogger import *
from .optimizers import *
from .swiftcli import *
from .litagent import LitAgent
from .scout import *
from .zeroart import *
from .yep_search import *
# # Import litprinter components for direct access from webscout
# from .litprinter import lit, litprint, ic, install, uninstall
agent = LitAgent()

__repo__ = "https://github.com/OEvortex/Webscout"

# Add update checker
from .update_checker import check_for_updates
try:
    update_message = check_for_updates()
    if update_message:
        print(update_message)
except Exception:
    pass  # Silently handle any update check errors

import logging
logging.getLogger("webscout").addHandler(logging.NullHandler())

# Import models for easy access
from .models import model
