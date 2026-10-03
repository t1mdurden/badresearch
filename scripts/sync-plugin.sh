#!/usr/bin/env bash
# Rebuild plugins/bad-research from this repo's sources, so an upstream sync is:
#   git merge upstream/main && scripts/sync-plugin.sh && git add -A plugins && git commit
#
# Layout it writes (everything else under plugins/bad-research is hand-kept: bin/, .claude-plugin/):
#   skills/bad-research/   <- skills/bad-research   (SKILL.md, references/, scripts/)
#   agents/                <- agents/               (the three research-* agents)
#   engine/                <- pyproject.toml README.md LICENSE uv.lock src/  -- what bin/bad pip-installs
#   engine/skills/bad-research, engine/agents      -- pyproject force-includes both into the wheel,
#                                                     so the engine build fails without them
# The plugin's version is set from pyproject.toml: bin/bad rebuilds its venv only when
# engine/pyproject.toml's version moves, and `claude plugin update` only when plugin.json's does.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
P="${ROOT}/plugins/bad-research"
SYNC=(rsync -a --delete --exclude __pycache__ --exclude .DS_Store --exclude '*.pyc')

[ -f "${P}/.claude-plugin/plugin.json" ] || { echo "sync-plugin: ${P} is not the plugin dir" >&2; exit 1; }

mkdir -p "${P}/skills" "${P}/engine/skills"
# Drop any skill or engine piece the sources no longer have (the retired step skills).
find "${P}/skills" -mindepth 1 -maxdepth 1 ! -name bad-research -exec rm -rf {} +
"${SYNC[@]}" "${ROOT}/skills/bad-research/" "${P}/skills/bad-research/"
"${SYNC[@]}" "${ROOT}/agents/" "${P}/agents/"
"${SYNC[@]}" "${ROOT}/src/" "${P}/engine/src/"
"${SYNC[@]}" "${ROOT}/skills/bad-research/" "${P}/engine/skills/bad-research/"
"${SYNC[@]}" "${ROOT}/agents/" "${P}/engine/agents/"
for f in pyproject.toml README.md LICENSE uv.lock; do
  [ -f "${ROOT}/${f}" ] && cp "${ROOT}/${f}" "${P}/engine/${f}"
done

VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "${ROOT}/pyproject.toml" | head -1)"
python3 - "${P}/.claude-plugin/plugin.json" "${VERSION}" <<'PY'
import json, sys
path, version = sys.argv[1], sys.argv[2]
data = json.load(open(path))
data["version"] = version
open(path, "w").write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
PY

echo "sync-plugin: plugins/bad-research <- sources, version ${VERSION}"
echo "  skills: $(ls "${P}/skills" | tr '\n' ' ')"
echo "  agents: $(ls "${P}/agents" | tr '\n' ' ')"
