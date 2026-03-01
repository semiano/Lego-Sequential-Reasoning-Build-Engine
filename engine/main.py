from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from sqlalchemy import select

from engine.builder.generator import MicroAssemblyGenerator
from engine.config import EnginePreset, get_settings, load_preset
from engine.control_plane.client import ControlPlaneClient
from engine.evaluator.clip_embedder import ClipEmbedder
from engine.evaluator.scorer import LocalScorer
from engine.orchestration.build_loop import run_build_loop
from engine.orchestration.run_manager import RunManager
from engine.persistence.db import create_session_factory
from engine.persistence.models import InspirationAsset, Step, StrategyBucket
from engine.planner.planner import Planner
from engine.providers.openai_provider import OpenAIProvider
from engine.retrieval.collector import InspirationCollector
from engine.retrieval.serpapi_provider import SerpApiProvider
from engine.strategy.buckets import label_and_store_buckets
from engine.strategy.clustering import kmeans_cluster_assets

app = typer.Typer(help="AI sequential LEGO build engine")


def _load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_db_session():
    settings = get_settings()
    session_factory = create_session_factory(settings.resolved_engine_data_dir / "engine.db")
    return session_factory(), settings


def _build_provider(model: str, trace_dir: Path) -> OpenAIProvider:
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required")
    return OpenAIProvider(
        api_key=settings.openai_api_key,
        model=model,
        base_url=settings.openai_base_url,
        trace_dir=trace_dir,
    )


async def _collect_and_cluster(
    db,
    run_id: str,
    concept_image: Path,
    preset: EnginePreset,
    run_dir: Path,
):
    embedder = ClipEmbedder()
    collector = InspirationCollector(
        search_provider=SerpApiProvider(),
        embedder=embedder,
        cache_dir=run_dir / "inspiration_cache",
    )
    assets = await collector.collect(db=db, run_id=run_id, subject=preset.subject)

    if not assets:
        embedding = embedder.embed_image(concept_image)
        seed = InspirationAsset(
            run_id=run_id,
            image_url=str(concept_image),
            embedding=json.dumps(embedding.tolist()),
            metadata_json={"seed": True, "local_path": str(concept_image)},
        )
        db.add(seed)
        db.commit()
        db.refresh(seed)
        assets = [seed]

    cluster_count = max(5, min(12, len(assets)))
    clustered = kmeans_cluster_assets(assets, k=cluster_count)
    cluster_id_map = {idx: [asset.id for asset in group] for idx, group in clustered.items()}

    namer = None
    try:
        settings = get_settings()
        namer = _build_provider(settings.model_namer, run_dir / "llm_traces")
    except Exception:
        namer = None

    buckets = await label_and_store_buckets(db=db, run_id=run_id, clustered_asset_ids=cluster_id_map, namer_provider=namer)
    return buckets


@app.command("run")
def run_command(
    concept: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False),
    name: str = typer.Option(...),
    workspace_id: str = typer.Option(None),
    control_plane: str = typer.Option("http://localhost:8000"),
    preset: Path = typer.Option(Path("presets/bird_sculpt.json"), exists=True),
):
    async def _run():
        db, settings = _ensure_db_session()
        preset_model = load_preset(str(preset))

        run_root = settings.resolved_engine_data_dir / "runs"
        run_root.mkdir(parents=True, exist_ok=True)

        planner_schema = _load_schema(Path(__file__).parent / "schemas" / "plan.schema.json")
        assembly_schema = _load_schema(Path(__file__).parent / "schemas" / "micro_assembly.schema.json")

        cp = ControlPlaneClient(control_plane)
        if workspace_id:
            await cp.get_timeline(workspace_id)
            workspace = {"id": workspace_id, "name": name}
        else:
            workspace = await cp.create_workspace(name=name)

        manager = RunManager(db=db, run_dir=run_root)
        run = manager.create_run(
            name=name,
            workspace_id=workspace["id"],
            concept_image=str(concept),
            knobs_json=preset_model.model_dump(),
        )
        run_dir = run_root / run.id
        run_dir.mkdir(parents=True, exist_ok=True)

        buckets = await _collect_and_cluster(db=db, run_id=run.id, concept_image=concept, preset=preset_model, run_dir=run_dir)

        planner_provider = _build_provider(settings.model_planner, run_dir / "llm_traces")
        builder_provider = _build_provider(settings.model_builder, run_dir / "llm_traces")
        planner = Planner(provider=planner_provider, plan_schema=planner_schema)
        builder = MicroAssemblyGenerator(provider=builder_provider, schema=assembly_schema)
        scorer = LocalScorer(embedder=ClipEmbedder(), weights=preset_model.weights.model_dump())

        try:
            await run_build_loop(
                db=db,
                run_manager=manager,
                run_id=run.id,
                concept_image=concept,
                preset=preset_model,
                planner=planner,
                builder=builder,
                scorer=scorer,
                control_plane=cp,
                control_plane_base=control_plane,
                strategy_buckets=buckets,
                trace_dir=run_dir,
            )
        except Exception:
            manager.fail_run(run.id)
            raise

        report_path = manager.write_report(run.id, control_plane_base=control_plane)
        typer.echo(f"Run complete: {run.id}")
        typer.echo(f"Workspace: {workspace['id']}")
        typer.echo(f"Report: {report_path}")

    asyncio.run(_run())


