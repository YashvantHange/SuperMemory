"""Unified MCP tool handlers — GitHub-compatible + extended learn.* tools."""

from __future__ import annotations

import json
import uuid

from supermemory_mcp.bridge import SuperMemoryBridge
from uall_core.schemas.common import PolicyVersion, Skill
from uall_core.schemas.events import Event, EventType, Feedback, RunEnd, RunStart, StageMetadata
from uall_core.schemas.lesson import CandidateLesson, Lesson, MemorySearchRequest

_bridge: SuperMemoryBridge | None = None
_data_dir: str | None = None


def _get_bridge(data_dir: str | None = None) -> SuperMemoryBridge:
    global _bridge, _data_dir
    if data_dir and data_dir != _data_dir:
        _bridge = SuperMemoryBridge(data_dir)
        _data_dir = data_dir
    if _bridge is None:
        _bridge = SuperMemoryBridge(data_dir)
        _data_dir = data_dir
    return _bridge


def reset_service() -> None:
    global _bridge, _data_dir
    _bridge = None
    _data_dir = None


async def get_service(data_dir: str | None = None):
    bridge = _get_bridge(data_dir)
    return await bridge.service()


def _parse_namespace(namespace: str | None) -> tuple[str | None, str | None]:
    if namespace and ":" in namespace:
        level, ns_id = namespace.split(":", 1)
        return level, ns_id
    if namespace == "global":
        return "global", None
    return None, namespace


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

GITHUB_TOOLS = [
    {
        "name": "retrieve",
        "description": "Retrieve policy-first, stage-aware lessons.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "workflow": {"type": "string"},
                "step": {"type": "string"},
                "tool": {"type": "string"},
                "agent": {"type": "string"},
                "domain": {"type": "string"},
                "language": {"type": "string"},
                "environment": {"type": "string"},
                "namespace": {"type": "string", "default": "global"},
                "top_k": {"type": "integer", "default": 5},
                "max_tokens": {"type": "integer", "default": 800},
            },
            "required": ["query"],
        },
    },
    {
        "name": "record_event",
        "description": "Record a bounded significant event. Full transcripts should not be sent here.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "event_type": {"type": "string"},
                "summary": {"type": "string"},
                "workflow": {"type": "string"},
                "step": {"type": "string"},
                "tool": {"type": "string"},
                "agent": {"type": "string"},
                "domain": {"type": "string"},
                "language": {"type": "string"},
                "environment": {"type": "string"},
                "namespace": {"type": "string", "default": "global"},
                "payload": {"type": "object"},
            },
            "required": ["event_type", "summary"],
        },
    },
    {
        "name": "record_failure",
        "description": "Record a bounded failure signal.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "workflow": {"type": "string"},
                "step": {"type": "string"},
                "tool": {"type": "string"},
                "agent": {"type": "string"},
                "domain": {"type": "string"},
                "language": {"type": "string"},
                "environment": {"type": "string"},
                "namespace": {"type": "string", "default": "global"},
                "payload": {"type": "object"},
            },
            "required": ["summary"],
        },
    },
    {
        "name": "record_correction",
        "description": "Record a bounded correction signal.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "workflow": {"type": "string"},
                "step": {"type": "string"},
                "tool": {"type": "string"},
                "agent": {"type": "string"},
                "domain": {"type": "string"},
                "language": {"type": "string"},
                "environment": {"type": "string"},
                "namespace": {"type": "string", "default": "global"},
                "payload": {"type": "object"},
            },
            "required": ["summary"],
        },
    },
    {
        "name": "reflect",
        "description": "Create a candidate lesson from evidence events.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "event_ids": {"type": "array", "items": {"type": "string"}},
                "suggestion": {"type": "string"},
                "lesson_text": {"type": "string"},
            },
            "required": ["event_ids"],
        },
    },
    {
        "name": "validate",
        "description": "Validate a lesson candidate and enqueue approved lessons for promotion.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reflection_id": {"type": "string"},
                "candidate_lesson": {"type": "string"},
                "event_ids": {"type": "array", "items": {"type": "string"}},
                "metadata": {"type": "object"},
            },
        },
    },
    {
        "name": "process_promotions",
        "description": "Process pending validated lessons and promote passing items.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 50}},
        },
    },
    {
        "name": "report_outcome",
        "description": "Report telemetry for a retrieved lesson.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "string"},
                "used": {"type": "boolean"},
                "accepted": {"type": "boolean"},
                "improved": {"type": "boolean"},
                "retrieval_id": {"type": "string"},
                "run_id": {"type": "string"},
            },
            "required": ["lesson_id", "used", "accepted", "improved"],
        },
    },
    {
        "name": "get_policies",
        "description": "Return active policies visible to a namespace.",
        "inputSchema": {
            "type": "object",
            "properties": {"namespace": {"type": "string", "default": "global"}},
        },
    },
    {
        "name": "add_policy",
        "description": "Add a local policy rule.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rule": {"type": "string"},
                "namespace": {"type": "string", "default": "global"},
                "priority": {"type": "integer", "default": 100},
            },
            "required": ["rule"],
        },
    },
    {
        "name": "add_skill",
        "description": "Add a reusable skill/workflow block.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "steps": {"type": "array", "items": {"type": "string"}},
                "workflow": {"type": "string"},
                "tools": {"type": "array", "items": {"type": "string"}},
                "namespace": {"type": "string", "default": "global"},
                "version": {"type": "string", "default": "0.1.0"},
                "metadata": {"type": "object"},
            },
            "required": ["name", "description", "steps"],
        },
    },
    {
        "name": "search_skills",
        "description": "Search reusable skills visible to a namespace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "workflow": {"type": "string"},
                "namespace": {"type": "string", "default": "global"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_skill",
        "description": "Read a reusable skill by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {"skill_id": {"type": "string"}},
            "required": ["skill_id"],
        },
    },
]

