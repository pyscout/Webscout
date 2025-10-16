"""
Pydantic models for API requests and responses.
"""

from typing import List, Dict, Optional, Union, Any, Literal
from webscout.Provider.OPENAI.pydantic_imports import BaseModel, Field


# Define Pydantic models for multimodal content parts, aligning with OpenAI's API
class TextPart(BaseModel):
    """Text content part for multimodal messages."""
    type: Literal["text"]
    text: str


class ImageURL(BaseModel):
    """Image URL configuration for multimodal messages."""
    url: str  # Can be http(s) or data URI
    detail: Optional[Literal["auto", "low", "high"]] = Field(
        "auto",
        description="Specifies the detail level of the image."
    )


class ImagePart(BaseModel):
    """Image content part for multimodal messages."""
    type: Literal["image_url"]
    image_url: ImageURL


MessageContentParts = Union[TextPart, ImagePart]


class Message(BaseModel):
    """Chat message model compatible with OpenAI API."""
    role: Literal["system", "user", "assistant", "function", "tool"]
    content: Optional[Union[str, List[MessageContentParts]]] = Field(
        None,
        description="The content of the message. Can be a string, a list of content parts (for multimodal), or null."
    )
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    """Request model for chat completions."""
    model: str = Field(..., description="ID of the model to use. See the model endpoint for the available models.")
    messages: List[Message] = Field(..., description="A list of messages comprising the conversation so far.")
    temperature: Optional[float] = Field(None, description="What sampling temperature to use, between 0 and 2.")
    top_p: Optional[float] = Field(None, description="An alternative to sampling with temperature, called nucleus sampling.")
    n: Optional[int] = Field(1, description="How many chat completion choices to generate for each input message.")
    stream: Optional[bool] = Field(False, description="If set, partial message deltas will be sent, like in ChatGPT.")
    max_tokens: Optional[int] = Field(None, description="The maximum number of tokens to generate in the chat completion.")
    presence_penalty: Optional[float] = Field(None, description="Number between -2.0 and 2.0. Positive values penalize new tokens based on whether they appear in the text so far.")
    frequency_penalty: Optional[float] = Field(None, description="Number between -2.0 and 2.0. Positive values penalize new tokens based on their existing frequency in the text so far.")
    logit_bias: Optional[Dict[str, float]] = Field(None, description="Modify the likelihood of specified tokens appearing in the completion.")
    user: Optional[str] = Field(None, description="A unique identifier representing your end-user.")
    stop: Optional[Union[str, List[str]]] = Field(None, description="Up to 4 sequences where the API will stop generating further tokens.")

    class Config:
        extra = "ignore"
        schema_extra = {
            "example": {
                "model": "Cloudflare/@cf/meta/llama-4-scout-17b-16e-instruct",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Hello, how are you?"}
                ],
                "temperature": 0.7,
                "max_tokens": 150,
                "stream": False
            }
        }


class ImageGenerationRequest(BaseModel):
    """Request model for OpenAI-compatible image generation endpoint."""
    prompt: str = Field(..., description="A text description of the desired image(s). The maximum length is 1000 characters.")
    model: str = Field(..., description="The model to use for image generation.")
    n: Optional[int] = Field(1, description="The number of images to generate. Must be between 1 and 10.")
    size: Optional[str] = Field("1024x1024", description="The size of the generated images. Must be one of: '256x256', '512x512', or '1024x1024'.")
    response_format: Optional[Literal["url", "b64_json"]] = Field("url", description="The format in which the generated images are returned.")
    user: Optional[str] = Field(None, description="A unique identifier representing your end-user.")
    style: Optional[str] = Field(None, description="Optional style for the image (provider/model-specific).")
    aspect_ratio: Optional[str] = Field(None, description="Optional aspect ratio for the image (provider/model-specific).")
    timeout: Optional[int] = Field(None, description="Optional timeout for the image generation request in seconds.")
    image_format: Optional[str] = Field(None, description="Optional image format (e.g., 'png', 'jpeg').")
    seed: Optional[int] = Field(None, description="Optional random seed for reproducibility.")

    class Config:
        extra = "ignore"
        schema_extra = {
            "example": {
                "prompt": "A futuristic cityscape at sunset, digital art",
                "model": "PollinationsAI/turbo",
                "n": 1,
                "size": "1024x1024",
                "response_format": "url",
                "user": "user-1234"
            }
        }


class ModelInfo(BaseModel):
    """Model information for the models endpoint."""
    id: str
    object: str = "model"
    created: int
    owned_by: str


class ModelListResponse(BaseModel):
    """Response model for the models list endpoint."""
    object: str = "list"
    data: List[ModelInfo]


class ErrorDetail(BaseModel):
    """Error detail structure compatible with OpenAI API."""
    message: str
    type: str = "server_error"
    param: Optional[str] = None
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response structure compatible with OpenAI API."""
    error: ErrorDetail
