#!/usr/bin/env bash
# Lance la suite de tests (Linux / macOS). Usage : tests/run-tests.sh [options pytest]
#   tests/run-tests.sh                 -> tout
#   tests/run-tests.sh -m static       -> contrôles rapides sans navigateur
#   tests/run-tests.sh --full          -> 17 tailles d'écran au lieu de 7
#   tests/run-tests.sh --launch        -> ajoute les contrôles d'avant mise en ligne
#   tests/run-tests.sh -k formulaire   -> seulement les tests dont le nom contient « formulaire »
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -d .venv-tests ]; then
  python3 -m venv .venv-tests
  .venv-tests/bin/pip install -q -r tests/requirements.txt
  .venv-tests/bin/python -m playwright install chromium
fi
mkdir -p tests/artifacts
.venv-tests/bin/python -m pytest --html=tests/artifacts/rapport.html --self-contained-html "$@"
echo
echo "Rapport : tests/artifacts/rapport.html"