@app.command("resume")
def resume_command(run_id: str = typer.Option(None), name: str = typer.Option(None), control_plane: str = typer.Option("http://localhost:8000")):
    async def _resume():
        db, settings = _ensure_db_session()
        run_root = settings.resolved_engine_data_dir / "runs"
        manager = RunManager(db=db, run_dir=run_root)

        run_obj = manager.get_run(run_id) if run_id else manager.latest_run_by_name(name or "")
        if run_obj is None:
            raise ValueError("No matching run found")

        run_obj.status = "running"
        db.commit()

        preset_model = EnginePreset.model_validate(run_obj.knobs_json)
        concept = Path(run_obj.concept_image)
        run_dir = run_root / run_obj.id
        run_dir.mkdir(parents=True, exist_ok=True)

        planner_schema = _load_schema(Path(__file__).parent / "schemas" / "plan.schema.json")
        assembly_schema = _load_schema(Path(__file__).parent / "schemas" / "micro_assembly.schema.json")

        cp = ControlPlaneClient(control_plane)

        planner_provider = _build_provider(settings.model_planner, run_dir / "llm_traces")
        builder_provider = _build_provider(settings.model_builder, run_dir / "llm_traces")
        planner = Planner(provider=planner_provider, plan_schema=planner_schema)
        builder = MicroAssemblyGenerator(provider=builder_provider, schema=assembly_schema)
        scorer = LocalScorer(embedder=ClipEmbedder(), weights=preset_model.weights.model_dump())

        step_stmt = select(Step).where(Step.run_id == run_obj.id).order_by(Step.step_index.asc())
        existing_steps = list(db.scalars(step_stmt).all())

        bucket_stmt = select(StrategyBucket).where(StrategyBucket.run_id == run_obj.id)
        buckets = list(db.scalars(bucket_stmt).all())

        await run_build_loop(
            db=db,
            run_manager=manager,
            run_id=run_obj.id,
            concept_image=concept,
            preset=preset_model,
            planner=planner,
            builder=builder,
            scorer=scorer,
            control_plane=cp,
            control_plane_base=control_plane,
            strategy_buckets=buckets,
            trace_dir=run_dir,
            start_step=len(existing_steps) + 1,
        )

        report_path = manager.write_report(run_obj.id, control_plane_base=control_plane)
        typer.echo(f"Resumed run complete: {run_obj.id}")
        typer.echo(f"Report: {report_path}")

    asyncio.run(_resume())


@app.command("stop")
def stop_command(run_id: str = typer.Option(...)):
    db, settings = _ensure_db_session()
    manager = RunManager(db=db, run_dir=settings.resolved_engine_data_dir / "runs")
    run = manager.stop_run(run_id)
    typer.echo(f"Run stopped: {run.id}")


@app.command("report")
def report_command(run_id: str = typer.Option(...), control_plane: str = typer.Option("http://localhost:8000")):
    db, settings = _ensure_db_session()
    manager = RunManager(db=db, run_dir=settings.resolved_engine_data_dir / "runs")
    path = manager.write_report(run_id, control_plane)
    typer.echo(f"Report generated: {path}")


@app.command("export")
def export_command(run_id: str = typer.Option(...), output: Path = typer.Option(...)):
    db, settings = _ensure_db_session()
    manager = RunManager(db=db, run_dir=settings.resolved_engine_data_dir / "runs")
    out = manager.export_run(run_id, output)
    typer.echo(f"Report exported: {out}")


if __name__ == "__main__":
    app()
