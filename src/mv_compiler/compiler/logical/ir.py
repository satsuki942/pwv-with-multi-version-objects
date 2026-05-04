import ast
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class LogicalObjectKind(str, Enum):
    """論理モジュール内で扱うトップレベル要素の分類。"""

    IMPORT = "import"
    VARIABLE = "variable"
    FUNCTION = "function"
    CLASS = "class"
    OTHER = "other"


@dataclass(frozen=True)
class LogicalObjectIR:
    """各版のトップレベル要素を、単一の論理要素として束ねたIR。"""

    kind: LogicalObjectKind
    order_index: int
    public_name: str | None
    base_version_node: ast.AST
    version_nodes: dict[int, ast.AST | None] = field(default_factory=dict)
    compatibility_spec: dict[str, Any] | None = None


@dataclass(frozen=True)
class LogicalModuleIR:
    """コンパイラ入力から得られる論理モジュール単位のIR。"""

    module_key: str
    module_path: str
    logical_rel_path: Path
    versions: list[int]
    base_version: int
    objects: list[LogicalObjectIR]
