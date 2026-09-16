"""AI-powered endpoints using OmniRoute gateway"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from tenant_auth import get_tenant_context, TenantContext
from omniroute_client import summarize_text, generate_description, analyze_data
import json

router = APIRouter(prefix="/api/v1/ai", tags=["AI"])


# ============ SCHEMAS ============

class TextSummarizeRequest(BaseModel):
    text: str
    max_tokens: int = 200


class TextSummarizeResponse(BaseModel):
    original_length: int
    summary: str
    model: str = "omniroute/auto"


class DescriptionGenerateRequest(BaseModel):
    subject: str
    context: str = ""
    max_tokens: int = 300


class DescriptionGenerateResponse(BaseModel):
    subject: str
    description: str
    model: str = "omniroute/auto"


class DataAnalysisRequest(BaseModel):
    data: dict | str
    query: str
    max_tokens: int = 400


class DataAnalysisResponse(BaseModel):
    query: str
    analysis: str
    model: str = "omniroute/auto"


# ============ ENDPOINTS ============

@router.post("/summarize", response_model=TextSummarizeResponse)
async def summarize_endpoint(
    request: TextSummarizeRequest,
    context: TenantContext = Depends(get_tenant_context)
):
    """Summarize text using OmniRoute AI."""
    try:
        summary = summarize_text(request.text, max_tokens=request.max_tokens)
        return TextSummarizeResponse(
            original_length=len(request.text),
            summary=summary
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AI service error: {str(e)}")


@router.post("/generate-description", response_model=DescriptionGenerateResponse)
async def generate_description_endpoint(
    request: DescriptionGenerateRequest,
    context: TenantContext = Depends(get_tenant_context)
):
    """Generate product or service description using OmniRoute AI."""
    try:
        description = generate_description(request.subject, request.context, request.max_tokens)
        return DescriptionGenerateResponse(
            subject=request.subject,
            description=description
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AI service error: {str(e)}")


@router.post("/analyze", response_model=DataAnalysisResponse)
async def analyze_endpoint(
    request: DataAnalysisRequest,
    context: TenantContext = Depends(get_tenant_context)
):
    """Analyze data using OmniRoute AI."""
    try:
        data_str = json.dumps(request.data) if isinstance(request.data, dict) else str(request.data)
        analysis = analyze_data(data_str, request.query, request.max_tokens)
        return DataAnalysisResponse(
            query=request.query,
            analysis=analysis
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AI service error: {str(e)}")


@router.get("/status")
async def ai_status(
    context: TenantContext = Depends(get_tenant_context)
):
    """Check OmniRoute AI gateway status."""
    try:
        from omniroute_client import client
        # Simple health check by creating minimal request
        response = client.chat.completions.create(
            model="auto",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=10
        )
        return {
            "status": "ok",
            "gateway": "omniroute",
            "endpoint": "http://localhost:20128/v1"
        }
    except Exception as e:
        return {
            "status": "error",
            "gateway": "omniroute",
            "error": str(e)
        }
