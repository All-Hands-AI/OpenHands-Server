#!/usr/bin/env python3
"""
build_context.py

- Local (no --artifact-dir): stage repo source (respecting .gitignore) so the executable
  is built inside Docker via the builder stage (build_from_source=True).
- CI (--artifact-dir provided): copy a prebuilt Linux executable into the context
  (build_from_source=False).
- Renders Dockerfile from Dockerfile.j2 (colocated with this script).
- Namespaces build contexts by base image slug: .docker/build_ctx/<base_slug>/
- Writes VERSIONED_TAG as agent_v{sdk_version}_{base_slug}.

Usage:
  # Local (build inside Docker; multi-arch via buildx)
  python build_context.py --base-image nikolaik/python-nodejs:python3.12-nodejs22

  # CI (reuse prebuilt linux binary from dist/)
  python build_context.py --artifact-dir dist --base-image nikolaik/python-nodejs:python3.12-nodejs22
"""  # noqa: E501

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Iterable

import pathspec
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel


# -----------------------------
# Config / Inputs
# -----------------------------
class Inputs(BaseModel):
    # Presence of artifact_dir toggles "CI mode" (prebuilt binary)
    # vs "local" (build from source)
    artifact_dir: str | None = None

    # Hardcoded defaults (keep the script simple)
    template_path: str = str(Path(__file__).parent / "Dockerfile.j2")
    binary_prefix: str = "openhands-agent-server"  # normalized name inside the image
    port: int = 8080

    # Customizable knobs
    base_image: str = "nikolaik/python-nodejs:python3.12-nodejs22"
    sdk_version: str
    repo: str = os.environ.get("GITHUB_REPOSITORY", "all-hands-ai/agent-server")
    revision: str = os.environ.get("GITHUB_SHA", "unknown")


# -----------------------------
# Helpers
# -----------------------------
def slugify_base_for_tag(base_image: str) -> str:
    """
    Transform base image name to a docker tag/path-safe suffix.
    Replace '/' with '_s_' and ':' with '_tag_' (exact mapping requested).
    """
    return base_image.replace("/", "_s_").replace(":", "_tag_")


def find_linux_executable(artifact_dir: Path, binary_prefix: str) -> Path:
    """
    Find a Linux executable that starts with `binary_prefix` under artifact_dir.
    Excludes obvious non-Linux files (.exe, .dll, .dylib).
    Picks the shortest filename (usually the bare binary).
    """
    candidates: list[Path] = []
    for p in artifact_dir.rglob("*"):
        if not p.is_file():
            continue
        name = p.name
        if not name.startswith(binary_prefix):
            continue
        if name.endswith(".exe") or name.endswith(".dll") or name.endswith(".dylib"):
            continue
        candidates.append(p)
    if not candidates:
        raise FileNotFoundError(
            "No Linux executable found under "
            f"'{artifact_dir}' with prefix '{binary_prefix}'."
        )
    candidates.sort(key=lambda x: (len(x.name), x.stat().st_mtime_ns))
    return candidates[0]


def load_gitignore(repo_root: Path) -> pathspec.PathSpec:
    """
    Load .gitignore + a few default exclusions that should *always* be ignored
    when building a Docker context.
    """
    defaults = [
        ".git/",
        ".git/**",
        ".docker/",  # avoid copying other contexts
        ".venv/",
        ".venv/**",
        "node_modules/",
        "node_modules/**",
        "dist/",
        "dist/**",
        "artifacts/",
        "artifacts/**",
        "__pycache__/",
        "**/__pycache__/**",
        ".pytest_cache/",
        ".mypy_cache/",
        ".DS_Store",
    ]

    patterns = []
    gi = repo_root / ".gitignore"
    if gi.exists():
        patterns.extend(gi.read_text(encoding="utf-8").splitlines())
    patterns.extend(defaults)

    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def _iter_repo_entries(
    repo_root: Path, out_dir: Path, spec: pathspec.PathSpec
) -> Iterable[Path]:
    """
    Yield repo entries to include in the staged context, honoring .gitignore
    and preventing recursive copying of the build context itself.
    """
    for src in repo_root.rglob("*"):
        # Skip the build context itself (avoid recursion)
        if _is_within(src, out_dir):
            continue
        # Evaluate .gitignore against path relative to repo root
        rel = src.relative_to(repo_root)
        if spec.match_file(str(rel)):
            continue
        yield src


