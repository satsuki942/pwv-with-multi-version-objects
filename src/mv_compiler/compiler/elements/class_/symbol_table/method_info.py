import ast
from dataclasses import dataclass, field
from typing import List

from ...signature import ParameterInfo

@dataclass
class MethodInfo:
    """メソッド情報を保持するデータクラス。"""
    name: str
    version: str
    parameters: List[ParameterInfo] = field(default_factory=list)
    ast_node: ast.FunctionDef | None = None