LEARN_TOOLS = [
    {
        "name": "learn.run.start",
        "description": "Start a UALL run with workflow and step metadata",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string"},
                "step": {"type": "string"},
                "agents": {"type": "array", "items": {"type": "string"}},
                "namespace": {"type": "string"},
                "agent": {"type": "string"},
            },
            "required": ["workflow_id"],
        },
    },
    {
        "name": "learn.run.event",
        "description": "Record a selective event (failure, correction, suggestion, workflow_step)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "event_type": {"type": "string"},
                "snippet": {"type": "string"},
                "before": {"type": "string"},
                "after": {"type": "string"},
                "intent": {"type": "string"},
                "workflow": {"type": "string"},
                "step": {"type": "string"},
                "agent": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["run_id", "event_type"],
        },
    },
    {
        "name": "learn.run.end",
        "description": "End a UALL run with outcome and lessons used",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "success": {"type": "boolean"},
                "lessons_used": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["run_id", "success"],
        },
    },
    {
        "name": "learn.store",
        "description": "Store a validated lesson (post-validation only)",
        "inputSchema": {
            "type": "object",
            "properties": {"lesson_json": {"type": "string"}},
            "required": ["lesson_json"],
        },
    },
    {
        "name": "learn.retrieve",
        "description": "Retrieve lessons for a workflow step (hybrid pipeline)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "workflow": {"type": "string"},
                "step": {"type": "string"},
                "namespace": {"type": "string"},
                "max_tokens": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "learn.reflect",
        "description": "Reflect on evidence events and queue for promotion (requires event_ids)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "event_ids": {"type": "array", "items": {"type": "string"}},
                "suggestion": {"type": "string"},
                "failure": {"type": "string"},
                "root_cause": {"type": "string"},
                "fix": {"type": "string"},
                "workflow": {"type": "string"},
                "step": {"type": "string"},
                "auto_promote": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "learn.validate",
        "description": "Validate a candidate lesson without storing",
        "inputSchema": {
            "type": "object",
            "properties": {
                "failure": {"type": "string"},
                "root_cause": {"type": "string"},
                "fix": {"type": "string"},
                "event_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["failure", "fix"],
        },
    },
    {
        "name": "learn.evaluate",
        "description": "Evaluate a completed run",
        "inputSchema": {
            "type": "object",
            "properties": {"run_id": {"type": "string"}},
            "required": ["run_id"],
        },
    },
    {
        "name": "learn.feedback",
        "description": "Record user feedback or correction",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rating": {"type": "string"},
                "comment": {"type": "string"},
                "run_id": {"type": "string"},
            },
            "required": ["rating"],
        },
    },
    {
        "name": "learn.improvements",
        "description": "Get actionable recommendations from distilled lessons",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string"},
                "agent_id": {"type": "string"},
            },
        },
    },
    {
        "name": "learn.analytics",
        "description": "Get UALL analytics summary",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "learn.policies",
        "description": "Get organization policies (injected before lessons)",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "learn.experiment",
        "description": "Start an A/B experiment for prompt or workflow change",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_id": {"type": "string"},
                "variant_b": {"type": "string"},
                "traffic_split": {"type": "number"},
            },
            "required": ["resource_id", "variant_b"],
        },
    },
    {
        "name": "learn.rollback",
        "description": "Rollback a prompt, workflow, or lesson version",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_type": {"type": "string"},
                "resource_id": {"type": "string"},
                "target_version": {"type": "string"},
            },
            "required": ["resource_type", "resource_id", "target_version"],
        },
    },
    {
        "name": "learn.skills",
        "description": "Search the versioned skill library",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "learn.telemetry",
        "description": "Report lesson outcome: retrieved → used → accepted → improved",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "string"},
                "run_id": {"type": "string"},
                "used": {"type": "boolean"},
                "accepted": {"type": "boolean"},
                "improved": {"type": "boolean"},
                "telemetry_id": {"type": "string"},
            },
            "required": ["lesson_id"],
        },
    },
]

