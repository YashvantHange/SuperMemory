import uuid
from datetime import datetime

from uall_core.ports.storage import StoragePort
from uall_core.schemas.common import Experiment, ExperimentMetrics


class ExperimentManager:
    def __init__(self, storage: StoragePort):
        self.storage = storage
        self.min_sample_size = 30

    async def start(
        self,
        resource_type: str,
        resource_id: str,
        variant_a: str,
        variant_b: str,
        traffic_split: float = 0.1,
    ) -> Experiment:
        exp = Experiment(
            experiment_id=f"exp_{uuid.uuid4().hex[:8]}",
            resource_type=resource_type,
            resource_id=resource_id,
            variant_a=variant_a,
            variant_b=variant_b,
            traffic_split=traffic_split,
        )
        await self.storage.save_experiment(exp)
        return exp

    async def record_run_metrics(
        self, experiment_id: str, variant: str, metrics: dict
    ) -> Experiment:
        exp = await self.storage.get_experiment(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")
        target = exp.metrics_b if variant == "b" else exp.metrics_a
        target.sample_size += 1
        if metrics.get("success"):
            target.success_rate = (
                target.success_rate * (target.sample_size - 1) + 1
            ) / target.sample_size
        else:
            target.success_rate = (
                target.success_rate * (target.sample_size - 1)
            ) / target.sample_size
        target.retry_count = metrics.get("retry_count", target.retry_count)
        target.cost = metrics.get("cost", target.cost)
        target.latency_p50 = metrics.get("latency_p50", target.latency_p50)
        target.latency_p95 = metrics.get("latency_p95", target.latency_p95)
        target.token_usage = metrics.get("token_usage", target.token_usage)
        target.human_approval_rate = metrics.get("human_approval_rate", target.human_approval_rate)
        target.downstream_failure_rate = metrics.get(
            "downstream_failure_rate", target.downstream_failure_rate
        )
        await self.storage.update_experiment(exp)
        return exp

    async def conclude(self, experiment_id: str) -> Experiment:
        exp = await self.storage.get_experiment(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")
        if exp.metrics_b.sample_size < self.min_sample_size:
            exp.status = "running"
            exp.winner = None
        elif exp.metrics_b.success_rate > exp.metrics_a.success_rate:
            guardrail_ok = (
                exp.metrics_b.latency_p95 <= exp.metrics_a.latency_p95 * 1.2
                and exp.metrics_b.downstream_failure_rate
                <= exp.metrics_a.downstream_failure_rate + 0.05
            )
            exp.winner = "b" if guardrail_ok else None
            exp.status = "concluded" if guardrail_ok else "rolled_back"
        else:
            exp.winner = "a"
            exp.status = "concluded"
        exp.concluded_at = datetime.utcnow()
        await self.storage.update_experiment(exp)
        return exp

    async def get_results(self, experiment_id: str) -> Experiment | None:
        return await self.storage.get_experiment(experiment_id)
