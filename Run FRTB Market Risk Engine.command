#!/bin/zsh
set -e
PROJECT_DIR="${0:A:h}"
cd "$PROJECT_DIR"
if [[ -x "$PROJECT_DIR/.frtb_sa_env/bin/python" ]]; then
  BOOTSTRAP_PYTHON="$PROJECT_DIR/.frtb_sa_env/bin/python"
else
  BOOTSTRAP_PYTHON="python3"
fi
"$BOOTSTRAP_PYTHON" "$PROJECT_DIR/scripts/bootstrap_environment.py"
"$PROJECT_DIR/.frtb_sa_env/bin/python" -m frtb_engine run-ima
"$PROJECT_DIR/.frtb_sa_env/bin/python" "$PROJECT_DIR/scripts/build_notebooks.py"
"$PROJECT_DIR/.frtb_sa_env/bin/python" "$PROJECT_DIR/scripts/build_ima_notebooks.py"
"$PROJECT_DIR/.frtb_sa_env/bin/python" "$PROJECT_DIR/scripts/validate_notebooks.py"
"$PROJECT_DIR/.frtb_sa_env/bin/python" "$PROJECT_DIR/scripts/build_report.py"
open "$PROJECT_DIR/outputs"
