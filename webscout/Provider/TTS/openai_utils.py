"""
OpenAI-compatible response structures for TTS providers.
"""
from typing import Dict, Optional, Any
import time
import uuid
from pathlib import Path

try:
    from webscout.Provider.OPENAI.pydantic_imports import (
        BaseModel, Field, StrictStr, StrictInt
    )
except ImportError:
    # Fallback for basic usage without full OpenAI module
    try:
        from pydantic import BaseModel, Field, StrictStr, StrictInt
    except ImportError:
        # Minimal implementation for environments without pydantic
        class BaseModel:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
            
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
            
            def __repr__(self):
                return f"{self.__class__.__name__}({self.model_dump()})"
        
        def Field(default_factory=None, **kwargs):
            return default_factory() if default_factory else None
        
        StrictStr = str
        StrictInt = int


class TTSUsage(BaseModel):
    """Usage information for TTS requests."""
    characters: StrictInt
    total_characters: StrictInt
    
    def __init__(self, characters: int = 0, **kwargs):
        super().__init__(
            characters=characters,
            total_characters=characters,
            **kwargs
        )


class TTSResponse(BaseModel):
    """OpenAI-compatible TTS response structure."""
    
    def __init__(self, model: str, voice: str, audio_file: str, text: str = "", **kwargs):
        # Generate default values
        response_id = kwargs.get('id', f"tts-{str(uuid.uuid4())}")
        created_time = kwargs.get('created', int(time.time()))
        response_format = kwargs.get('response_format', None)
        
        # Calculate usage from text length
        usage = TTSUsage(characters=len(text)) if text else None
        
        # Determine response format from file extension if not provided
        if not response_format:
            file_path = Path(audio_file)
            response_format = file_path.suffix.lstrip('.').lower() or "mp3"
        
        # Initialize with all fields
        super().__init__(
            id=response_id,
            object="audio.speech",
            created=created_time,
            model=model,
            voice=voice,
            audio_file=str(audio_file),
            audio_url=kwargs.get('audio_url', None),
            response_format=response_format,
            usage=usage,
            **{k: v for k, v in kwargs.items() if k not in ['id', 'created', 'response_format', 'audio_url']}
        )
    
    def get_audio_data(self) -> bytes:
        """Read and return the audio file data."""
        with open(self.audio_file, 'rb') as f:
            return f.read()
    
    def get_audio_file_path(self) -> str:
        """Get the path to the audio file (for backward compatibility)."""
        return self.audio_file
    
    def __str__(self) -> str:
        """String representation returns the audio file path for backward compatibility."""
        return self.audio_file


def create_tts_response(
    model: str,
    voice: str, 
    audio_file: str,
    text: str = "",
    **kwargs
) -> TTSResponse:
    """
    Helper function to create an OpenAI-compatible TTS response.
    
    Args:
        model: The model used for TTS
        voice: The voice used
        audio_file: Path to the generated audio file
        text: The original text (for usage calculation)
        **kwargs: Additional response parameters
        
    Returns:
        TTSResponse object
    """
    return TTSResponse(
        model=model,
        voice=voice,
        audio_file=audio_file,
        text=text,
        **kwargs
    )