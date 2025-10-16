import requests
import time
import tempfile
import os
from typing import Optional
from webscout.Provider.TTI.utils import ImageData, ImageResponse
from webscout.Provider.TTI.base import TTICompatibleProvider, BaseImages
from io import BytesIO
from webscout.litagent import LitAgent
from webscout.scout import Scout

try:
    from PIL import Image
except ImportError:
    Image = None

class Images(BaseImages):
    def __init__(self, client):
        self._client = client

    def create(
        self,
        *,
        model: str = "dalle",
        prompt: str,
        n: int = 1,
        size: str = "1024x1024",
        response_format: str = "url",
        user: Optional[str] = None,
        style: str = "none",
        aspect_ratio: str = "1:1",
        timeout: int = 60,
        image_format: str = "png",
        seed: Optional[int] = None,
        **kwargs
    ) -> ImageResponse:
        if not prompt:
            raise ValueError("Parameter 'prompt' is required")
        if Image is None:
            raise ImportError("Pillow (PIL) is required for image format conversion.")
        agent = LitAgent()
        session = self._client.session
        headers = self._client.headers
        images = []
        urls = []
        
        # Map model names to Bing model codes
        model_mapping = {
            "dalle": "0",
            "gpt4o": "1",
        }
        
        # Get the appropriate model code
        model_code = model_mapping.get(model.lower(), "4")
        
        for _ in range(n):
            data = {
                "q": prompt,
                "rt": "4",
                "mdl": model_code,
                "FORM": "GENCRE"
            }
            response = session.post(
                "https://www.bing.com/images/create",
                data=data,
                headers=headers,
                allow_redirects=False,
                timeout=timeout
            )
            redirect_url = response.headers.get("Location")
            if not redirect_url:
                raise Exception("Failed to get redirect URL")
            from urllib.parse import urlparse, parse_qs
            query = urlparse(redirect_url).query
            request_id = parse_qs(query).get("id", [None])[0]
            if not request_id:
                raise Exception("ID not found in URL")
            polling_url = f"https://www.bing.com/images/create/async/results/{request_id}?q={requests.utils.quote(prompt)}"
            attempts = 0
            img_url = None
            while attempts < 10:
                time.sleep(3)
                try:
                    poll_resp = session.get(polling_url, headers=headers, timeout=timeout)
                    scout = Scout(poll_resp.text, features='html.parser')
                    imgs = [img["src"].split("?")[0] for img in scout.select(".img_cont .mimg") if img.attrs.get("src")]
                    if imgs:
                        img_url = imgs[0]
                        break
                except Exception:
                    pass
                attempts += 1
            if not img_url:
                raise Exception("Failed to get images after polling.")
            img_bytes = session.get(img_url, headers=headers, timeout=timeout).content
            # Convert to png or jpeg in memory
            with BytesIO(img_bytes) as input_io:
                with Image.open(input_io) as im:
                    out_io = BytesIO()
                    if image_format.lower() == "jpeg":
                        im = im.convert("RGB")
                        im.save(out_io, format="JPEG")
                    else:
                        im.save(out_io, format="PNG")
                    img_bytes = out_io.getvalue()
            images.append(img_bytes)
            if response_format == "url":
                def upload_file_with_retry(img_bytes, image_format, max_retries=3):
                    ext = "jpg" if image_format.lower() == "jpeg" else "png"
                    for attempt in range(max_retries):
                        tmp_path = None
                        try:
                            with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                                tmp.write(img_bytes)
                                tmp.flush()
                                tmp_path = tmp.name
                            with open(tmp_path, "rb") as f:
                                files = {"fileToUpload": (f"image.{ext}", f, f"image/{ext}")}
                                data = {"reqtype": "fileupload", "json": "true"}
                                headers2 = {"User-Agent": agent.random()}
                                if attempt > 0:
                                    headers2["Connection"] = "close"
                                resp2 = requests.post(
                                    "https://catbox.moe/user/api.php",
                                    files=files,
                                    data=data,
                                    headers=headers2,
                                    timeout=timeout,
                                )
                                if resp2.status_code == 200 and resp2.text.strip():
                                    text = resp2.text.strip()
                                    if text.startswith("http"):
                                        return text
                                    try:
                                        result = resp2.json()
                                        if "url" in result:
                                            return result["url"]
                                    except Exception:
                                        if "http" in text:
                                            return text
                        except Exception:
                            if attempt < max_retries - 1:
                                time.sleep(1 * (attempt + 1))
                        finally:
                            if tmp_path and os.path.isfile(tmp_path):
                                try:
                                    os.remove(tmp_path)
                                except Exception:
                                    pass
                    return None
                def upload_file_alternative(img_bytes, image_format):
                    try:
                        ext = "jpg" if image_format.lower() == "jpeg" else "png"
                        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                            tmp.write(img_bytes)
                            tmp.flush()
                            tmp_path = tmp.name
                        try:
                            if not os.path.isfile(tmp_path):
                                return None
                            with open(tmp_path, "rb") as img_file:
                                files = {"file": img_file}
                                alt_resp = requests.post("https://0x0.st", files=files)
                                alt_resp.raise_for_status()
                                image_url = alt_resp.text.strip()
                                if not image_url.startswith("http"):
                                    return None
                                return image_url
                        except Exception:
                            return None
                        finally:
                            try:
                                os.remove(tmp_path)
                            except Exception:
                                pass
                    except Exception:
                        return None
                uploaded_url = upload_file_with_retry(img_bytes, image_format)
                if not uploaded_url:
                    uploaded_url = upload_file_alternative(img_bytes, image_format)
                if uploaded_url:
                    urls.append(uploaded_url)
                else:
                    raise RuntimeError(
                        "Failed to upload image to catbox.moe using all available methods"
                    )
        result_data = []
        if response_format == "url":
            for url in urls:
                result_data.append(ImageData(url=url))
        elif response_format == "b64_json":
            import base64
            for img in images:
                b64 = base64.b64encode(img).decode("utf-8")
                result_data.append(ImageData(b64_json=b64))
        else:
            raise ValueError("response_format must be 'url' or 'b64_json'")
        from time import time as _time
        return ImageResponse(created=int(_time()), data=result_data)

