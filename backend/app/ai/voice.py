import os
import asyncio
import litellm
from litellm import completion
import edge_tts
from app.core.config import Setting

async def speech_to_text(audio_path: str) -> str:
    """
    Converts speech from an audio file to text using Gemini Multimodal STT and cleans with Mistral.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found at: {audio_path}")

    raw_text = ""

    # Primary: Gemini Multimodal STT
    gemini_key = Setting.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=gemini_key)
            with open(audio_path, 'rb') as audio_file:
                audio_bytes = audio_file.read()

            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/webm")
            prompt = "Transcribe spoken speech accurately in English or Tanglish. Return ONLY the transcribed text."

            res = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-3.6-flash",
                contents=[audio_part, prompt]
            )
            if res and hasattr(res, "text") and res.text:
                raw_text = res.text.strip()
        except Exception as e:
            print(f"Gemini Multimodal STT note in voice.py: {e}")

    if not raw_text:
        raise RuntimeError("Speech to text failed. Please check Gemini API key.")

    mistral_key = Setting.MISTRAL_API_KEY or os.getenv("MISTRAL_API_KEY")
    if mistral_key:
        try:
            response = completion(
                model='mistral/mistral-small-latest',
                messages=[
                    {"role": "system", "content": "summarize the text short and crisp"},
                    {"role": "user", "content": raw_text}
                ],
                api_key=mistral_key
            )
            if response and hasattr(response, "choices") and len(response.choices) > 0:
                return response.choices[0].message.content or raw_text
        except Exception:
            pass

    return raw_text

async def text_to_speech(text: str, output_path: str, voice: str = 'en-IN-PrabhatNeural') -> None:
    """
    Converts text to speech using edge_tts and saves it to output_path.
    """
    # Ensure the output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

async def main():
    input_audio = 'recordings/audio.m4a'
    output_audio = 'outputs/output.mp3'
    
    print(f"1. Performing STT on '{input_audio}'...")
    try:
        text = await speech_to_text(input_audio)
        print(f"STT Output (Transcribed Text): \"{text}\"\n")
    except Exception as e:
        print(f"Error during STT: {e}")
        return

    print(f"2. Performing TTS to generate '{output_audio}'...")
    try:
        await text_to_speech(text, output_audio)
        print(f"TTS Output successfully saved to: {output_audio}")
    except Exception as e:
        print(f"Error during TTS: {e}")

if __name__ == "__main__":
    asyncio.run(main())

