"""Execute every notebook in chronological order and retain visible outputs."""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbclient import NotebookClient


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    notebooks = sorted((ROOT / "notebooks").glob("*.ipynb"))
    failures = []
    for path in notebooks:
        try:
            notebook = nbformat.read(path, as_version=4)
            client = NotebookClient(
                notebook,
                timeout=120,
                kernel_name="frtb-sa-local",
                resources={"metadata": {"path": str(ROOT)}},
            )
            client.execute(cwd=str(ROOT))
            nbformat.write(notebook, path)
            print(f"PASS {path.name}")
        except Exception as error:  # the complete filename and exception are needed for QA
            failures.append((path.name, str(error)))
            print(f"FAIL {path.name}: {error}")
    if failures:
        details = "\n".join(f"{name}: {error}" for name, error in failures)
        raise RuntimeError(f"Notebook validation failed:\n{details}")
    print(f"Executed {len(notebooks)} notebooks successfully.")


if __name__ == "__main__":
    main()
