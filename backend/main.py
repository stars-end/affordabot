from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from services.notifications.email import EmailNotificationService
from db.postgres_client import PostgresDB
from typing import Dict, Any, List, Literal, Optional
import os
import logging
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from routers import admin, sources, discovery, prompts, bills
from services.scraper.registry import SCRAPERS
from middleware.auth import TestAuthBypassMiddleware
from services.llm.web_search_factory import create_web_search_client
from scripts.substrate.manual_expansion_runner import run_manual_substrate_expansion
from pathlib import Path
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from uuid import uuid4

# Initialize Sentry
if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        traces_sample_rate=0.1,
        environment=os.getenv("ENVIRONMENT", "development"),
    )
    logger = logging.getLogger(__name__)
    logger.info("Sentry initialized")
else:
    logger = logging.getLogger(__name__)
    logger.warning("Sentry DSN not set. Error tracking disabled.")

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
EMBEDDING_DIMENSIONS = 4096

app = FastAPI(title="Affordabot API")
db = PostgresDB()
email_service = EmailNotificationService()


@app.on_event("startup")
async def startup_db():
    await db.connect()
    app.state.db = db
    logger.info("✅ Database connected (Postgres/Railway)")


@app.on_event("shutdown")
async def shutdown_db():
    await db.close()


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add test auth bypass middleware
app.add_middleware(TestAuthBypassMiddleware)

