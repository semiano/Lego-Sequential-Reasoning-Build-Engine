from __future__ import annotations

from sqlalchemy.orm import Session

from engine.persistence.models import StrategyBucket
from engine.providers.base import LLMProvider
from engine.prompts import load_system_prompt


async def label_and_store_buckets(
    db: Session,
    run_id: str,
    clustered_asset_ids: dict[int, list[str]],
    namer_provider: LLMProvider | None,
) -> list[StrategyBucket]:
    created: list[StrategyBucket] = []

    for cluster_id, exemplar_ids in clustered_asset_ids.items():
        name = f"Cluster {cluster_id + 1}"
        if namer_provider is not None:
            try:
                schema = {
                    "type": "object",
                    "required": ["name"],
                    "properties": {"name": {"type": "string", "minLength": 2}},
                    "additionalProperties": False,
                }
                payload = await namer_provider.generate_json(
                    system_prompt=load_system_prompt(
                        "namer_system.txt",
                        "You create concise names for LEGO inspiration clusters.",
                    ),
                    user_prompt=f"Provide a short cluster label for assets: {exemplar_ids[:5]}",
                    schema=schema,
                )
                name = payload["name"]
            except Exception:
                name = f"Cluster {cluster_id + 1}"

        record = StrategyBucket(run_id=run_id, name=name, exemplar_ids_json=exemplar_ids)
        db.add(record)
        created.append(record)

    db.commit()
    for item in created:
        db.refresh(item)
    return created
