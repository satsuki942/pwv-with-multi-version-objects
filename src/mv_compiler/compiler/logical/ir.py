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
class FunctionSourceIR:
    """論理関数entityを構成する、各版の元関数定義。"""

    version: int
    name: str
    node: ast.FunctionDef


@dataclass(frozen=True)
class FunctionMeaningIR:
    """論理関数の版固有の意味を表すIR。"""

    id: str


@dataclass(frozen=True)
class FunctionMeaningResolutionIR:
    """呼び出しが期待する関数meaningを決定する仕様。"""

    mode: str
    meaning: str


@dataclass(frozen=True)
class FunctionImplementationIR:
    """realizationが最終的に呼ぶ実装を表すIR。"""

    kind: str
    version: int
    name: str


@dataclass(frozen=True)
class FunctionRealizationIR:
    """あるmeaningを実現するための候補実行方法。"""

    meaning: str
    implementation: FunctionImplementationIR
    preconditions: list[Any] = field(default_factory=list)
    pre_adjustments: list[Any] = field(default_factory=list)


@dataclass(frozen=True)
class LogicalFunctionIR:
    """論理関数entityに必要な仕様と版別実体を束ねたIR。"""

    entity: str
    public_name: str
    sources: dict[int, FunctionSourceIR]
    meanings: dict[str, FunctionMeaningIR]
    meaning_resolution: FunctionMeaningResolutionIR
    realizations: list[FunctionRealizationIR]


@dataclass(frozen=True)
class LogicalObjectIR:
    """各版のトップレベル要素を、単一の論理要素として束ねたIR。"""

    kind: LogicalObjectKind
    order_index: int
    public_name: str | None
    base_version_node: ast.AST
    version_nodes: dict[int, ast.AST | None] = field(default_factory=dict)
    compatibility_spec: dict[str, Any] | None = None
    function_ir: LogicalFunctionIR | None = None


@dataclass(frozen=True)
class LogicalModuleIR:
    """コンパイラ入力から得られる論理モジュール単位のIR。"""

    module_key: str
    module_path: str
    logical_rel_path: Path
    versions: list[int]
    base_version: int
    import_nodes: list[ast.Import | ast.ImportFrom]
    objects: list[LogicalObjectIR]
