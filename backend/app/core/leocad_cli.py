from pathlib import Path
import os
import subprocess

from app.core.config import get_settings


class LeoCADError(RuntimeError):
    pass


class LeoCADCLI:
    def __init__(self) -> None:
        settings = get_settings()
        self.executable = settings.leocad_exe
        self.ldraw_parts_dir = settings.ldraw_parts_dir

    def _run_candidates(self, candidates: list[list[str]]) -> None:
        errors: list[str] = []
        for cmd in candidates:
            env = os.environ.copy()
            if self.ldraw_parts_dir:
                env["LDRAWDIR"] = self.ldraw_parts_dir
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
                return
            except FileNotFoundError as exc:
                raise LeoCADError(f"LeoCAD executable not found: {self.executable}") from exc
            except subprocess.CalledProcessError as exc:
                stderr = (exc.stderr or "").strip()
                stdout = (exc.stdout or "").strip()
                errors.append(f"cmd={' '.join(cmd)} stderr={stderr} stdout={stdout}")
        raise LeoCADError("; ".join(errors) or "LeoCAD command failed")

    def render_single(self, ldraw_path: Path, out_path: Path, camera_preset: str, w: int, h: int) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        viewpoint_map = {
            "iso": "home",
            "front": "front",
            "side": "right",
            "top": "top",
        }
        viewpoint = viewpoint_map.get(camera_preset, "home")
        libpath_args = ["--libpath", self.ldraw_parts_dir] if self.ldraw_parts_dir else []
        candidates = [
            [self.executable, *libpath_args, str(ldraw_path), "--image", str(out_path), "--width", str(w), "--height", str(h), "--viewpoint", viewpoint],
            [self.executable, *libpath_args, str(ldraw_path), "-i", str(out_path), "-w", str(w), "-h", str(h), "--viewpoint", viewpoint],
            [self.executable, *libpath_args, str(ldraw_path), "-i", str(out_path), "-w", str(w), "-h", str(h)],
        ]
        self._run_candidates(candidates)
        return out_path

    def render_views(self, ldraw_path: Path, out_dir: Path, views: list[str], w: int, h: int) -> list[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        artifacts: list[Path] = []
        for view in views:
            output = out_dir / f"{view}.png"
            try:
                self.render_single(ldraw_path, output, view, w, h)
            except LeoCADError:
                if view != "iso":
                    self.render_single(ldraw_path, output, "iso", w, h)
                else:
                    raise
            artifacts.append(output)
        return artifacts

    def render_turntable(self, ldraw_path: Path, out_dir: Path, frames: int, w: int, h: int) -> list[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        artifacts: list[Path] = []
        if frames <= 0:
            return artifacts
        for idx in range(frames):
            frame_path = out_dir / f"frame_{idx + 1:04d}.png"
            self.render_single(ldraw_path, frame_path, "iso", w, h)
            artifacts.append(frame_path)
        return artifacts
