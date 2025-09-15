import json
import logging
import time
import urllib
import uuid
from typing import Dict, Generator, List, Union

import random
from curl_cffi import CurlError
from curl_cffi.requests import Session
from webscout.scout import Scout

from webscout.AIutel import Optimizers
from webscout.AIutel import Conversation
from webscout.AIutel import AwesomePrompts
from webscout.AIbase import Provider
from webscout import exceptions
from webscout.litagent import LitAgent as Lit
MAX_RETRIES = 3

def generate_offline_threading_id() -> str:
    """
    Generates an offline threading ID.

    Returns:
        str: The generated offline threading ID.
    """
    # Maximum value for a 64-bit integer in Python
    max_int = (1 << 64) - 1
    mask22_bits = (1 << 22) - 1

    # Function to get the current timestamp in milliseconds
    def get_current_timestamp():
        return int(time.time() * 1000)

    # Function to generate a random 64-bit integer
    def get_random_64bit_int():
        return random.getrandbits(64)

    # Combine timestamp and random value
    def combine_and_mask(timestamp, random_value):
        shifted_timestamp = timestamp << 22
        masked_random = random_value & mask22_bits
        return (shifted_timestamp | masked_random) & max_int

    timestamp = get_current_timestamp()
    random_value = get_random_64bit_int()
    threading_id = combine_and_mask(timestamp, random_value)

    return str(threading_id)


def extract_value(text: str, start_str: str, end_str: str) -> str:
    """
    Helper function to extract a specific value from the given text using a key.

    Args:
        text (str): The text from which to extract the value.
        start_str (str): The starting key.
        end_str (str): The ending key.

    Returns:
        str: The extracted value.
    """
    start = text.find(start_str) + len(start_str)
    end = text.find(end_str, start)
    return text[start:end]


def format_response(response: dict) -> str:
    """
    Formats the response from Meta AI to remove unnecessary characters.

    Args:
        response (dict): The dictionnary containing the response to format.

    Returns:
        str: The formatted response.
    """
    text = ""
    for content in (
        response.get("data", {})
        .get("node", {})
        .get("bot_response_message", {})
        .get("composed_text", {})
        .get("content", [])
    ):
        text += content["text"] + "\n"
    return text


