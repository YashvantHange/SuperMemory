"""
Multi-agent orchestrator demo — proves closed-loop learning.

Run 1: Planner fails (chooses OCR for searchable PDF)
Run 2: Planner retrieves lesson and avoids the mistake
"""

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

from uall_python.client import UALLClient


def simulate_pdf_routing(lessons: list[dict], is_searchable: bool) -> str:
    """Simulate planner routing decision."""
    lesson_text = " ".join(
        r.get("lesson", {}).get("fix", "") for r in lessons
    ).lower()
    if "text layer" in lesson_text or "inspect" in lesson_text:
        return "text_layer" if is_searchable else "ocr"
    return "ocr"


def main():
    tmp = tempfile.mkdtemp(prefix="uall_demo_")
    data_dir = Path(tmp) / ".uall"
    client = UALLClient(storage="file", data_dir=str(data_dir))

    print("=== UALL Multi-Agent Demo ===\n")

    # Run 1: failure
    print("Run 1: Planner routes searchable PDF to OCR (failure)")
    with client.run(
        workflow_id="pdf-pipeline", step="planner", namespace="team:eng"
    ) as run:
        lessons = run.retrieve(step="planner", query="PDF routing")
        decision = simulate_pdf_routing(lessons, is_searchable=True)
        print(f"  Decision: {decision}")
        if decision == "ocr":
            run.record_failure(
                snippet="chose OCR for searchable PDF",
                tags=["routing"],
                agent="planner-agent-1",
            )
            run.record_correction(
                before="route to OCR",
                after="inspect text layer first",
                intent="use text layer for searchable PDFs",
            )
        run.end(success=False)

    recs = client.get_recommendations(workflow_id="pdf-pipeline")
    print(f"  Lessons learned: {len(recs)} recommendation(s)")
    if recs:
        print(f"  Top lesson: {recs[0]['text'][:80]}")

    # Run 2: success with retrieved lesson
    print("\nRun 2: Planner retrieves lesson and routes correctly")
    with client.run(
        workflow_id="pdf-pipeline", step="planner", namespace="team:eng"
    ) as run:
        lessons = run.retrieve(step="planner", query="PDF routing")
        decision = simulate_pdf_routing(lessons, is_searchable=True)
        print(f"  Decision: {decision}")
        success = decision == "text_layer"
        if lessons:
            lid = lessons[0].get("lesson", {}).get("lesson_id", "")
            if lid:
                run.report_lesson_outcome(
                    lesson_id=lid, used=True, accepted=True, improved=success
                )
        run.end(success=success)

    policies = client.get_policies()
    print(f"\nPolicies loaded: {len(policies)}")
    print(f"Data stored in: {data_dir}")

    # A/B experiment demo
    exp = client.experiment(
        prompt_id="planner",
        variant_b="Always inspect PDF text layer before choosing OCR",
        split=0.1,
    )
    print(f"\nExperiment started: {exp.get('experiment_id', 'n/a')}")

    print("\n=== Demo complete ===")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
