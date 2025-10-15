"""Base class for Bing search implementations."""

from __future__ import annotations

from ....litagent import LitAgent
from curl_cffi.requests import Session


class BingBase:
    """Base class for Bing search engines."""

    def __init__(
        self,
        timeout: int = 10,
        proxies: dict[str, str] | None = None,
        verify: bool = True,
        lang: str = "en-US",
        sleep_interval: float = 0.0,
        impersonate: str = "chrome110",
    ):
        self.timeout = timeout
        self.proxies = proxies
        self.verify = verify
        self.lang = lang
        self.sleep_interval = sleep_interval
        self.base_url = "https://www.bing.com"
        self.session = Session(
            proxies=proxies,
            verify=verify,
            timeout=timeout,
            impersonate=impersonate,
        )
        self.session.headers.update(LitAgent().generate_fingerprint())