def stage_source_with_gitignore(project_root: Path, out_dir: Path) -> None:
    """
    Copy repo content into the build context for builder stage (COPY . .),
    respecting .gitignore and skipping the build context directory itself.
    """
    spec = load_gitignore(project_root)
    for src in _iter_repo_entries(project_root, out_dir, spec):
        rel = src.relative_to(project_root)
        dest = out_dir / rel
        if src.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def render_dockerfile(cfg: Inputs, out_dir: Path, build_from_source: bool) -> None:
    template_path = Path(cfg.template_path).resolve()
    if not template_path.exists():
        raise FileNotFoundError(f"Missing Dockerfile template: {template_path}")
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        autoescape=select_autoescape(disabled_extensions=("j2",)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    text = env.get_template(template_path.name).render(
        base_image=cfg.base_image,
        binary_filename=cfg.binary_prefix,
        port=cfg.port,
        repo=cfg.repo,
        revision=cfg.revision,
        build_from_source=build_from_source,
    )
    (out_dir / "Dockerfile").write_text(text, encoding="utf-8")


def write_dockerignore(out_dir: Path, build_from_source: bool) -> None:
    """
    Write a .dockerignore at the context root (out_dir).
    - Local build (build_from_source=True): keep everything we staged.
    - CI (prebuilt binary): keep only Dockerfile and the binary.
    """
    if build_from_source:
        content = """# Keep staged source; .gitignore was applied during staging.
"""
    else:
        content = """# Keep only the Dockerfile and the binary in this context
*
!Dockerfile
!openhands-agent-server
"""
    (out_dir / ".dockerignore").write_text(content, encoding="utf-8")


# -----------------------------
# Main
# -----------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--artifact-dir",
        default=None,
        help="Directory containing the built Linux executable (CI path). "
        "Omit for local build-in-docker.",
    )
    ap.add_argument(
        "--base-image", default="nikolaik/python-nodejs:python3.12-nodejs22"
    )
    ap.add_argument(
        "--sdk-version",
        required=True,
        help="SDK version to bake into the image (e.g. 0.1.0)",
    )
    args = ap.parse_args()

    cfg = Inputs(
        artifact_dir=args.artifact_dir,
        base_image=args.base_image,
        sdk_version=args.sdk_version,
    )

    # Build context directory is namespaced by base image slug
    base_slug = slugify_base_for_tag(cfg.base_image)
    out_dir = Path(".docker") / "build_ctx" / base_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    build_from_source = cfg.artifact_dir is None

    if build_from_source:
        print(f"[dockerize] Local mode: staging source with .gitignore → {out_dir}")
        stage_source_with_gitignore(Path.cwd(), out_dir)
    else:
        print(
            "[dockerize] CI mode: using prebuilt "
            f"executable from: {cfg.artifact_dir}. Context: {out_dir}"
        )
        assert cfg.artifact_dir is not None
        artifact_dir = Path(cfg.artifact_dir).resolve()
        src_binary = find_linux_executable(artifact_dir, cfg.binary_prefix)
        dest_binary = out_dir / cfg.binary_prefix
        shutil.copy2(src_binary, dest_binary)
        dest_binary.chmod(dest_binary.stat().st_mode | 0o111)
        print(f"[dockerize] Copied executable: {src_binary} -> {dest_binary}")

    render_dockerfile(cfg, out_dir, build_from_source=build_from_source)
    write_dockerignore(out_dir, build_from_source=build_from_source)

    # Versioned tag file
    if cfg.sdk_version:
        versioned_tag = f"agent_v{cfg.sdk_version}_{base_slug}"
        (out_dir / "VERSIONED_TAG").write_text(versioned_tag, encoding="utf-8")
        print(f"[dockerize] VERSIONED_TAG = {versioned_tag}")

    print(f"[dockerize] Build context ready at: {out_dir}")
    print(f"[dockerize] Dockerfile: {out_dir / 'Dockerfile'}")


if __name__ == "__main__":
    main()