# Function to perform the login
def get_fb_session(email, password, proxies=None):
    login_url = "https://mbasic.facebook.com/login/"
    headers = {
        "authority": "mbasic.facebook.com",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "en-US,en;q=0.9",
        "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": Lit().random(),
    }
    # Create a session
    session = Session()
    if proxies:
        session.proxies = proxies

    # Send the GET request
    response = session.get(login_url, headers=headers)

    # Use Scout for parsing instead of BeautifulSoup
    scout = Scout(response.text)

    # Parse necessary parameters from the login form
    lsd = scout.find_first('input[name="lsd"]').get('value')
    jazoest = scout.find_first('input[name="jazoest"]').get('value')
    li = scout.find_first('input[name="li"]').get('value')
    m_ts = scout.find_first('input[name="m_ts"]').get('value')

    # Define the URL and body for the POST request to submit the login form
    post_url = "https://mbasic.facebook.com/login/device-based/regular/login/?refsrc=deprecated&lwv=100"
    data = {
        "lsd": lsd,
        "jazoest": jazoest,
        "m_ts": m_ts,
        "li": li,
        "try_number": "0",
        "unrecognized_tries": "0",
        "email": email,
        "pass": password,
        "login": "Log In",
        "bi_xrwh": "0",
    }

    headers = {
        "authority": "mbasic.facebook.com",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "content-type": "application/x-www-form-urlencoded",
        "cookie": f"datr={response.cookies.get('datr')}; sb={response.cookies.get('sb')}; ps_n=1; ps_l=1",
        "dpr": "2",
        "origin": "https://mbasic.facebook.com",
        "pragma": "no-cache",
        "referer": "https://mbasic.facebook.com/login/",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": Lit().random(),
        "viewport-width": "1728",
    }

    # Send the POST request
    result = session.post(post_url, headers=headers, data=data)
    if "sb" not in session.cookies:
        raise exceptions.FacebookInvalidCredentialsException(
            "Was not able to login to Facebook. Please check your credentials. "
            "You may also have been rate limited. Try to connect to Facebook manually."
        )

    cookies = {
        **result.cookies.get_dict(),
        "sb": session.cookies["sb"],
        "xs": session.cookies["xs"],
        "fr": session.cookies["fr"],
        "c_user": session.cookies["c_user"],
    }

    response_login = {
        "cookies": cookies,
        "headers": result.headers,
        "response": response.text,
    }
    meta_ai_cookies = get_cookies()

    url = "https://www.meta.ai/state/"

    payload = f'__a=1&lsd={meta_ai_cookies["lsd"]}'
    headers = {
        "authority": "www.meta.ai",
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "content-type": "application/x-www-form-urlencoded",
        "cookie": f'ps_n=1; ps_l=1; dpr=2; _js_datr={meta_ai_cookies["_js_datr"]}; abra_csrf={meta_ai_cookies["abra_csrf"]}; datr={meta_ai_cookies["datr"]};; ps_l=1; ps_n=1',
        "origin": "https://www.meta.ai",
        "pragma": "no-cache",
        "referer": "https://www.meta.ai/",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": Lit().random(),
        "viewport-width": "1728",
    }

    # Create a new session for this request
    req_session = Session()
    if proxies:
        req_session.proxies = proxies

    response = req_session.post(url, headers=headers, data=payload)

    state = extract_value(response.text, start_str='"state":"', end_str='"')

    url = f"https://www.facebook.com/oidc/?app_id=1358015658191005&scope=openid%20linking&response_type=code&redirect_uri=https%3A%2F%2Fwww.meta.ai%2Fauth%2F&no_universal_links=1&deoia=1&state={state}"
    payload = {}
    headers = {
        "authority": "www.facebook.com",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "cookie": f"datr={response_login['cookies']['datr']}; sb={response_login['cookies']['sb']}; c_user={response_login['cookies']['c_user']}; xs={response_login['cookies']['xs']}; fr={response_login['cookies']['fr']}; m_page_voice={response_login['cookies']['m_page_voice']}; abra_csrf={meta_ai_cookies['abra_csrf']};",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "cross-site",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": Lit().random(),
    }

    # Create a new session for Facebook
    fb_session = Session()
    if proxies:
        fb_session.proxies = proxies

    response = fb_session.get(url, headers=headers, data=payload, allow_redirects=False)

    next_url = response.headers["Location"]

    url = next_url

    payload = {}
    headers = {
        "User-Agent": Lit().random(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.meta.ai/",
        "Connection": "keep-alive",
        "Cookie": f'dpr=2; abra_csrf={meta_ai_cookies["abra_csrf"]}; datr={meta_ai_cookies["_js_datr"]}',
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "TE": "trailers",
    }
    fb_session.get(url, headers=headers, data=payload)
    cookies = fb_session.cookies.get_dict()
    if "abra_sess" not in cookies:
        raise exceptions.FacebookInvalidCredentialsException(
            "Was not able to login to Facebook. Please check your credentials. "
            "You may also have been rate limited. Try to connect to Facebook manually."
        )
    logging.info("Successfully logged in to Facebook.")
    return cookies


def get_cookies() -> dict:
    """
    Extracts necessary cookies from the Meta AI main page.

    Returns:
        dict: A dictionary containing essential cookies.
    """
    # Create a session
    session = Session()

    response = session.get(
        "https://www.meta.ai/",
    )

    cookies = {
        "_js_datr": extract_value(
            response.text, start_str='_js_datr":{"value":"', end_str='",'
        ),
        "datr": extract_value(
            response.text, start_str='datr":{"value":"', end_str='",'
        ),
        "lsd": extract_value(
            response.text, start_str='"LSD",[],{"token":"', end_str='"}'
        ),
        "fb_dtsg": extract_value(
            response.text, start_str='DTSGInitData",[],{"token":"', end_str='"'
        ),
        "abra_csrf": extract_value(
            response.text, start_str='abra_csrf":{"value":"', end_str='",'
        )
    }
    return cookies

class Meta(Provider):
    """
    A class to interact with the Meta AI API to obtain and use access tokens for sending
    and receiving messages from the Meta AI Chat API.
    """
    required_auth = False
    def __init__(
        self,
        fb_email: str = None,
        fb_password: str = None,
        proxy: dict = None,
        is_conversation: bool = True,
        max_tokens: int = 600,
        timeout: int = 30,
        intro: str = None,
        filepath: str = None,
        update_file: bool = True,
        proxies: dict = {},
        history_offset: int = 10250,
        act: str = None,
    ):
        """
        Initializes the Meta AI API with given parameters.

        Args:
            fb_email (str, optional): Your Facebook email address. Defaults to None.
            fb_password (str, optional): Your Facebook password. Defaults to None.
            proxy (dict, optional): Proxy settings for requests. Defaults to None.
            is_conversation (bool, optional): Flag for chatting conversationally. Defaults to True.
            max_tokens (int, optional): Maximum number of tokens to be generated upon completion. Defaults to 600.
            timeout (int, optional): Http request timeout. Defaults to 30.
            intro (str, optional): Conversation introductory prompt. Defaults to None.
            filepath (str, optional): Path to file containing conversation history. Defaults to None.
            update_file (bool, optional): Add new prompts and responses to the file. Defaults to True.
            proxies (dict, optional): Http request proxies. Defaults to {}.
            history_offset (int, optional): Limit conversation history to this number of last texts. Defaults to 10250.
            act (str|int, optional): Awesome prompt key or index. (Used as intro). Defaults to None.
        """
        self.session = Session()
        self.session.headers.update(
            {
                "user-agent": Lit().random(),
            }
        )
        self.access_token = None
        self.fb_email = fb_email
        self.fb_password = fb_password
        self.proxy = proxy
        if self.proxy and not self.check_proxy():
            raise ConnectionError(
                "Unable to connect to proxy. Please check your proxy settings."
            )
        self.is_conversation = is_conversation
        self.max_tokens_to_sample = max_tokens
        self.timeout = timeout
        self.last_response = {}
        self.is_authed = fb_password is not None and fb_email is not None
        self.cookies = self.get_cookies()
        self.external_conversation_id = None
        self.offline_threading_id = None

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

    def check_proxy(self, test_url: str = "https://api.ipify.org/?format=json") -> bool:
        """
        Checks the proxy connection by making a request to a test URL.

        Args:
            test_url (str): A test site from which we check that the proxy is installed correctly.

        Returns:
            bool: True if the proxy is working, False otherwise.
        """
        try:
            response = self.session.get(test_url, proxies=self.proxy, timeout=10)
            if response.status_code == 200:
                self.session.proxies = self.proxy
                return True
            return False
        except CurlError:
            return False

    def get_access_token(self) -> str:
        """
        Retrieves an access token using Meta's authentication API.

        Returns:
            str: A valid access token.
        """

        if self.access_token:
            return self.access_token

        url = "https://www.meta.ai/api/graphql/"
        payload = {
            "lsd": self.cookies["lsd"],
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": "useAbraAcceptTOSForTempUserMutation",
            "variables": {
                "dob": "1999-01-01",
                "icebreaker_type": "TEXT",
                "__relay_internal__pv__WebPixelRatiorelayprovider": 1,
            },
            "doc_id": "7604648749596940",
        }
        payload = urllib.parse.urlencode(payload)  # noqa
        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "cookie": f'_js_datr={self.cookies["_js_datr"]}; '
            f'abra_csrf={self.cookies["abra_csrf"]}; datr={self.cookies["datr"]};',
            "sec-fetch-site": "same-origin",
            "x-fb-friendly-name": "useAbraAcceptTOSForTempUserMutation",
        }

        response = self.session.post(url, headers=headers, data=payload)

        try:
            auth_json = response.json()
        except json.JSONDecodeError:
            raise exceptions.FacebookRegionBlocked(
                "Unable to receive a valid response from Meta AI. This is likely due to your region being blocked. "
                "Try manually accessing https://www.meta.ai/ to confirm."
            )

        access_token = auth_json["data"]["xab_abra_accept_terms_of_service"][
            "new_temp_user_auth"
        ]["access_token"]

        # Need to sleep for a bit, for some reason the API doesn't like it when we send request too quickly
        # (maybe Meta needs to register Cookies on their side?)
        time.sleep(1)

        return access_token

    def ask(
        self,
        prompt: str,
        stream: bool = False,
        raw: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> Union[Dict, Generator[Dict, None, None]]:
        """
        Sends a message to the Meta AI and returns the response.

        Args:
            prompt (str): The prompt to send.
            stream (bool): Whether to stream the response or not. Defaults to False.
            raw (bool, optional): Stream back raw response as received. Defaults to False.
            optimizer (str, optional): Prompt optimizer name - `[code, shell_command]`. Defaults to None.
            conversationally (bool, optional): Chat conversationally when using optimizer. Defaults to False.
        Returns:
            Union[Dict, Generator[Dict, None, None]]: A dictionary containing the response message and sources, or a generator yielding such dictionaries.
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

        if not self.is_authed:
            self.access_token = self.get_access_token()
            auth_payload = {"access_token": self.access_token}
            url = "https://graph.meta.ai/graphql?locale=user"

        else:
            auth_payload = {"fb_dtsg": self.cookies["fb_dtsg"]}
            url = "https://www.meta.ai/api/graphql/"

        if not self.external_conversation_id:
            external_id = str(uuid.uuid4())
            self.external_conversation_id = external_id
        payload = {
            **auth_payload,
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": "useAbraSendMessageMutation",
            "variables": json.dumps(
                {
                    "message": {"sensitive_string_value": conversation_prompt},
                    "externalConversationId": self.external_conversation_id,
                    "offlineThreadingId": generate_offline_threading_id(),
                    "suggestedPromptIndex": None,
                    "flashVideoRecapInput": {"images": []},
                    "flashPreviewInput": None,
                    "promptPrefix": None,
                    "entrypoint": "ABRA__CHAT__TEXT",
                    "icebreaker_type": "TEXT",
                    "__relay_internal__pv__AbraDebugDevOnlyrelayprovider": False,
                    "__relay_internal__pv__WebPixelRatiorelayprovider": 1,
                }
            ),
            "server_timestamps": "true",
            "doc_id": "7783822248314888",
        }
        payload = urllib.parse.urlencode(payload)  # noqa
        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "x-fb-friendly-name": "useAbraSendMessageMutation",
        }
        if self.is_authed:
            headers["cookie"] = f'abra_sess={self.cookies["abra_sess"]}'
            # Recreate the session to avoid cookie leakage when user is authenticated
            self.session = Session()
            self.session.proxies = self.proxy

        if stream:

            def for_stream():
                response = self.session.post(
                    url, headers=headers, data=payload, stream=True, timeout=self.timeout
                )
                if not response.ok:
                    raise exceptions.FailedToGenerateResponseError(
                        f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                    )

                lines = response.iter_lines()
                is_error = json.loads(next(lines))
                if len(is_error.get("errors", [])) > 0:
                    raise exceptions.FailedToGenerateResponseError(
                        f"Failed to generate response - {response.text}"
                    )
                final_message = None
                for line in lines:
                    if line:
                        json_line = json.loads(line)
                        extracted_data = self.extract_data(json_line)
                        if not extracted_data.get("message"):
                            continue
                        self.last_response.update(extracted_data)
                        final_message = extracted_data  # Always keep the latest
                if final_message:
                    yield final_message if not raw else json.dumps(final_message)
                    self.conversation.update_chat_history(
                        prompt, self.get_message(self.last_response)
                    )

            return for_stream()
        else:
            response = self.session.post(
                url, headers=headers, data=payload, timeout=self.timeout
            )
            if not response.ok:
                raise exceptions.FailedToGenerateResponseError(
                    f"Failed to generate response - ({response.status_code}, {response.reason}) - {response.text}"
                )
            raw_response = response.text
            last_streamed_response = self.extract_last_response(raw_response)
            if not last_streamed_response:
                raise exceptions.FailedToGenerateResponseError(
                    f"Failed to generate response - {response.text}"
                )

            extracted_data = self.extract_data(last_streamed_response)
            self.last_response.update(extracted_data)
            self.conversation.update_chat_history(
                prompt, self.get_message(self.last_response)
            )
            return extracted_data

    def chat(
        self,
        prompt: str,
        stream: bool = False,
        optimizer: str = None,
        conversationally: bool = False,
    ) -> str:
        """
        Sends a message to the Meta AI and returns the response.

        Args:
            prompt (str): The message to send.
            stream (bool): Whether to stream the response or not. Defaults to False.
            optimizer (str, optional): Prompt optimizer name - `[code, shell_command]`. Defaults to None.
            conversationally (bool, optional): Chat conversationally when using optimizer. Defaults to False.

        Returns:
            str: The response message.
        """

        def for_stream():
            for response in self.ask(
                prompt, True, optimizer=optimizer, conversationally=conversationally
            ):
                yield self.get_message(response)

        def for_non_stream():
            return self.get_message(
                self.ask(
                    prompt,
                    False,
                    optimizer=optimizer,
                    conversationally=conversationally,
                )
            )

        return for_stream() if stream else for_non_stream()

    def extract_last_response(self, response: str) -> Dict:
        """
        Extracts the last response from the Meta AI API.

        Args:
            response (str): The response to extract the last response from.

        Returns:
            dict: A dictionary containing the last response.
        """
        last_streamed_response = None
        for line in response.split("\n"):
            try:
                json_line = json.loads(line)
            except json.JSONDecodeError:
                continue

            bot_response_message = (
                json_line.get("data", {})
                .get("node", {})
                .get("bot_response_message", {})
            )
            chat_id = bot_response_message.get("id")
            if chat_id:
                external_conversation_id, offline_threading_id, _ = chat_id.split("_")
                self.external_conversation_id = external_conversation_id
                self.offline_threading_id = offline_threading_id

            streaming_state = bot_response_message.get("streaming_state")
            if streaming_state == "OVERALL_DONE":
                last_streamed_response = json_line

        return last_streamed_response

    def extract_data(self, json_line: dict) -> Dict:
        """
        Extract data and sources from a parsed JSON line.

        Args:
            json_line (dict): Parsed JSON line.

        Returns:
            dict: A dictionary containing the response message, sources, and media.
        """
        bot_response_message = (
            json_line.get("data", {}).get("node", {}).get("bot_response_message", {})
        )
        response = format_response(response=json_line)
        fetch_id = bot_response_message.get("fetch_id")
        sources = self.fetch_sources(fetch_id) if fetch_id else []
        medias = self.extract_media(bot_response_message)
        return {"message": response, "sources": sources, "media": medias}

    def extract_media(self, json_line: dict) -> List[Dict]:
        """
        Extract media from a parsed JSON line.

        Args:
            json_line (dict): Parsed JSON line.

        Returns:
            list: A list of dictionaries containing the extracted media.
        """
        medias = []
        imagine_card = json_line.get("imagine_card", {})
        session = imagine_card.get("session", {}) if imagine_card else {}
        media_sets = (
            (json_line.get("imagine_card", {}).get("session", {}).get("media_sets", []))
            if imagine_card and session
            else []
        )
        for media_set in media_sets:
            imagine_media = media_set.get("imagine_media", [])
            for media in imagine_media:
                medias.append(
                    {
                        "url": media.get("uri"),
                        "type": media.get("media_type"),
                        "prompt": media.get("prompt"),
                    }
                )
        return medias

    def get_cookies(self) -> dict:
        """
        Extracts necessary cookies from the Meta AI main page.

        Returns:
            dict: A dictionary containing essential cookies.
        """
        headers = {}
        if self.fb_email is not None and self.fb_password is not None:
            fb_session = get_fb_session(self.fb_email, self.fb_password, self.proxy)
            headers = {"cookie": f"abra_sess={fb_session['abra_sess']}"}

        response = self.session.get(
            url="https://www.meta.ai/",
            headers=headers,
            proxies=self.proxy,
        )

        cookies = {
            "_js_datr": extract_value(
                response.text, start_str='_js_datr":{"value":"', end_str='",'
            ),
            "datr": extract_value(
                response.text, start_str='datr":{"value":"', end_str='",'
            ),
            "lsd": extract_value(
                response.text, start_str='"LSD",[],{"token":"', end_str='"}'
            ),
            "fb_dtsg": extract_value(
                response.text, start_str='DTSGInitData",[],{"token":"', end_str='"'
            ),
        }

        if len(headers) > 0:
            cookies["abra_sess"] = fb_session["abra_sess"]
        else:
            cookies["abra_csrf"] = extract_value(
                response.text, start_str='abra_csrf":{"value":"', end_str='",'
            )
        return cookies

    def fetch_sources(self, fetch_id: str) -> List[Dict]:
        """
        Fetches sources from the Meta AI API based on the given query.

        Args:
            fetch_id (str): The fetch ID to use for the query.

        Returns:
            list: A list of dictionaries containing the fetched sources.
        """

        url = "https://graph.meta.ai/graphql?locale=user"
        payload = {
            "access_token": self.access_token,
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": "AbraSearchPluginDialogQuery",
            "variables": json.dumps({"abraMessageFetchID": fetch_id}),
            "server_timestamps": "true",
            "doc_id": "6946734308765963",
        }

        payload = urllib.parse.urlencode(payload)  # noqa

        headers = {
            "authority": "graph.meta.ai",
            "accept-language": "en-US,en;q=0.9,fr-FR;q=0.8,fr;q=0.7",
            "content-type": "application/x-www-form-urlencoded",
            "cookie": f'dpr=2; abra_csrf={self.cookies.get("abra_csrf")}; datr={self.cookies.get("datr")}; ps_n=1; ps_l=1',
            "x-fb-friendly-name": "AbraSearchPluginDialogQuery",
        }

        response = self.session.post(url, headers=headers, data=payload)
        response_json = response.json()
        message = response_json.get("data", {}).get("message", {})
        search_results = (
            (response_json.get("data", {}).get("message", {}).get("searchResults"))
            if message
            else None
        )
        if search_results is None:
            return []

        references = search_results["references"]
        return references

    def get_message(self, response: dict) -> str:
        """Retrieves message only from response

        Args:
            response (dict): Response generated by `self.ask`

        Returns:
            str: Message extracted
        """
        assert isinstance(response, dict), "Response should be of dict data-type only"
        return response["message"]

if __name__ == "__main__":
    Meta = Meta()
    ai = Meta.chat("hi")
    for chunk in ai:
        print(chunk, end="", flush=True)
