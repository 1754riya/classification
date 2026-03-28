from pydantic import BaseModel


class AnalyzeResponse(BaseModel):
    session_id: str
    classification: str
    objects: list[str]
    description: str


class SuggestRequest(BaseModel):
    session_id: str


class SuggestResponse(BaseModel):
    session_id: str
    suggestions: list[str]


class ImagineRequest(BaseModel):
    session_id: str


class ImagineResponse(BaseModel):
    session_id: str
    image: str  # base64-encoded PNG
