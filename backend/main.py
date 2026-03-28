import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

import services.gemini as gemini
import services.groq as groq
from schemas import (
    AnalyzeResponse,
    ImagineRequest,
    ImagineResponse,
    SuggestRequest,
    SuggestResponse,
)
from store import SessionNotFound, StepRequired, create_session, get_analysis, get_for_generation, save_suggestions
from utils.image import to_png_base64

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/tif", "image/tiff"}
MAX_SIZE = 15 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await gemini.close()
    await groq.close()


app = FastAPI(title="Satellite AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(file: UploadFile = File(...)) -> AnalyzeResponse:
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    if len(data) > MAX_SIZE:
        raise HTTPException(413, "File too large (max 15 MB)")
    if (file.content_type or "").lower() not in ALLOWED_TYPES:
        raise HTTPException(400, "Unsupported format. Use JPG, PNG, or TIF.")

    try:
        image_b64 = to_png_base64(data)
    except Exception as exc:
        raise HTTPException(400, f"Invalid image: {exc}")

    try:
        analysis = await gemini.analyze(image_b64)
        session_id = create_session(data, analysis)
        return AnalyzeResponse(session_id=session_id, **analysis)
    except gemini.GeminiError as exc:
        logger.error("Gemini analyze failed: %s", exc)
        raise HTTPException(502, f"Gemini error: {exc}")
    except Exception:
        logger.exception("/analyze failed")
        raise HTTPException(500, "Internal server error")


@app.post("/suggest", response_model=SuggestResponse)
async def suggest(body: SuggestRequest) -> SuggestResponse:
    try:
        analysis = get_analysis(body.session_id)
        suggestions = await groq.get_suggestions(analysis)
        save_suggestions(body.session_id, suggestions)
        return SuggestResponse(session_id=body.session_id, suggestions=suggestions)
    except SessionNotFound:
        raise HTTPException(404, "Session not found. Run /analyze first.")
    except groq.GroqError as exc:
        logger.error("Groq suggest failed: %s", exc)
        raise HTTPException(502, f"Groq error: {exc}")
    except Exception:
        logger.exception("/suggest failed")
        raise HTTPException(500, "Internal server error")


@app.post("/imagine", response_model=ImagineResponse)
async def imagine(body: ImagineRequest) -> ImagineResponse:
    try:
        image_bytes, suggestions = get_for_generation(body.session_id)
        image_b64 = to_png_base64(image_bytes)
        result_b64 = await gemini.generate(image_b64, suggestions)
        return ImagineResponse(session_id=body.session_id, image=result_b64)
    except SessionNotFound:
        raise HTTPException(404, "Session not found. Run /analyze first.")
    except StepRequired as exc:
        raise HTTPException(409, str(exc))
    except gemini.GeminiError as exc:
        logger.error("Gemini imagine failed: %s", exc)
        raise HTTPException(502, f"Gemini error: {exc}")
    except Exception:
        logger.exception("/imagine failed")
        raise HTTPException(500, "Internal server error")
