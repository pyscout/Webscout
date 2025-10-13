from __future__ import annotations

from ....litagent import LitAgent
from curl_cffi.requests import Session


class YepBase:
    """Base class for Yep search engines."""

    def __init__(
        self,
        timeout: int = 20,
        proxies: dict[str, str] | None = None,
        verify: bool = True,
        impersonate: str = "chrome110",
    ):
        self.base_url = "https://api.yep.com/fs/2/search"
        self.timeout = timeout
        self.session = Session(
            proxies=proxies,
            verify=verify,
            impersonate=impersonate,
            timeout=timeout,
        )
        self.session.headers.update(
            {
                **LitAgent().generate_fingerprint(),
                "Origin": "https://yep.com",
                "Referer": "https://yep.com/",
            }
        )

