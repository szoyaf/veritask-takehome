"""One command to rebuild everything:  python run.py [--all-methods] [--as-of YYYY-MM-DD]

PDF -> structured text -> relations/versions/graph -> metadata -> RAG chunks.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from veritask.pipeline import main  # noqa: E402

if __name__ == "__main__":
    main()
