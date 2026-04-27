# modules.json に宣言した import 文だけが version 順に重複排除されて出力されることを検証する。
from pathlib import Path

import sample


if __name__ == "__main__":
    generated = Path(sample.__file__).read_text(encoding="utf-8")
    print(generated.index("import os") < generated.index("from math import sqrt"))
    print(generated.index("from math import sqrt") < generated.index("from decimal import Decimal as D"))
    print(generated.count("import os"))
