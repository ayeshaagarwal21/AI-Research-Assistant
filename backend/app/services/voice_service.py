"""Text-to-speech and speech-to-text.

The third-party libraries are imported inside the functions, so the server still
starts (and the text-cleaning logic stays testable) even if they aren't installed.
"""
import io
import re


def clean_for_speech(text: str) -> str:
    """Remove citations like (file.pdf, p. 3) and markdown symbols before speaking."""
    text = re.sub(r"\([^()]*\.pdf,\s*p\.?\s*\d+\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[*_`#>]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1500]


def text_to_mp3(text: str, lang: str = "en") -> bytes:
    cleaned = clean_for_speech(text)
    if not cleaned:
        raise ValueError("There is no text to read aloud")

    from gtts import gTTS

    buffer = io.BytesIO()
    gTTS(text=cleaned, lang=lang).write_to_fp(buffer)
    return buffer.getvalue()


def speech_to_text(audio_bytes: bytes, language: str = "en-US") -> str:
    """Transcribe WAV audio. Use language="hi-IN" for Hindi."""
    import speech_recognition as sr

    recognizer = sr.Recognizer()
    with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
        audio = recognizer.record(source)
    try:
        return recognizer.recognize_google(audio, language=language)
    except sr.UnknownValueError:
        raise ValueError(
            "Couldn't understand the audio. Speak clearly and closer to the mic."
        )
