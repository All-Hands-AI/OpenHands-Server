#!/usr/bin/env bash
set -euo pipefail

#------------------------------------------------------------------------------
# Config: only BASE_IMAGE is required. Everything else is auto.
#------------------------------------------------------------------------------
: "${BASE_IMAGE:?Set BASE_IMAGE, e.g. nikolaik/python-nodejs:python3.12-nodejs22}"

IMAGE="ghcr.io/all-hands-ai/agent-server"
PLATFORMS_CI="linux/amd64,linux/arm64"

# Resolve script dir so we can call sibling files no matter the CWD
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
BUILD_CTX_PY="${SCRIPT_DIR}/build_context.py"

if [[ ! -f "${BUILD_CTX_PY}" ]]; then
  echo "[build] ERROR: build_context.py not found at ${BUILD_CTX_PY}"
  exit 1
fi

#------------------------------------------------------------------------------
# Git info
#------------------------------------------------------------------------------
GIT_SHA="${GITHUB_SHA:-$(git rev-parse --verify HEAD 2>/dev/null || echo unknown)}"
SHORT_SHA="${GIT_SHA:0:7}"
GIT_REF="${GITHUB_REF:-$(git symbolic-ref -q --short HEAD 2>/dev/null || echo unknown)}"

#------------------------------------------------------------------------------
# Determine version from openhands.sdk and append short sha
# (make module importable by adding SCRIPT_DIR to PYTHONPATH)
#------------------------------------------------------------------------------
SDK_VERSION="$(
  uv run python - <<'PY'
import os, sys
# allow imports from script dir AND repo root
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.dirname(__file__))
import openhands.sdk as sdk
print(getattr(sdk, "__version__", "0.0.0"))
PY
)"
VERSION_WITH_SHA="${SDK_VERSION}-${SHORT_SHA}"
echo "[build] Detected sdk version: ${SDK_VERSION}  (tag will use ${VERSION_WITH_SHA})"

#------------------------------------------------------------------------------
# Render build context (local: build-from-source; CI: use artifact)
#------------------------------------------------------------------------------
ARGS=( 
    --base-image "${BASE_IMAGE}"
    --sdk-version "${VERSION_WITH_SHA}"
)
if [[ -n "${ARTIFACT_DIR:-}" ]]; then
  echo "[build] CI mode: using artifact at '${ARTIFACT_DIR}'"
  ARGS+=( --artifact-dir "${ARTIFACT_DIR}" )
else
  echo "[build] Local mode: building from source in Docker"
fi

python3 "${BUILD_CTX_PY}" "${ARGS[@]}"

#------------------------------------------------------------------------------
# Locate context & tags (use slug from the same build_context module)
#------------------------------------------------------------------------------
BASE_SLUG="$(
  PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH:-}" python3 - <<'PY'
import os
from build_context import slugify_base_for_tag
print(slugify_base_for_tag(os.environ["BASE_IMAGE"]))
PY
)"
CTX_DIR="${SCRIPT_DIR}/.docker/build_ctx/${BASE_SLUG}"
DOCKERFILE="${CTX_DIR}/Dockerfile"

# Fallback if build_context writes under repo-root/.docker (older layout)
if [[ ! -f "${DOCKERFILE}" ]]; then
  CTX_DIR=".docker/build_ctx/${BASE_SLUG}"
  DOCKERFILE="${CTX_DIR}/Dockerfile"
fi

[[ -f "${DOCKERFILE}" ]] || { echo "[build] Dockerfile missing at ${DOCKERFILE}"; exit 1; }

# Tags: short sha, latest (on main), and canonical VERSIONED_TAG
TAGS=( "${IMAGE}:${SHORT_SHA}" )
if [[ "${GIT_REF}" == "refs/heads/main" || "${GIT_REF}" == "main" ]]; then
  TAGS+=( "${IMAGE}:latest" )
fi
if [[ -f "${CTX_DIR}/VERSIONED_TAG" ]]; then
  VTAG="$(cat "${CTX_DIR}/VERSIONED_TAG")"
  TAGS+=( "${IMAGE}:${VTAG}" )
fi

#------------------------------------------------------------------------------
# Build: CI → multi-arch + push; Local → single-arch + load
#------------------------------------------------------------------------------
if [[ -n "${GITHUB_ACTIONS:-}" || -n "${CI:-}" || -n "${ARTIFACT_DIR:-}" ]]; then
  echo "[build] CI: buildx multi-arch → push"
  docker buildx create --use --name agentserver-builder >/dev/null 2>&1 || docker buildx use agentserver-builder
  docker buildx build \
    --platform "${PLATFORMS_CI}" \
    $(printf -- ' --tag %q' "${TAGS[@]}") \
    --push \
    --file "${DOCKERFILE}" \
    "${CTX_DIR}"
else
  echo "[build] Local: buildx single-arch → load"
  docker buildx build \
    $(printf -- ' --tag %q' "${TAGS[@]}") \
    --load \
    --file "${DOCKERFILE}" \
    "${CTX_DIR}"
fi

echo "[build] Done. Tags:"
printf ' - %s\n' "${TAGS[@]}"