TOOLS = GITHUB_TOOLS + LEARN_TOOLS


async def handle_tool(name: str, arguments: dict, data_dir: str | None = None) -> str:
    svc = await get_service(data_dir)
    args = arguments or {}

    # --- GitHub-compatible tools ---
    if name == "record_event":
        return json.dumps(
            await svc.record_mcp_event(
                args["event_type"],
                args["summary"],
                workflow=args.get("workflow"),
                step=args.get("step"),
                tool=args.get("tool"),
                agent=args.get("agent"),
                domain=args.get("domain"),
                language=args.get("language"),
                environment=args.get("environment"),
                namespace=args.get("namespace", "global"),
                payload=args.get("payload"),
            )
        )

    if name == "record_failure":
        return json.dumps(
            await svc.record_mcp_event(
                "failure",
                args["summary"],
                workflow=args.get("workflow"),
                step=args.get("step"),
                tool=args.get("tool"),
                agent=args.get("agent"),
                domain=args.get("domain"),
                language=args.get("language"),
                environment=args.get("environment"),
                namespace=args.get("namespace", "global"),
                payload=args.get("payload"),
            )
        )

    if name == "record_correction":
        return json.dumps(
            await svc.record_mcp_event(
                "correction",
                args["summary"],
                workflow=args.get("workflow"),
                step=args.get("step"),
                tool=args.get("tool"),
                agent=args.get("agent"),
                domain=args.get("domain"),
                language=args.get("language"),
                environment=args.get("environment"),
                namespace=args.get("namespace", "global"),
                payload=args.get("payload"),
            )
        )

    if name == "reflect":
        try:
            return json.dumps(
                await svc.reflect_from_events(
                    args["event_ids"],
                    suggestion=args.get("suggestion"),
                    lesson_text=args.get("lesson_text"),
                )
            )
        except ValueError as exc:
            return json.dumps({"error": str(exc)})

    if name == "validate":
        return json.dumps(
            await svc.validate_and_enqueue(
                reflection_id=args.get("reflection_id"),
                candidate_lesson=args.get("candidate_lesson"),
                event_ids=args.get("event_ids"),
                metadata=args.get("metadata"),
            )
        )

    if name == "process_promotions":
        return json.dumps(await svc.process_promotion_queue(limit=args.get("limit", 50)))

    if name == "retrieve":
        return json.dumps(
            await svc.retrieve_for_mcp(
                args["query"],
                workflow=args.get("workflow"),
                step=args.get("step"),
                tool=args.get("tool"),
                agent=args.get("agent"),
                domain=args.get("domain"),
                language=args.get("language"),
                environment=args.get("environment"),
                namespace=args.get("namespace", "global"),
                top_k=args.get("top_k", 5),
                max_tokens=args.get("max_tokens", 800),
            )
        )

    if name == "report_outcome":
        return json.dumps(
            await svc.report_outcome(
                args["lesson_id"],
                args["used"],
                args["accepted"],
                args["improved"],
                retrieval_id=args.get("retrieval_id"),
                run_id=args.get("run_id"),
            )
        )

    if name == "get_policies":
        policies = await svc.get_policies()
        return json.dumps({"policies": [p.model_dump(mode="json") for p in policies]})

    if name == "add_policy":
        return json.dumps(
            await svc.add_policy_rule(
                args["rule"],
                namespace=args.get("namespace", "global"),
                priority=args.get("priority", 100),
            )
        )

    if name == "add_skill":
        return json.dumps(
            await svc.add_mcp_skill(
                args["name"],
                args["description"],
                args["steps"],
                workflow=args.get("workflow"),
                tools=args.get("tools"),
                namespace=args.get("namespace", "global"),
                version=args.get("version", "0.1.0"),
                metadata=args.get("metadata"),
            )
        )

    if name == "search_skills":
        skills = await svc.search_mcp_skills(
            args["query"],
            workflow=args.get("workflow"),
            namespace=args.get("namespace", "global"),
            top_k=args.get("top_k", 5),
        )
        return json.dumps({"skills": skills})

    if name == "get_skill":
        skill = await svc.get_mcp_skill(args["skill_id"])
        return json.dumps(skill or {"error": "not_found"})

    # --- Extended learn.* tools ---
    if name == "learn.run.start":
        ns_level, ns_id = _parse_namespace(args.get("namespace"))
        stage = StageMetadata(
            workflow=args["workflow_id"],
            step=args.get("step"),
            agent=args.get("agent"),
            namespace=ns_level,
            namespace_id=ns_id,
        )
        run_id = args.get("run_id") or f"run_{uuid.uuid4().hex[:8]}"
        start = RunStart(
            run_id=run_id,
            workflow_id=args["workflow_id"],
            agents=args.get("agents", []),
            stage=stage,
        )
        result = await svc.start_run(start)
        result["run_id"] = run_id
        return json.dumps(result)

    if name == "learn.run.event":
        stage = StageMetadata(
            workflow=args.get("workflow"),
            step=args.get("step"),
            agent=args.get("agent"),
        )
        etype = args["event_type"]
        payload: dict = {}
        if etype == "failure":
            payload = {"snippet": args.get("snippet", "")[:500], "summary": args.get("snippet", "")[:500]}
        elif etype == "correction":
            payload = {
                "before": args.get("before", "")[:300],
                "after": args.get("after", "")[:300],
                "intent": args.get("intent", ""),
                "summary": args.get("after", "")[:500],
            }
        elif etype == "workflow_step":
            payload = {"outcome": args.get("outcome", "ok")}
        event = Event(
            event_id=f"{etype}_{uuid.uuid4().hex[:8]}",
            event_type=EventType(etype) if etype in EventType._value2member_map_ else EventType.FAILURE,
            run_id=args["run_id"],
            stage=stage,
            tags=args.get("tags", []),
            payload=payload,
        )
        return json.dumps(await svc.record_event(event))

    if name == "learn.run.end":
        end = RunEnd(
            run_id=args["run_id"],
            success=args["success"],
            lessons_used=args.get("lessons_used", []),
        )
        return json.dumps(await svc.end_run(end))

    if name == "learn.store":
        lesson_data = json.loads(args["lesson_json"])
        lesson = Lesson(**lesson_data)
        lid = await svc.store_lesson(lesson)
        return json.dumps({"lesson_id": lid, "stored": True})

    if name == "learn.retrieve":
        result = await svc.retrieve_for_mcp(
            args.get("query", ""),
            workflow=args.get("workflow"),
            step=args.get("step"),
            namespace=args.get("namespace", "global"),
            max_tokens=args.get("max_tokens", 800),
        )
        return json.dumps(result)

    if name == "learn.reflect":
        event_ids = args.get("event_ids", [])
        if not event_ids:
            return json.dumps({"status": "rejected", "reason": "event_ids required for evidence-first reflection"})
        reflection = await svc.reflect_from_events(
            event_ids,
            suggestion=args.get("suggestion") or args.get("fix"),
            lesson_text=args.get("fix"),
        )
        validation = await svc.validate_and_enqueue(
            reflection_id=reflection["id"],
            event_ids=event_ids,
        )
        if validation.get("action") == "reject":
            return json.dumps({"status": "rejected", "reason": validation.get("reason"), "reflection_id": reflection["id"]})
        result = {
            "status": "queued",
            "reflection_id": reflection["id"],
            "pending_id": validation.get("pending_id"),
            "validation": validation,
        }
        if args.get("auto_promote"):
            result["promotion"] = await svc.process_promotion_queue()
        return json.dumps(result)

    if name == "learn.validate":
        candidate = CandidateLesson(
            reflection_id="",
            failure=args["failure"],
            root_cause=args.get("root_cause", ""),
            fix=args["fix"],
            evidence_payload=args,
            event_ids=args.get("event_ids", []),
        )
        result = await svc.validate_lesson(candidate)
        return json.dumps(result.model_dump(mode="json"))

    if name == "learn.evaluate":
        return json.dumps(await svc.evaluate(args["run_id"]))

    if name == "learn.feedback":
        fb = Feedback(
            rating=args["rating"],
            comment=args.get("comment"),
            run_id=args.get("run_id"),
        )
        return json.dumps(await svc.record_feedback(fb))

    if name == "learn.improvements":
        return json.dumps(
            await svc.get_recommendations(
                workflow_id=args.get("workflow_id"),
                agent_id=args.get("agent_id"),
            )
        )

    if name == "learn.analytics":
        return json.dumps(await svc.get_analytics())

    if name == "learn.policies":
        policies = await svc.get_policies()
        return json.dumps([p.model_dump(mode="json") for p in policies])

    if name == "learn.experiment":
        exp = await svc.start_experiment(
            resource_type="prompt",
            resource_id=args["resource_id"],
            variant_a="current",
            variant_b=args["variant_b"],
            traffic_split=args.get("traffic_split", 0.1),
        )
        return json.dumps(exp.model_dump(mode="json"))

    if name == "learn.rollback":
        return json.dumps(
            await svc.rollback_resource(
                args["resource_type"], args["resource_id"], args["target_version"]
            )
        )

    if name == "learn.skills":
        skills = await svc.search_skills(args["query"])
        return json.dumps([s.model_dump(mode="json") for s in skills])

    if name == "learn.telemetry":
        return json.dumps(
            await svc.record_lesson_outcome(
                args["lesson_id"],
                telemetry_id=args.get("telemetry_id"),
                run_id=args.get("run_id"),
                used=args.get("used", False),
                accepted=args.get("accepted", False),
                improved=args.get("improved"),
            )
        )

    return json.dumps({"error": f"Unknown tool: {name}"})
