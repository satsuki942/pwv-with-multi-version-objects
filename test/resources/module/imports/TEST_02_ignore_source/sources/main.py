# 元ソース内の import 文は modules.json に宣言されていなければ出力されないことを検証する。
from pathlib import Path

import sample


if __name__ == "__main__":
    generated = Path(sample.__file__).read_text(encoding="utf-8")
    print("from math import sqrt" in generated)
    print("import os" in generated)
    print("import sys" in generated)
