from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schemas import AnalysisDTO, DecisionContextDTO, HealthDTO
from .service import ProVSAService

app = FastAPI(title="ProVSA API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://provsascan.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_service = ProVSAService()


@app.get("/api/health", response_model=HealthDTO)
def health() -> HealthDTO:
    return _service.health()


@app.get("/api/symbols/{symbol}/analysis", response_model=AnalysisDTO)
def symbol_analysis(symbol: str) -> AnalysisDTO:
    try:
        return _service.analyze_symbol(symbol)
    except (ValueError, IndexError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Analysis failed") from exc


@app.get("/api/symbols/{symbol}/decision-context", response_model=DecisionContextDTO)
def symbol_decision_context(symbol: str) -> DecisionContextDTO:
    try:
        return _service.decision_context_for_symbol(symbol)
    except (ValueError, IndexError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Decision context failed") from exc
