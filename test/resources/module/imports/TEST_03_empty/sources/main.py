# modules.json に imports がない場合は import なしとして扱われることを検証する。
from pathlib import Path

import sample


if __name__ == "__main__":
    generated = Path(sample.__file__).read_text(encoding="utf-8")
    print("import os" in generated)
    print("import sys" in generated)
