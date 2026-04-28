from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


EntityKind = Literal["class", "function", "variable"]
DiffOp = Literal["change", "rename", "add", "delete", "revive"]


@dataclass
class EntityVersion:
    """ある semantic entity が特定 version で持つ具体定義を表す。"""

    version: int
    name: str
    node: ast.AST
    sync_functions: list[ast.FunctionDef] = field(default_factory=list)


@dataclass
class EntityHistory:
    """1つの semantic entity の版履歴と出力位置を保持する。"""

    entity_key: str
    kind: EntityKind
    order: int
    variable_versioning: str | None = None
    versions: list[EntityVersion] = field(default_factory=list)
    deleted_at: list[int] = field(default_factory=list)

    def concrete_versions(self) -> list[int]:
        return sorted(version.version for version in self.versions)

    def public_names(self) -> list[str]:
        names: list[str] = []
        for version in self.versions:
            if version.name not in names:
                names.append(version.name)
        return names

    def latest_version(self) -> EntityVersion:
        return sorted(self.versions, key=lambda item: item.version)[-1]


@dataclass
class NormalStatement:
    """entity ではない top-level 文を、元の位置に戻すための記録。"""

    order: int
    node: ast.AST


@dataclass
class ParsedModule:
    """DSL parsing 後の中間表現。"""

    rel_path: Path
    imports: list[ast.AST]
    entities: list[EntityHistory]
    normal_statements: list[NormalStatement]
    max_version: int

