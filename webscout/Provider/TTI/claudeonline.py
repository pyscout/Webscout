import base64
import json
import os
import tempfile
import time
from io import BytesIO
from typing import Optional

import requests
from requests.exceptions import RequestException

from webscout.litagent import LitAgent
from webscout.Provider.TTI.base import BaseImages, TTICompatibleProvider
from webscout.Provider.TTI.utils import ImageData, ImageResponse

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
        model: str,
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
        **kwargs,
    ) -> ImageResponse:
        """
        Generate images using Claude Online's /imagine feature via Pollinations.ai.

        Args:
            model: Model to use (ignored, uses Pollinations.ai)
            prompt: The image generation prompt
            n: Number of images to generate (max 1 for Claude Online)
            size: Image size (supports various sizes)
            response_format: "url" or "b64_json"
            timeout: Request timeout in seconds
            image_format: Output format "png" or "jpeg"
            **kwargs: Additional parameters

        Returns:
            ImageResponse with generated image data
        """
        if Image is None:
            raise ImportError("Pillow (PIL) is required for image format conversion.")

        # Claude Online only supports 1 image per request
        if n > 1:
            raise ValueError("Claude Online only supports generating 1 image per request")

        # Parse size parameter
        width, height = self._parse_size(size)

        try:
            # Clean the prompt (remove command words if present)
            clean_prompt = self._clean_prompt(prompt)

            # Generate image using Pollinations.ai API
            timestamp = int(time.time() * 1000)  # Use timestamp as seed for uniqueness
            seed_value = seed if seed is not None else timestamp

            # Build the Pollinations.ai URL
            base_url = "https://image.pollinations.ai/prompt"
            params = {
                "width": width,
                "height": height,
                "nologo": "true",
                "seed": seed_value
            }

            image_url = f"{base_url}/{clean_prompt}"
            query_params = "&".join([f"{k}={v}" for k, v in params.items()])
            full_image_url = f"{image_url}?{query_params}"

            # Download the image
            response = requests.get(full_image_url, timeout=timeout, stream=True)
            response.raise_for_status()

            img_bytes = response.content

            # Convert image format if needed
            with BytesIO(img_bytes) as input_io:
                with Image.open(input_io) as im:
                    out_io = BytesIO()
                    if image_format.lower() == "jpeg":
                        im = im.convert("RGB")
                        im.save(out_io, format="JPEG")
                    else:
                        im.save(out_io, format="PNG")
                    processed_img_bytes = out_io.getvalue()

            # Handle response format
            if response_format == "url":
                # Upload to image hosting service
                uploaded_url = self._upload_image(processed_img_bytes, image_format)
                if not uploaded_url:
                    raise RuntimeError("Failed to upload generated image")
                result_data = [ImageData(url=uploaded_url)]
            elif response_format == "b64_json":
                b64 = base64.b64encode(processed_img_bytes).decode("utf-8")
                result_data = [ImageData(b64_json=b64)]
            else:
                raise ValueError("response_format must be 'url' or 'b64_json'")

            return ImageResponse(created=int(time.time()), data=result_data)

        except RequestException as e:
            raise RuntimeError(f"Failed to generate image with Claude Online: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error during image generation: {e}")

    def _parse_size(self, size: str) -> tuple[int, int]:
        """Parse size string into width and height."""
        size = size.lower().strip()

        # Handle common size formats
        size_map = {
            "256x256": (256, 256),
            "512x512": (512, 512),
            "1024x1024": (1024, 1024),
            "1024x768": (1024, 768),
            "768x1024": (768, 1024),
            "1280x720": (1280, 720),
            "720x1280": (720, 1280),
            "1920x1080": (1920, 1080),
            "1080x1920": (1080, 1920),
        }

        if size in size_map:
            return size_map[size]

        # Try to parse custom size (e.g., "800x600")
        try:
            width, height = size.split("x")
            return int(width), int(height)
        except (ValueError, AttributeError):
            # Default to 1024x1024
            return 1024, 1024

    def _clean_prompt(self, prompt: str) -> str:
        """Clean the prompt by removing command prefixes."""
        # Remove common image generation command prefixes
        prefixes_to_remove = [
            r'^/imagine\s*',
            r'^/image\s*',
            r'^/picture\s*',
            r'^/draw\s*',
            r'^/create\s*',
            r'^/generate\s*',
            r'^создай изображение\s*',
            r'^нарисуй\s*',
            r'^сгенерируй картинку\s*',
        ]

        import re
        clean_prompt = prompt
        for prefix in prefixes_to_remove:
            clean_prompt = re.sub(prefix, '', clean_prompt, flags=re.IGNORECASE)

        return clean_prompt.strip()

    def _upload_image(self, img_bytes: bytes, image_format: str, max_retries: int = 3) -> Optional[str]:
        """Upload image to hosting service and return URL"""

        def upload_to_catbox(img_bytes, image_format):
            """Upload to catbox.moe"""
            ext = "jpg" if image_format.lower() == "jpeg" else "png"
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                    tmp.write(img_bytes)
                    tmp.flush()
                    tmp_path = tmp.name

                with open(tmp_path, "rb") as f:
                    files = {"fileToUpload": (f"image.{ext}", f, f"image/{ext}")}
                    data = {"reqtype": "fileupload", "json": "true"}
                    headers = {"User-Agent": LitAgent().random()}

                    resp = requests.post(
                        "https://catbox.moe/user/api.php",
                        files=files,
                        data=data,
                        headers=headers,
                        timeout=30,
                    )

                    if resp.status_code == 200 and resp.text.strip():
                        text = resp.text.strip()
                        if text.startswith("http"):
                            return text
                        try:
                            result = resp.json()
                            if "url" in result:
                                return result["url"]
                        except json.JSONDecodeError:
                            pass
            except Exception:
                pass
            finally:
                if tmp_path and os.path.isfile(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
            return None

        def upload_to_0x0(img_bytes, image_format):
            """Upload to 0x0.st as fallback"""
            ext = "jpg" if image_format.lower() == "jpeg" else "png"
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                    tmp.write(img_bytes)
                    tmp.flush()
                    tmp_path = tmp.name

                with open(tmp_path, "rb") as img_file:
                    files = {"file": img_file}
                    response = requests.post("https://0x0.st", files=files, timeout=30)
                    response.raise_for_status()
                    image_url = response.text.strip()
                    if image_url.startswith("http"):
                        return image_url
            except Exception:
                pass
            finally:
                if tmp_path and os.path.isfile(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
            return None

        # Try primary upload method
        for attempt in range(max_retries):
            uploaded_url = upload_to_catbox(img_bytes, image_format)
            if uploaded_url:
                return uploaded_url
            time.sleep(1 * (attempt + 1))

        # Try fallback method
        for attempt in range(max_retries):
            uploaded_url = upload_to_0x0(img_bytes, image_format)
            if uploaded_url:
                return uploaded_url
            time.sleep(1 * (attempt + 1))

        return None


class ClaudeOnlineTTI(TTICompatibleProvider):
    """
    Claude Online Text-to-Image Provider

    Uses Claude Online's /imagine feature with Pollinations.ai backend.
    Supports high-quality image generation with various styles and sizes.
    """

    AVAILABLE_MODELS = ["claude-imagine"]

    def __init__(self):
        self.api_endpoint = "https://image.pollinations.ai/prompt"
        self.session = requests.Session()
        self.user_agent = LitAgent().random()
        self.headers = {
            "accept": "image/*",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": self.user_agent,
        }
        self.session.headers.update(self.headers)
        self.images = Images(self)

    @property
    def models(self):
        class _ModelList:
            def list(inner_self):
                return type(self).AVAILABLE_MODELS

        return _ModelList()


if __name__ == "__main__":
    from rich import print

    # Test the Claude Online TTI provider
    client = ClaudeOnlineTTI()

    try:
        response = client.images.create(
            model="claude-imagine",
            prompt="a beautiful sunset over mountains with vibrant colors",
            response_format="url",
            timeout=60,
        )
        print("✅ Image generation successful!")
        print(response)
    except Exception as e:
        print(f"❌ Image generation failed: {e}")
        import traceback
        traceback.print_exc()
