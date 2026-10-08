from backend.app.core import config


class ImageGenerationError(RuntimeError):
    pass


def generate_image(prompt: str):
    """Return (image_bytes, mime_type) using Google's image model."""
    if not config.GOOGLE_API_KEY:
        raise ImageGenerationError("GOOGLE_API_KEY is not set in .env")

    from google import genai  # imported lazily so the server starts without it

    client = genai.Client(api_key=config.GOOGLE_API_KEY)
    response = client.models.generate_content(model=config.IMAGE_MODEL, contents=prompt)

    for candidate in response.candidates or []:
        for part in candidate.content.parts or []:
            if part.inline_data is not None:
                return part.inline_data.data, part.inline_data.mime_type or "image/png"

    raise ImageGenerationError(
        "The model didn't return an image. Try rephrasing your prompt."
    )
