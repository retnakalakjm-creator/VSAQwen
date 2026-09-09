from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from decision_journal import DEFAULT_VALIDATION_HORIZON_BARS
from market_data import create_market_data_provider_from_env

from .data_source_status import build_data_source_status
from .schemas import (
    AnalysisDTO,
    DataSourceStatusDTO,
    DecisionContextDTO,
    DecisionJournalDTO,
    DecisionJournalEvaluationResponseDTO,
    HealthDTO,
)
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


def create_service() -> ProVSAService:
    """Create the API service with runtime market-data provider selection."""
    return ProVSAService(
        market_data_provider=create_market_data_provider_from_env(),
    )


_service = create_service()


@app.get("/api/health", response_model=HealthDTO)
def health() -> HealthDTO:
    return _service.health()


@app.get("/api/symbols/{symbol}/data-source", response_model=DataSourceStatusDTO)
def symbol_data_source_status(symbol: str) -> DataSourceStatusDTO:
    try:
        return DataSourceStatusDTO(
            **build_data_source_status(symbol, _service._market_data_provider)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Data source status failed") from exc


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


@app.get(
    "/api/symbols/{symbol}/decision-context/developing",
    response_model=DecisionContextDTO,
)
def symbol_developing_decision_context(symbol: str) -> DecisionContextDTO:
    try:
        return _service.developing_decision_context_for_symbol(symbol)
    except (ValueError, IndexError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Developing decision context failed") from exc


@app.get("/api/symbols/{symbol}/decision-journal", response_model=DecisionJournalDTO)
def symbol_decision_journal(symbol: str) -> DecisionJournalDTO:
    try:
        return _service.decision_journal_for_symbol(symbol)
    except (ValueError, IndexError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Decision journal failed") from exc


@app.get(
    "/api/symbols/{symbol}/decision-journal/evaluations",
    response_model=DecisionJournalEvaluationResponseDTO,
)
def symbol_decision_journal_evaluations(
    symbol: str,
    horizon_bars: int = DEFAULT_VALIDATION_HORIZON_BARS,
    persist_status: bool = False,
) -> DecisionJournalEvaluationResponseDTO:
    try:
        return _service.evaluate_decision_journal_for_symbol(
            symbol,
            horizon_bars=horizon_bars,
            persist_status=persist_status,
        )
    except (ValueError, IndexError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Decision journal evaluation failed") from exc