class BingImageAI(TTICompatibleProvider):
    AVAILABLE_MODELS = ["bing"]
    def __init__(self, cookie: Optional[str] = None):
        self.session = requests.Session()
        self.user_agent = LitAgent().random()
        self.headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "id-ID,id;q=0.9",
            "cache-control": "max-age=0",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://www.bing.com",
            "referer": "https://www.bing.com/images/create?&wlexpsignin=1",
            "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24", "Microsoft Edge Simulate";v="131", "Lemur";v="131"',
            "sec-ch-ua-mobile": "?1",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "navigate",
            "sec-fetch-dest": "document",
            "upgrade-insecure-requests": "1",
            "user-agent": self.user_agent,
        }
        self.session.headers.update(self.headers)
        self.cookie = cookie
        if cookie:
            self.session.cookies.set("_U", cookie, domain="bing.com")
        self.images = Images(self)
    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS
        return _ModelList()

if __name__ == "__main__":
    from rich import print
    client = BingImageAI(cookie="1Fw9daLSZzVBJXgevTDuc0jHZ60l4m5IiQEwjRCFOwEkpEBDmw3b8CEAALFSwZ1QBu-rATNkfD0i0gfJmVHeFlogqIriGwxNwT9T6fVREgAQD4_qn0VnQYP681NN4K80t6o-eJXnK1MBhdjxTIaok8173LGmLkEWLqHC0k3dYnF7m2kHRhf1dxjEH3WDI56hxiSPZtnggdzrfnuFAmOgCQQ")
    response = client.images.create(
        model="gpt4o",
        prompt="A cat riding a bicycle",
        response_format="url",
        n=4,
        timeout=30
    )
    print(response)