# Include admin router
app.include_router(admin.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(discovery.router, prefix="/api")
app.include_router(prompts.router, prefix="/api")
app.include_router(bills.router, prefix="/api")

# Add rate limiting middleware (60 requests/minute per IP)
# app.middleware("http")(RateLimiter(requests_per_minute=60))


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback

    error_msg = f"{str(exc)}\n{traceback.format_exc()}"
    logger.error(f"Global exception: {error_msg}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "traceback": traceback.format_exc()},
    )


# Jurisdiction mapping


@app.get("/")
async def root():
    return {
        "message": "Welcome to AffordaBot API",
        "jurisdictions": list(SCRAPERS.keys()),
        "version": "1.0.0",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    # Check Z.ai health
    from services.research.zai import ZaiResearchService

    zai_health = await ZaiResearchService().check_health()

    return {
        "status": "healthy",
        "database": "connected" if db.is_connected() else "disconnected",
        "zai_research": "connected" if zai_health else "disconnected",
    }


@app.get("/health/build")
async def build_health_check():
    """Return immutable build identity for deployment freshness checks.

    Compatible with the shared agent-skills railway contract.
    Agents use this to answer: "Is origin/master actually live on Railway?"
    """
    git_commit = (
        os.getenv("GIT_COMMIT")
        or os.getenv("RAILWAY_GIT_COMMIT_SHA")
        or os.getenv("COMMIT_SHA")
        or "unknown"
    )
    build_timestamp = (
        os.getenv("BUILD_TIMESTAMP")
        or os.getenv("RAILWAY_DEPLOYMENT_CREATED_AT")
        or os.getenv("SOURCE_DATE_EPOCH")
        or "unknown"
    )
    build_id = os.getenv("BUILD_ID") or f"{git_commit}:{build_timestamp}"

    return {
        "git_commit": git_commit,
        "build_timestamp": build_timestamp,
        "build_id": build_id,
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "service": "backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health/jurisdictions")
async def health_check_jurisdictions():
    """Check health of all jurisdiction scrapers."""
    results = {}
    for jurisdiction, (scraper_class, _) in SCRAPERS.items():
        scraper = scraper_class()
        is_healthy = await scraper.check_health()
        results[jurisdiction] = "healthy" if is_healthy else "unhealthy"

    return {"status": "success", "jurisdictions": results}


@app.get("/health/analysis")
async def health_check_analysis():
    """Check health of LLM pipeline (LLM + Search)."""
    try:
        from llm_common.core import LLMConfig
        from llm_common.providers import ZaiClient

        # Check LLM
        llm_config = LLMConfig(
            api_key=os.getenv("ZAI_API_KEY", "dummy"),
            provider="zai",
            default_model=os.getenv("LLM_MODEL_RESEARCH", "glm-4.7"),
        )
        llm_client = ZaiClient(llm_config)
        llm_ok = await llm_client.validate_api_key()

        # Check Search
        _ = create_web_search_client(api_key=os.getenv("ZAI_API_KEY", "dummy"))
        # WebSearchClient doesn't have explicit check_health, assume OK if init passed or add check if available
        # But we can try a simple search?
        search_ok = True

        status = "healthy" if llm_ok else "degraded"
        return {
            "status": status,
            "details": {
                "llm": "connected" if llm_ok else "error",
                "search": "connected" if search_ok else "unknown",
            },
        }
    except Exception as e:
        logger.error(f"Analysis health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


async def process_jurisdiction(jurisdiction: str, scraper_class, jur_type: str):
    """Background task to process a single jurisdiction."""
    logger.info(f"Starting scrape for {jurisdiction}")

    scraper = scraper_class()

    # Initialize Agentic Pipeline
    try:
        from services.llm.orchestrator import AnalysisPipeline
        from services.llm.orchestrator import DEFAULT_OPENROUTER_FALLBACK_MODEL
        from llm_common.core import LLMConfig
        from llm_common.providers import ZaiClient, OpenRouterClient

        llm_config = LLMConfig(
            api_key=os.getenv("ZAI_API_KEY"),
            provider="zai",
            default_model=os.getenv("LLM_MODEL_RESEARCH", "glm-4.7"),
        )
        llm_client = ZaiClient(llm_config)

        # Initialize fallback client (OpenRouter)
        fallback_client = None
        if os.getenv("OPENROUTER_API_KEY"):
            or_config = LLMConfig(
                api_key=os.getenv("OPENROUTER_API_KEY"),
                provider="openrouter",
                default_model=(
                    os.getenv("LLM_MODEL_FALLBACK_OPENROUTER")
                    or DEFAULT_OPENROUTER_FALLBACK_MODEL
                ),
            )
            fallback_client = OpenRouterClient(or_config)

        search_client = create_web_search_client(api_key=os.getenv("ZAI_API_KEY"))

        retrieval_backend = None
        embedding_fn = None
        if os.getenv("OPENROUTER_API_KEY"):
            from services.retrieval.local_pgvector import LocalPgVectorBackend
            from llm_common.embeddings.openai import OpenAIEmbeddingService

            _embed_svc = OpenAIEmbeddingService(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.getenv("OPENROUTER_API_KEY"),
                model="qwen/qwen3-embedding-8b",
                dimensions=EMBEDDING_DIMENSIONS,
            )
            retrieval_backend = LocalPgVectorBackend(
                table_name="document_chunks",
                postgres_client=db,
                embedding_fn=_embed_svc.embed_query,
            )
            embedding_fn = _embed_svc.embed_query

        pipeline = AnalysisPipeline(
            llm_client,
            search_client,
            db,
            fallback_client=fallback_client,
            retrieval_backend=retrieval_backend,
            embedding_fn=embedding_fn,
        )

    except Exception as e:
        logger.error(f"Failed to initialize AnalysisPipeline: {e}")
        return {"jurisdiction": jurisdiction, "error": f"Pipeline Init Failed: {e}"}

    try:
        # 1. Scrape legislation
        bills = await scraper.scrape()
        logger.info(f"{jurisdiction}: Found {len(bills)} bills")

        if not bills:
            return {"jurisdiction": jurisdiction, "status": "no bills"}

        # 2. Get or create jurisdiction in DB
        _ = await db.get_or_create_jurisdiction(
            name=scraper.jurisdiction_name, type=jur_type
        )

        processed = 0
        skipped = 0

        errors = []
        for bill in bills:
            try:
                if jurisdiction == "california":
                    if not bill.text or len(bill.text) < 100:
                        extraction_status = getattr(bill, "provenance", None)
                        if extraction_status and hasattr(
                            extraction_status, "extraction_status"
                        ):
                            status = extraction_status.extraction_status
                            error = extraction_status.extraction_error
                        else:
                            status = "unknown"
                            error = "No bill text available"
                        logger.warning(
                            f"{jurisdiction}: Skipping {bill.bill_number} - "
                            f"extraction_status={status}, error={error}"
                        )
                        skipped += 1
                        continue

                models = {
                    "research": os.getenv("LLM_MODEL_RESEARCH", "glm-4.7"),
                    "generate": os.getenv("LLM_MODEL_GENERATE", "glm-4.7"),
                    "review": os.getenv("LLM_MODEL_REVIEW", "glm-4.7"),
                }

                await pipeline.run(
                    bill_id=bill.bill_number,
                    bill_text=bill.text,
                    jurisdiction=scraper.jurisdiction_name,
                    models=models,
                )

                processed += 1
                logger.info(f"{jurisdiction}: Processed {bill.bill_number}")

            except Exception as e:
                import traceback

                error_details = f"{str(e)}\n{traceback.format_exc()}"
                errors.append({"bill": bill.bill_number, "error": error_details})
                logger.error(
                    f"{jurisdiction}: Error processing {bill.bill_number}: {e}"
                )

        return {
            "jurisdiction": jurisdiction,
            "processed": processed,
            "skipped": skipped,
            "errors": errors,
        }

    except Exception as e:
        logger.error(f"{jurisdiction}: Scraping failed: {e}")
        return {"jurisdiction": jurisdiction, "error": str(e)}


# --- Authenticated Cron Trigger Endpoints (bd-s8id.3) ---
# These endpoints are used by Windmill as the scheduler of record.
# Auth: Authorization: Bearer $CRON_SECRET, X-Cron-Secret: $CRON_SECRET,
# or X-PR-CRON-SECRET: $CRON_SECRET for Prime-style shared-instance wrappers.

CRON_SECRET = os.environ.get("CRON_SECRET")
BACKEND_ROOT = Path(__file__).resolve().parent


def _backend_script_path(relative_path: str) -> str:
    """Resolve cron scripts relative to the deployed backend service root."""
    return str((BACKEND_ROOT / relative_path).resolve())


def _verify_cron_auth(request: Request) -> bool:
    """Verify cron secret from supported internal cron auth headers."""
    if not CRON_SECRET:
        logger.warning("CRON_SECRET not set — cron auth rejected")
        return False

    # Check Authorization: Bearer token
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if token == CRON_SECRET:
            return True

    # Check X-Cron-Secret header
    cron_header = request.headers.get("x-cron-secret", "")
    if cron_header == CRON_SECRET:
        return True

    # Prime-style shared Windmill instance header
    pr_cron_header = request.headers.get("x-pr-cron-secret", "")
    if pr_cron_header == CRON_SECRET:
        return True

    return False


class ManualSubstrateExpansionManifest(BaseModel):
    run_label: str = Field(min_length=1)
    jurisdictions: List[str] = Field(min_length=1)
    asset_classes: List[str] = Field(min_length=1)
    max_documents_per_source: int = Field(ge=1, le=100)
    run_mode: Literal["capture_only", "capture_and_ingest"]
    ocr_mode: Literal["off", "hard_doc_only"]
    sample_size_per_bucket: int = Field(ge=1, le=10)
    notes: Optional[str] = None


class PipelinePocStartRunRequest(BaseModel):
    run_label: str = Field(min_length=1)
    query: str = Field(min_length=1)
    family: str = Field(min_length=1)
    jurisdiction: str = Field(default="San Jose, CA")
    live: bool = Field(default=False)
    prefer_cached_search: bool = Field(default=False)
    allow_stale_fallback: bool = Field(default=True)
    skip_analysis: bool = Field(default=False)


class PipelinePocRunRequest(BaseModel):
    run_id: str = Field(min_length=1)


_POC_PIPELINE_RUNS: Dict[str, Dict[str, Any]] = {}


def _extract_windmill_linkage(request: Request) -> dict[str, Optional[str]]:
    flow_id = (
        request.headers.get("x-pr-windmill-flow-run-id")
        or request.headers.get("x-windmill-flow-run-id")
        or request.headers.get("x-pr-flow-run-id")
    )
    job_id = (
        request.headers.get("x-pr-windmill-job-id")
        or request.headers.get("x-windmill-job-id")
        or request.headers.get("x-pr-job-id")
    )
    return {"windmill_flow_run_id": flow_id, "windmill_job_id": job_id}


def _build_poc_pipeline_context(*, live: bool) -> Dict[str, Any]:
    from services.persisted_pipeline import (
        FixedSearchProvider,
        MockAnalysisProvider,
        MockReaderProvider,
        PersistedPipeline,
        PersistedPipelineStore,
        SearXNGSearchProvider,
        ZaiLLMAnalysisProvider,
        ZaiWebReaderProvider,
    )

    run_id = f"run_{uuid4().hex}"
    root = BACKEND_ROOT / "artifacts" / "poc_persisted_pipeline_adapter" / run_id
    db_path = root / "poc.sqlite3"
    artifact_dir = root / "object_store"
    store = PersistedPipelineStore(db_path=db_path, artifact_dir=artifact_dir)

    if live:
        search_provider = SearXNGSearchProvider()
        reader_provider = ZaiWebReaderProvider()
        analysis_provider = ZaiLLMAnalysisProvider()
    else:
        search_provider = FixedSearchProvider()
        reader_provider = MockReaderProvider()
        analysis_provider = MockAnalysisProvider()

    pipeline = PersistedPipeline(
        store=store,
        search_provider=search_provider,
        reader_provider=reader_provider,
        analysis_provider=analysis_provider,
    )
    return {
        "store": store,
        "pipeline": pipeline,
        "run_id": run_id,
        "search_response": None,
        "read_response": None,
        "analyze_response": None,
    }


def _domain_http_status(step_response: Dict[str, Any]) -> int:
    # Domain outcomes are branchable states for Windmill and should be 2xx.
    return 200


@app.post("/internal/pipeline/poc/start-run")
async def poc_start_run(request: Request, payload: PipelinePocStartRunRequest):
    if not _verify_cron_auth(request):
        raise HTTPException(status_code=401, detail="Invalid cron credentials")

    linkage = _extract_windmill_linkage(request)
    try:
        ctx = _build_poc_pipeline_context(live=payload.live)
        pipeline = ctx["pipeline"]
        store = ctx["store"]
        _ = pipeline  # satisfy linters in explicit context assignment
        run_id = store.create_run(
            run_label=payload.run_label,
            triggered_by=(
                request.headers.get("x-pr-pipeline-step") or "windmill:poc/start-run"
            ),
            now=datetime.now(timezone.utc),
            jurisdiction=payload.jurisdiction,
            target_family=payload.family,
            windmill_flow_run_id=linkage["windmill_flow_run_id"],
            windmill_job_id=linkage["windmill_job_id"],
        )
        ctx.update(
            {
                "query": payload.query,
                "family": payload.family,
                "jurisdiction": payload.jurisdiction,
                "prefer_cached_search": payload.prefer_cached_search,
                "allow_stale_fallback": payload.allow_stale_fallback,
                "skip_analysis": payload.skip_analysis,
                "windmill_flow_run_id": linkage["windmill_flow_run_id"],
                "windmill_job_id": linkage["windmill_job_id"],
            }
        )
        ctx["run_id"] = run_id
        _POC_PIPELINE_RUNS[run_id] = ctx
        return JSONResponse(
            status_code=200,
            content={
                "contract_version": "persisted-pipeline.v1",
                "run_id": run_id,
                "step": "start_run",
                "status": "succeeded",
                "decision": "run_started",
                "decision_reason": "POC run context created",
                "windmill_flow_run_id": linkage["windmill_flow_run_id"],
                "windmill_job_id": linkage["windmill_job_id"],
                "evidence": {
                    "query": payload.query,
                    "family": payload.family,
                    "live_mode": payload.live,
                },
                "alerts": [],
            },
        )
    except Exception as exc:
        logger.exception("POC start-run failed")
        raise HTTPException(status_code=503, detail=f"poc start-run failed: {exc}")


@app.post("/internal/pipeline/poc/search-materialize")
async def poc_search_materialize(request: Request, payload: PipelinePocRunRequest):
    if not _verify_cron_auth(request):
        raise HTTPException(status_code=401, detail="Invalid cron credentials")
    ctx = _POC_PIPELINE_RUNS.get(payload.run_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Unknown run_id")

    try:
        response = ctx["pipeline"]._step_search_materialize(
            run_id=payload.run_id,
            query=ctx["query"],
            family=ctx["family"],
            prefer_cached_search=ctx["prefer_cached_search"],
            allow_stale_fallback=ctx["allow_stale_fallback"],
            alerts=[],
            windmill_flow_run_id=ctx.get("windmill_flow_run_id"),
            windmill_job_id=ctx.get("windmill_job_id"),
        )
        ctx["search_response"] = response
        return JSONResponse(status_code=_domain_http_status(response), content=response)
    except Exception as exc:
        logger.exception("POC search-materialize runtime failure")
        raise HTTPException(
            status_code=503, detail=f"retryable runtime failure in search step: {exc}"
        )


@app.post("/internal/pipeline/poc/read-extract")
async def poc_read_extract(request: Request, payload: PipelinePocRunRequest):
    if not _verify_cron_auth(request):
        raise HTTPException(status_code=401, detail="Invalid cron credentials")
    ctx = _POC_PIPELINE_RUNS.get(payload.run_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Unknown run_id")
    search_response = ctx.get("search_response")
    if not search_response:
        raise HTTPException(status_code=409, detail="search step not completed")
    if search_response.get("decision") == "zero_results":
        return JSONResponse(status_code=200, content=search_response)
    snapshot_id = search_response.get("evidence", {}).get("snapshot_id")
    if not snapshot_id:
        raise HTTPException(status_code=409, detail="snapshot_id not available")

    try:
        snapshot = ctx["store"].get_snapshot(snapshot_id)
        response = ctx["pipeline"]._step_read_extract(
            run_id=payload.run_id,
            snapshot=snapshot,
            family=ctx["family"],
            alerts=[],
            windmill_flow_run_id=ctx.get("windmill_flow_run_id"),
            windmill_job_id=ctx.get("windmill_job_id"),
        )
        ctx["read_response"] = response
        return JSONResponse(status_code=_domain_http_status(response), content=response)
    except Exception as exc:
        logger.exception("POC read-extract runtime failure")
        raise HTTPException(
            status_code=503, detail=f"retryable runtime failure in read step: {exc}"
        )


@app.post("/internal/pipeline/poc/analyze")
async def poc_analyze(request: Request, payload: PipelinePocRunRequest):
    if not _verify_cron_auth(request):
        raise HTTPException(status_code=401, detail="Invalid cron credentials")
    ctx = _POC_PIPELINE_RUNS.get(payload.run_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Unknown run_id")
    read_response = ctx.get("read_response")
    if not read_response:
        raise HTTPException(status_code=409, detail="read step not completed")

    snapshot_id = (
        ctx.get("search_response", {}).get("evidence", {}).get("snapshot_id") or ""
    )
    try:
        if ctx.get("skip_analysis"):
            response = {
                "contract_version": "persisted-pipeline.v1",
                "run_id": payload.run_id,
                "windmill_flow_run_id": ctx.get("windmill_flow_run_id"),
                "windmill_job_id": ctx.get("windmill_job_id"),
                "step": "analyze",
                "status": "succeeded",
                "decision": "analysis_succeeded",
                "decision_reason": "skipped by request",
                "evidence": {"skipped": True},
                "alerts": [],
            }
        else:
            response = ctx["pipeline"]._step_analyze(
                run_id=payload.run_id,
                read_response=read_response,
                family=ctx["family"],
                snapshot_id=snapshot_id,
                alerts=[],
                windmill_flow_run_id=ctx.get("windmill_flow_run_id"),
                windmill_job_id=ctx.get("windmill_job_id"),
            )
        ctx["analyze_response"] = response
        return JSONResponse(status_code=_domain_http_status(response), content=response)
    except Exception as exc:
        logger.exception("POC analyze runtime failure")
        raise HTTPException(
            status_code=503, detail=f"retryable runtime failure in analyze step: {exc}"
        )


@app.post("/internal/pipeline/poc/finalize-report")
async def poc_finalize_report(request: Request, payload: PipelinePocRunRequest):
    if not _verify_cron_auth(request):
        raise HTTPException(status_code=401, detail="Invalid cron credentials")
    ctx = _POC_PIPELINE_RUNS.get(payload.run_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Unknown run_id")
    search_response = ctx.get("search_response")
    if not search_response:
        raise HTTPException(status_code=409, detail="search step not completed")

    if search_response.get("decision") == "zero_results":
        response = {
            "contract_version": "persisted-pipeline.v1",
            "run_id": payload.run_id,
            "windmill_flow_run_id": ctx.get("windmill_flow_run_id"),
            "windmill_job_id": ctx.get("windmill_job_id"),
            "step": "finalize",
            "status": "succeeded",
            "decision": "zero_results",
            "decision_reason": "search returned zero results; pipeline terminated",
            "evidence": search_response.get("evidence", {}),
            "alerts": search_response.get("alerts", []),
        }
        ctx["store"].complete_run(
            payload.run_id,
            "completed",
            response,
            response.get("alerts", []),
            datetime.now(timezone.utc),
        )
        ctx["store"].close()
        _POC_PIPELINE_RUNS.pop(payload.run_id, None)
        return JSONResponse(status_code=200, content=response)

    read_response = ctx.get("read_response")
    analyze_response = ctx.get("analyze_response")
    if not read_response:
        raise HTTPException(status_code=409, detail="read step not completed")
    if not analyze_response:
        raise HTTPException(status_code=409, detail="analyze step not completed")

    child_statuses = {
        "read": read_response.get("status"),
        "analyze": analyze_response.get("status"),
    }
    child_decisions = {
        "read": read_response.get("decision"),
        "analyze": analyze_response.get("decision"),
    }
    child_reasons = {
        "read": read_response.get("decision_reason"),
        "analyze": analyze_response.get("decision_reason"),
    }
    failing_children = [
        step
        for step, status in child_statuses.items()
        if status in {"failed", "blocked"}
    ]
    child_alerts = read_response.get("alerts", []) + analyze_response.get("alerts", [])
    alerts = search_response.get("alerts", []) + child_alerts

    if failing_children:
        has_blocked = any(
            child_statuses[step] == "blocked" for step in failing_children
        )
        final_status = "blocked" if has_blocked else "failed"
        final_decision = "downstream_blocked" if has_blocked else "downstream_failed"
        detail = ", ".join(
            f"{step}:{child_statuses[step]}/{child_decisions.get(step) or 'unknown'}"
            for step in failing_children
        )
        decision_reason = (
            f"finalize detected non-succeeded downstream step(s): {detail}"
        )
        alerts = alerts + [
            {
                "severity": "WARN" if has_blocked else "ERROR",
                "code": "poc_finalize_child_step_not_succeeded",
                "message": decision_reason,
                "failing_steps": failing_children,
            }
        ]
    else:
        final_status = "succeeded"
        final_decision = search_response.get("decision", "fresh_snapshot")
        decision_reason = "pipeline step sequence finalized"

    response = {
        "contract_version": "persisted-pipeline.v1",
        "run_id": payload.run_id,
        "windmill_flow_run_id": ctx.get("windmill_flow_run_id"),
        "windmill_job_id": ctx.get("windmill_job_id"),
        "step": "finalize",
        "status": final_status,
        "decision": final_decision,
        "decision_reason": decision_reason,
        "evidence": {
            "snapshot_id": search_response.get("evidence", {}).get("snapshot_id"),
            "result_count": search_response.get("evidence", {}).get("result_count", 0),
            "search_decision": search_response.get("decision"),
            "read_decision": child_decisions.get("read"),
            "read_status": child_statuses.get("read"),
            "read_decision_reason": child_reasons.get("read"),
            "analyze_decision": child_decisions.get("analyze"),
            "analyze_status": child_statuses.get("analyze"),
            "analyze_decision_reason": child_reasons.get("analyze"),
            "failing_steps": failing_children,
        },
        "alerts": alerts,
    }
    ctx["store"].complete_run(
        payload.run_id,
        "completed" if final_status == "succeeded" else final_status,
        response,
        response.get("alerts", []),
        datetime.now(timezone.utc),
    )
    ctx["store"].close()
    _POC_PIPELINE_RUNS.pop(payload.run_id, None)
    return JSONResponse(status_code=200, content=response)


@app.post("/internal/pipeline/poc/zai-search-canary")
async def poc_zai_search_canary(request: Request):
    if not _verify_cron_auth(request):
        raise HTTPException(status_code=401, detail="Invalid cron credentials")
    return {
        "status": "succeeded",
        "decision": "zai_direct_search_deprecated",
        "decision_reason": "Z.ai direct web search remains canary-only and excluded from product flow",
        "ZAI_DIRECT_SEARCH_DEPRECATED": True,
    }


@app.post("/cron/discovery")
async def cron_discovery(request: Request):
    """
    Authenticated cron trigger for discovery pipeline.
    Replaces Railway Cron scheduling for this job.
    Auth: Authorization: Bearer $CRON_SECRET or X-Cron-Secret: $CRON_SECRET
    """
    if not _verify_cron_auth(request):
        raise HTTPException(status_code=401, detail="Invalid cron credentials")

    logger.info("Cron trigger: discovery run")
    result = await _run_script_job(
        _backend_script_path("scripts/cron/run_discovery.py"), "discovery"
    )
    if result["status"] != "succeeded":
        raise HTTPException(status_code=500, detail=result)
    return result


@app.post("/cron/daily-scrape")
async def cron_daily_scrape(request: Request):
    """
    Cron endpoint to scrape all jurisdictions daily.
    Auth: Authorization: Bearer $CRON_SECRET or X-Cron-Secret: $CRON_SECRET
    """
    if not _verify_cron_auth(request):
        raise HTTPException(status_code=401, detail="Invalid cron credentials")

    logger.info("Cron trigger: daily scrape")
    result = await _run_script_job(
        _backend_script_path("scripts/cron/run_daily_scrape.py"), "daily_scrape"
    )
    if result["status"] != "succeeded":
        raise HTTPException(status_code=500, detail=result)
    return result


@app.post("/cron/rag-spiders")
async def cron_rag_spiders(request: Request):
    """
    Authenticated cron trigger for RAG spiders.
    Auth: Authorization: Bearer $CRON_SECRET or X-Cron-Secret: $CRON_SECRET
    """
    if not _verify_cron_auth(request):
        raise HTTPException(status_code=401, detail="Invalid cron credentials")

    logger.info("Cron trigger: rag spiders")
    result = await _run_script_job(
        _backend_script_path("scripts/cron/run_rag_spiders.py"), "rag_spiders"
    )
    if result["status"] != "succeeded":
        raise HTTPException(status_code=500, detail=result)
    return result


@app.post("/cron/universal-harvester")
async def cron_universal_harvester(request: Request):
    """
    Authenticated cron trigger for universal harvester.
    Auth: Authorization: Bearer $CRON_SECRET or X-Cron-Secret: $CRON_SECRET
    """
    if not _verify_cron_auth(request):
        raise HTTPException(status_code=401, detail="Invalid cron credentials")

    logger.info("Cron trigger: universal harvester")
    result = await _run_script_job(
        _backend_script_path("scripts/cron/run_universal_harvester.py"),
        "universal_harvester",
    )
    if result["status"] != "succeeded":
        raise HTTPException(status_code=500, detail=result)
    return result


@app.post("/cron/manual-substrate-expansion")
async def cron_manual_substrate_expansion(
    request: Request,
    manifest: ManualSubstrateExpansionManifest,
):
    """
    Authenticated manual trigger for broad substrate expansion runs.
    This endpoint currently returns a truthful planning/skeleton payload and does
    not execute the full capture pipeline inline.
    """
    if not _verify_cron_auth(request):
        raise HTTPException(status_code=401, detail="Invalid cron credentials")
    requested = manifest.model_dump()
    response = await run_manual_substrate_expansion(requested)
    logger.info(
        "Cron manual substrate expansion completed: run_id=%s run_label=%s status=%s",
        response["run_id"],
        requested["run_label"],
        response["status"],
    )
    return response


async def _run_script_job(script_path: str, job_name: str):
    """Run a cron script job synchronously and return a serializable result."""
    import asyncio
    import sys

    logger.info(f"Cron job '{job_name}' starting: {script_path}")
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")
        result = {
            "job": job_name,
            "script_path": script_path,
            "exit_code": proc.returncode,
            "status": "succeeded" if proc.returncode == 0 else "failed",
            "stdout_tail": stdout_text[-4000:],
            "stderr_tail": stderr_text[-4000:],
        }
        if proc.returncode != 0:
            logger.error(
                f"Cron job '{job_name}' failed (exit {proc.returncode}): {result['stderr_tail'][-500:]}"
            )
        else:
            logger.info(f"Cron job '{job_name}' succeeded (exit {proc.returncode})")
        return result
    except Exception as e:
        logger.error(f"Cron job '{job_name}' exception: {e}")
        return {
            "job": job_name,
            "script_path": script_path,
            "exit_code": -1,
            "status": "failed",
            "stdout_tail": "",
            "stderr_tail": str(e),
        }


@app.post("/scrape/{jurisdiction}")
async def scrape_and_analyze(jurisdiction: str) -> Dict[str, Any]:
    """
    Scrape legislation from a jurisdiction, analyze with LLM, and store in database.
    """
    if jurisdiction not in SCRAPERS:
        raise HTTPException(
            status_code=404, detail=f"Jurisdiction '{jurisdiction}' not supported"
        )

    scraper_class, jur_type = SCRAPERS[jurisdiction]
    result = await process_jurisdiction(jurisdiction, scraper_class, jur_type)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@app.get("/legislation/{jurisdiction}")
async def get_legislation(jurisdiction: str, limit: int = 10):
    """
    Get stored legislation for a jurisdiction with impacts.
    """
    if jurisdiction not in SCRAPERS:
        raise HTTPException(
            status_code=404, detail=f"Jurisdiction '{jurisdiction}' not supported"
        )

    scraper_class, _ = SCRAPERS[jurisdiction]
    scraper = scraper_class()

    legislation_data = await db.get_legislation_by_jurisdiction(
        jurisdiction_name=scraper.jurisdiction_name, limit=limit
    )

    # Adapt to the frontend's expected format
    legislation_list = []
    for leg in legislation_data:
        for impact in leg.get("impacts", []):
            if "confidence_score" in impact:
                impact["confidence"] = impact.pop("confidence_score")
        quantified_impacts = [
            i for i in leg.get("impacts", []) if i.get("p50") is not None
        ]
        legislation_list.append(
            {
                "bill_number": leg.get("bill_number"),
                "title": leg.get("title"),
                "jurisdiction": leg.get("jurisdiction", jurisdiction),
                "status": leg.get("status"),
                "impacts": leg.get("impacts", []),
                "total_impact_p50": (
                    sum(i["p50"] for i in quantified_impacts)
                    if quantified_impacts
                    else None
                ),
                "sufficiency_state": leg.get("sufficiency_state"),
                "insufficiency_reason": leg.get("insufficiency_reason"),
                "quantification_eligible": leg.get("quantification_eligible"),
                "analysis_timestamp": (
                    leg.get("created_at").isoformat() if leg.get("created_at") else None
                ),
                "model_used": "n/a",
            }
        )

    return {
        "jurisdiction": jurisdiction,
        "count": len(legislation_list),
        "legislation": legislation_list,
    }


@app.get("/legislation/{jurisdiction}/{bill_number}")
async def get_bill_details(jurisdiction: str, bill_number: str):
    """
    Get details for a specific bill including impacts.
    """
    if jurisdiction not in SCRAPERS:
        raise HTTPException(
            status_code=404, detail=f"Jurisdiction '{jurisdiction}' not supported"
        )

    bill = await db.get_bill(jurisdiction, bill_number)

    if not bill:
        raise HTTPException(
            status_code=404, detail=f"Bill '{bill_number}' not found in {jurisdiction}"
        )

    return bill
