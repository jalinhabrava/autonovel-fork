#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REACT_SHELL="${REPO_ROOT}/textifai/web_viewer/react_shell"
NVM_SH="${HOME}/.nvm/nvm.sh"
NVMRC_PATH="${REACT_SHELL}/.nvmrc"
PACKAGE_JSON="${REACT_SHELL}/package.json"
REQUIRED_NODE_RANGE=">=22 <23"

if [[ ! -d "${REACT_SHELL}" ]]; then
  echo "React shell missing: ${REACT_SHELL}" >&2
  exit 1
fi

cd "${REACT_SHELL}"

if [[ -f "${NVM_SH}" ]]; then
  # shellcheck disable=SC1090
  source "${NVM_SH}"
  if [[ -f "${NVMRC_PATH}" ]]; then
    nvm install >/dev/null
    nvm use >/dev/null
  fi
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Node >=22 <23 required. Current: missing. Load nvm or install Node 22." >&2
  exit 1
fi

if [[ ! -f "${PACKAGE_JSON}" ]]; then
  echo "React package missing: ${PACKAGE_JSON}" >&2
  exit 1
fi

CURRENT_NODE="$(node -v 2>/dev/null || true)"
CURRENT_MAJOR="$(printf '%s' "${CURRENT_NODE#v}" | cut -d. -f1)"

if [[ -z "${CURRENT_NODE}" || -z "${CURRENT_MAJOR}" || ! "${CURRENT_MAJOR}" =~ ^[0-9]+$ || "${CURRENT_MAJOR}" -lt 22 || "${CURRENT_MAJOR}" -ge 23 ]]; then
  echo "Node ${REQUIRED_NODE_RANGE} required. Current: ${CURRENT_NODE:-missing}. Load nvm or install Node 22." >&2
  exit 1
fi

npm run build
