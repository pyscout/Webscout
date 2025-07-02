import time
import requests
import pathlib
import urllib.parse
import tempfile
from typing import Union
from io import BytesIO
from webscout import exceptions
from webscout.litagent import LitAgent
from concurrent.futures import ThreadPoolExecutor, as_completed
from . import utils
from .base import BaseTTSProvider

class StreamElements(BaseTTSProvider):
    """
    Text-to-speech provider using the StreamElements API.
    """

    # Request headers
    headers: dict[str, str] = {
        "User-Agent": LitAgent().random()
    }
    all_voices: list[str] = [
        "Filiz",
        "Astrid",
        "Tatyana",
        "Maxim",
        "Carmen",
        "Ines",
        "Cristiano",
        "Vitoria",
        "Ricardo",
        "Maja",
        "Jan",
        "Jacek",
        "Ewa",
        "Ruben",
        "Lotte",
        "Liv",
        "Seoyeon",
        "Takumi",
        "Mizuki",
        "Giorgio",
        "Carla",
        "Bianca",
        "Karl",
        "Dora",
        "Mathieu",
        "Celine",
        "Chantal",
        "Penelope",
        "Miguel",
        "Mia",
        "Enrique",
        "Conchita",
        "Geraint",
        "Salli",
        "Matthew",
        "Kimberly",
        "Kendra",
        "Justin",
        "Joey",
        "Joanna",
        "Ivy",
        "Raveena",
        "Aditi",
        "Emma",
        "Brian",
        "Amy",
        "Russell",
        "Nicole",
        "Vicki",
        "Marlene",
        "Hans",
        "Naja",
        "Mads",
        "Gwyneth",
        "Zhiyu",
        "es-ES-Standard-A",
        "it-IT-Standard-A",
        "it-IT-Wavenet-A",
        "ja-JP-Standard-A",
        "ja-JP-Wavenet-A",
        "ko-KR-Standard-A",
        "ko-KR-Wavenet-A",
        "pt-BR-Standard-A",
        "tr-TR-Standard-A",
        "sv-SE-Standard-A",
        "nl-NL-Standard-A",
        "nl-NL-Wavenet-A",
        "en-US-Wavenet-A",
        "en-US-Wavenet-B",
        "en-US-Wavenet-C",
        "en-US-Wavenet-D",
        "en-US-Wavenet-E",
        "en-US-Wavenet-F",
        "en-GB-Standard-A",
        "en-GB-Standard-B",
        "en-GB-Standard-C",
        "en-GB-Standard-D",
        "en-GB-Wavenet-A",
        "en-GB-Wavenet-B",
        "en-GB-Wavenet-C",
        "en-GB-Wavenet-D",
        "en-US-Standard-B",
        "en-US-Standard-C",
        "en-US-Standard-D",
        "en-US-Standard-E",
        "de-DE-Standard-A",
        "de-DE-Standard-B",
        "de-DE-Wavenet-A",
        "de-DE-Wavenet-B",
        "de-DE-Wavenet-C",
        "de-DE-Wavenet-D",
        "en-AU-Standard-A",
        "en-AU-Standard-B",
        "en-AU-Wavenet-A",
        "en-AU-Wavenet-B",
        "en-AU-Wavenet-C",
        "en-AU-Wavenet-D",
        "en-AU-Standard-C",
        "en-AU-Standard-D",
        "fr-CA-Standard-A",
        "fr-CA-Standard-B",
        "fr-CA-Standard-C",
        "fr-CA-Standard-D",
        "fr-FR-Standard-C",
        "fr-FR-Standard-D",
        "fr-FR-Wavenet-A",
        "fr-FR-Wavenet-B",
        "fr-FR-Wavenet-C",
        "fr-FR-Wavenet-D",
        "da-DK-Wavenet-A",
        "pl-PL-Wavenet-A",
        "pl-PL-Wavenet-B",
        "pl-PL-Wavenet-C",
        "pl-PL-Wavenet-D",
        "pt-PT-Wavenet-A",
        "pt-PT-Wavenet-B",
        "pt-PT-Wavenet-C",
        "pt-PT-Wavenet-D",
        "ru-RU-Wavenet-A",
        "ru-RU-Wavenet-B",
        "ru-RU-Wavenet-C",
        "ru-RU-Wavenet-D",
        "sk-SK-Wavenet-A",
        "tr-TR-Wavenet-A",
        "tr-TR-Wavenet-B",
        "tr-TR-Wavenet-C",
        "tr-TR-Wavenet-D",
        "tr-TR-Wavenet-E",
        "uk-UA-Wavenet-A",
        "ar-XA-Wavenet-A",
        "ar-XA-Wavenet-B",
        "ar-XA-Wavenet-C",
        "cs-CZ-Wavenet-A",
        "nl-NL-Wavenet-B",
        "nl-NL-Wavenet-C",
        "nl-NL-Wavenet-D",
        "nl-NL-Wavenet-E",
        "en-IN-Wavenet-A",
        "en-IN-Wavenet-B",
        "en-IN-Wavenet-C",
        "fil-PH-Wavenet-A",
        "fi-FI-Wavenet-A",
        "el-GR-Wavenet-A",
        "hi-IN-Wavenet-A",
        "hi-IN-Wavenet-B",
        "hi-IN-Wavenet-C",
        "hu-HU-Wavenet-A",
        "id-ID-Wavenet-A",
        "id-ID-Wavenet-B",
        "id-ID-Wavenet-C",
        "it-IT-Wavenet-B",
        "it-IT-Wavenet-C",
        "it-IT-Wavenet-D",
        "ja-JP-Wavenet-B",
        "ja-JP-Wavenet-C",
        "ja-JP-Wavenet-D",
        "cmn-CN-Wavenet-A",
        "cmn-CN-Wavenet-B",
        "cmn-CN-Wavenet-C",
        "cmn-CN-Wavenet-D",
        "nb-no-Wavenet-E",
        "nb-no-Wavenet-A",
        "nb-no-Wavenet-B",
        "nb-no-Wavenet-C",
        "nb-no-Wavenet-D",
        "vi-VN-Wavenet-A",
        "vi-VN-Wavenet-B",
        "vi-VN-Wavenet-C",
        "vi-VN-Wavenet-D",
        "sr-rs-Standard-A",
        "lv-lv-Standard-A",
        "is-is-Standard-A",
        "bg-bg-Standard-A",
        "af-ZA-Standard-A",
        "Tracy",
        "Danny",
        "Huihui",
        "Yaoyao",
        "Kangkang",
        "HanHan",
        "Zhiwei",
        "Asaf",
        "An",
        "Stefanos",
        "Filip",
        "Ivan",
        "Heidi",
        "Herena",
        "Kalpana",
        "Hemant",
        "Matej",
        "Andika",
        "Rizwan",
        "Lado",
        "Valluvar",
        "Linda",
        "Heather",
        "Sean",
        "Michael",
        "Karsten",
        "Guillaume",
        "Pattara",
        "Jakub",
        "Szabolcs",
        "Hoda",
        "Naayf",
    ]

    def __init__(self, timeout: int = 20, proxies: dict = None, openai_compatible: bool = True):
        """
        Initializes the StreamElements TTS client.
        
        Args:
            timeout: Request timeout in seconds
            proxies: Proxy configuration  
            openai_compatible: Whether to return OpenAI-compatible responses (default: True)
        """
        super().__init__(openai_compatible=openai_compatible)
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        if proxies:
            self.session.proxies.update(proxies)
        self.timeout = timeout

    def tts(self, text: str, voice: str = "Mathieu", verbose: bool = True) -> Union[str, "TTSResponse"]:
        """
        Converts text to speech using the StreamElements API and saves it to a file.

        Args:
            text (str): The text to convert to speech
            voice (str): The voice to use for TTS (default: "Mathieu")
            verbose (bool): Whether to print progress messages (default: True)

        Returns:
            Union[str, TTSResponse]: Path to the generated audio file (legacy) or TTSResponse object (OpenAI-compatible)
        """
        assert (
            voice in self.all_voices
        ), f"Voice '{voice}' not one of [{', '.join(self.all_voices)}]"

        filename = pathlib.Path(tempfile.mktemp(suffix=".mp3", dir=self.temp_dir))

        # Split text into sentences
        sentences = utils.split_sentences(text)

        # Function to request audio for each chunk
        def generate_audio_for_chunk(part_text: str, part_number: int):
            while True:
                try:
                    # URL encode the text and voice
                    encoded_text = urllib.parse.quote(part_text)
                    encoded_voice = urllib.parse.quote(voice)

                    url = f"https://streamelements.com/tts/{encoded_voice}/{encoded_text}"

                    response = self.session.get(url, headers=self.headers, timeout=self.timeout)
                    response.raise_for_status()

                    # Check if the request was successful
                    if response.ok and response.status_code == 200:
                        if verbose:
                            print(f"[debug] Chunk {part_number} processed successfully")
                        return part_number, response.content
                    else:
                        if verbose:
                            print(f"[debug] No data received for chunk {part_number}. Retrying...")
                except requests.RequestException as e:
                    if verbose:
                        print(f"[debug] Error for chunk {part_number}: {e}. Retrying...")
                    time.sleep(1)
        try:
            # Using ThreadPoolExecutor to handle requests concurrently
            with ThreadPoolExecutor() as executor:
                futures = {executor.submit(generate_audio_for_chunk, sentence.strip(), chunk_num): chunk_num
                        for chunk_num, sentence in enumerate(sentences, start=1)}

                # Dictionary to store results with order preserved
                audio_chunks = {}

                for future in as_completed(futures):
                    chunk_num = futures[future]
                    try:
                        part_number, audio_data = future.result()
                        audio_chunks[part_number] = audio_data  # Store the audio data in correct sequence
                    except Exception as e:
                        if verbose:
                            print(f"[debug] Failed to generate audio for chunk {chunk_num}: {e}")

            # Combine audio chunks in the correct sequence
            combined_audio = BytesIO()
            for part_number in sorted(audio_chunks.keys()):
                combined_audio.write(audio_chunks[part_number])
                if verbose:
                    print(f"[debug] Added chunk {part_number} to the combined file.")

            # Save the combined audio data to a single file
            with open(filename, 'wb') as f:
                f.write(combined_audio.getvalue())
            if verbose:
                print(f"[debug] Final Audio Saved as {filename}")
            
            # Create and return response in the appropriate format
            return self.create_response(
                audio_file=filename.as_posix(),
                text=text,
                voice=voice,
                model="streamelements-tts"
            )

        except requests.exceptions.RequestException as e:
            if verbose:
                print(f"[debug] Failed to perform the operation: {e}")
            raise exceptions.FailedToGenerateResponseError(
                f"Failed to perform the operation: {e}"
            )

# Example usage
if __name__ == "__main__":
    streamelements = StreamElements()
    text = "This is a test of the StreamElements text-to-speech API. It supports multiple sentences and advanced logging."

    print("[debug] Generating audio...")
    audio_file = streamelements.tts(text, voice="Mathieu")
    print(f"Audio saved to: {audio_file}")
