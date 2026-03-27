import math

from pydantic import BaseModel, Field, validator


class Feature(BaseModel):
    name: str
    coordinates: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="[x, y, width, height]",
    )

    @validator("coordinates", pre=True)
    def validate_coordinates(cls, value: object) -> list[float]:
        if not isinstance(value, list) or len(value) != 4:
            raise ValueError("coordinates must be a list of 4 numeric values")

        parsed: list[float] = []
        for coordinate in value:
            if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)):
                raise ValueError("each coordinate must be an int or float")
            as_float = float(coordinate)
            if not math.isfinite(as_float):
                raise ValueError("coordinates must be finite numbers")
            parsed.append(as_float)

        return parsed


class UploadResponse(BaseModel):
    image_id: str
    classification: str
    features: list[Feature]
    description: str


class ImproveRequest(BaseModel):
    image_id: str


class ImproveResponse(BaseModel):
    image_id: str
    improvements: list[str]


class GenerateRequest(BaseModel):
    image_id: str


class GenerateResponse(BaseModel):
    image_id: str
    generated_image: str = Field(..., description="Base64 encoded generated image")


class HealthResponse(BaseModel):
    status: str = Field(..., description="API status")
    gemini_vision_configured: bool = Field(..., description="Whether Gemini vision key is configured")
    gemini_image_configured: bool = Field(..., description="Whether Gemini image key is configured")
    gemini_shared_key_configured: bool = Field(..., description="Whether shared Gemini key is configured")
    groq_configured: bool = Field(..., description="Whether Groq API is configured")
