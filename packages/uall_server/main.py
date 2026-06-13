import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure project root is on path for storage adapters
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from storage.adapters.file import get_storage
from uall.service import UALLService
from uall_core.schemas.common import PolicyVersion, Skill
from uall_core.schemas.events import Event, Feedback, RunEnd, RunStart
from uall_core.schemas.lesson import CandidateLesson, Lesson, MemorySearchRequest

API_KEY = os.environ.get("UALL_API_KEY", "dev-key-change-me")
service: UALLService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global service
    storage = get_storage()
    service = UALLService(storage)
    await service.init()
    yield


app = FastAPI(title="UALL — Universal Agent Learning Layer", version="0.1.0", lifespan=lifespan)


def verify_key(x_uall_key: str = Header(default="")):
    if x_uall_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_uall_key


def get_service() -> UALLService:
    assert service is not None
    return service


@app.get("/health")
async def health():
    return {"status": "ok", "service": "uall"}


# --- Runs ---
@app.post("/runs/start", dependencies=[Depends(verify_key)])
async def runs_start(data: RunStart, svc: UALLService = Depends(get_service)):
    return await svc.start_run(data)


@app.post("/runs/event", dependencies=[Depends(verify_key)])
async def runs_event(event: Event, svc: UALLService = Depends(get_service)):
    return await svc.record_event(event)


@app.post("/runs/end", dependencies=[Depends(verify_key)])
async def runs_end(data: RunEnd, svc: UALLService = Depends(get_service)):
    return await svc.end_run(data)


@app.post("/feedback", dependencies=[Depends(verify_key)])
async def feedback(data: Feedback, svc: UALLService = Depends(get_service)):
    return await svc.record_feedback(data)


# --- Reflection & validation ---
class ReflectRequest(BaseModel):
    candidate: CandidateLesson


@app.post("/reflection", dependencies=[Depends(verify_key)])
async def reflection(req: ReflectRequest, svc: UALLService = Depends(get_service)):
    return await svc.reflect_and_queue(req.candidate)


@app.post("/memory/validate", dependencies=[Depends(verify_key)])
async def memory_validate(req: ReflectRequest, svc: UALLService = Depends(get_service)):
    result = await svc.validate_lesson(req.candidate)
    return result.model_dump(mode="json")


@app.post("/memory/store", dependencies=[Depends(verify_key)])
async def memory_store(lesson: Lesson, svc: UALLService = Depends(get_service)):
    lid = await svc.store_lesson(lesson)
    return {"lesson_id": lid}


@app.post("/memory/search", dependencies=[Depends(verify_key)])
async def memory_search(req: MemorySearchRequest, svc: UALLService = Depends(get_service)):
    results = await svc.retrieve(req)
    return [
        {
            "lesson": r.lesson.model_dump(mode="json"),
            "score": r.score,
            "telemetry_id": r.telemetry_id,
        }
        for r in results
    ]


@app.get("/memory/{lesson_id}/provenance", dependencies=[Depends(verify_key)])
async def memory_provenance(lesson_id: str, svc: UALLService = Depends(get_service)):
    prov = await svc.get_provenance(lesson_id)
    if not prov:
        raise HTTPException(404, "Lesson not found")
    return prov


@app.get("/memory/{lesson_id}/graph", dependencies=[Depends(verify_key)])
async def memory_graph(lesson_id: str, svc: UALLService = Depends(get_service)):
    graph = await svc.get_graph(lesson_id)
    if not graph:
        raise HTTPException(404, "Lesson not found")
    return graph


@app.post("/memory/prune", dependencies=[Depends(verify_key)])
async def memory_prune(svc: UALLService = Depends(get_service)):
    return await svc.prune_memory()


# --- Promotion ---
@app.get("/promotion/pending", dependencies=[Depends(verify_key)])
async def promotion_pending(svc: UALLService = Depends(get_service)):
    return await svc.list_pending()


@app.post("/promotion/process", dependencies=[Depends(verify_key)])
async def promotion_process(svc: UALLService = Depends(get_service)):
    return await svc.process_promotion_queue()


# --- Telemetry ---
class TelemetryRequest(BaseModel):
    lesson_id: str
    telemetry_id: str | None = None
    run_id: str | None = None
    used: bool = False
    accepted: bool = False
    improved: bool | None = None


@app.post("/telemetry/lesson-outcome", dependencies=[Depends(verify_key)])
async def telemetry_outcome(req: TelemetryRequest, svc: UALLService = Depends(get_service)):
    return await svc.record_lesson_outcome(
        req.lesson_id, req.telemetry_id, req.run_id, req.used, req.accepted, req.improved
    )


# --- Policies ---
@app.get("/policies", dependencies=[Depends(verify_key)])
async def get_policies(svc: UALLService = Depends(get_service)):
    policies = await svc.get_policies()
    return [p.model_dump(mode="json") for p in policies]


@app.post("/policies", dependencies=[Depends(verify_key)])
async def create_policy(policy: PolicyVersion, svc: UALLService = Depends(get_service)):
    pid = await svc.create_policy(policy)
    return {"policy_id": pid}


@app.get("/policies/versions", dependencies=[Depends(verify_key)])
async def policy_versions(policy_id: str, svc: UALLService = Depends(get_service)):
    versions = await svc.list_policy_versions(policy_id)
    return [v.model_dump(mode="json") for v in versions]


# --- Evaluation & analytics ---
@app.post("/evaluate", dependencies=[Depends(verify_key)])
async def evaluate(run_id: str, svc: UALLService = Depends(get_service)):
    return await svc.evaluate(run_id)


@app.get("/agent-score", dependencies=[Depends(verify_key)])
async def agent_score(agent_id: str | None = None, svc: UALLService = Depends(get_service)):
    return await svc.agent_score(agent_id)


@app.get("/analytics", dependencies=[Depends(verify_key)])
async def analytics(svc: UALLService = Depends(get_service)):
    return await svc.get_analytics()


@app.get("/workflow-health", dependencies=[Depends(verify_key)])
async def workflow_health(workflow_id: str, svc: UALLService = Depends(get_service)):
    return await svc.workflow_health(workflow_id)


@app.get("/top-failures", dependencies=[Depends(verify_key)])
async def top_failures(svc: UALLService = Depends(get_service)):
    return await svc.top_failures()


# --- Recommendations ---
class RecommendationRequest(BaseModel):
    agent_id: str | None = None
    workflow_id: str | None = None
    context: str | None = None


@app.post("/recommendations", dependencies=[Depends(verify_key)])
async def recommendations(req: RecommendationRequest, svc: UALLService = Depends(get_service)):
    return await svc.get_recommendations(
        agent_id=req.agent_id, workflow_id=req.workflow_id, context=req.context
    )


@app.post("/recommendations/patterns", dependencies=[Depends(verify_key)])
async def recommendation_patterns(svc: UALLService = Depends(get_service)):
    return await svc.detect_patterns()


# --- Experiments ---
class ExperimentStartRequest(BaseModel):
    resource_type: str
    resource_id: str
    variant_a: str
    variant_b: str
    traffic_split: float = 0.1


@app.post("/experiments/start", dependencies=[Depends(verify_key)])
async def experiments_start(req: ExperimentStartRequest, svc: UALLService = Depends(get_service)):
    exp = await svc.start_experiment(**req.model_dump())
    return exp.model_dump(mode="json")


@app.post("/experiments/end", dependencies=[Depends(verify_key)])
async def experiments_end(experiment_id: str, svc: UALLService = Depends(get_service)):
    exp = await svc.end_experiment(experiment_id)
    return exp.model_dump(mode="json")


@app.get("/experiments/{experiment_id}/results", dependencies=[Depends(verify_key)])
async def experiment_results(experiment_id: str, svc: UALLService = Depends(get_service)):
    exp = await svc.experiment_results(experiment_id)
    if not exp:
        raise HTTPException(404, "Experiment not found")
    return exp.model_dump(mode="json")


# --- Rollback ---
class RollbackRequest(BaseModel):
    resource_type: str
    resource_id: str
    target_version: str


@app.post("/rollback", dependencies=[Depends(verify_key)])
async def rollback(req: RollbackRequest, svc: UALLService = Depends(get_service)):
    return await svc.rollback_resource(req.resource_type, req.resource_id, req.target_version)


@app.get("/versions/{resource_type}/{resource_id}", dependencies=[Depends(verify_key)])
async def versions(resource_type: str, resource_id: str, svc: UALLService = Depends(get_service)):
    records = await svc.list_versions(resource_type, resource_id)
    return [r.model_dump(mode="json") for r in records]


# --- Skills ---
@app.post("/skills", dependencies=[Depends(verify_key)])
async def create_skill(skill: Skill, svc: UALLService = Depends(get_service)):
    sid = await svc.create_skill(skill)
    return {"skill_id": sid}


@app.get("/skills/search", dependencies=[Depends(verify_key)])
async def search_skills(query: str, svc: UALLService = Depends(get_service)):
    skills = await svc.search_skills(query)
    return [s.model_dump(mode="json") for s in skills]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("uall_server.main:app", host="0.0.0.0", port=8000, reload=False)
