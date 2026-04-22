import ast
import copy

from .builder.unified_class_builder import build_unified_class
from .symbol_table.symbol_table import SymbolTable
from .symbol_table.symbol_table_builder import SymbolTableBuilder
from ...common.util import logger
from ..variable.reference_rewriter import VersionedValueNameRewriter


def build_unified_classes_for_module(
    class_exports: dict,
    top_level_by_version: dict[int, dict[str, ast.AST]],
    versions: list[int],
    versioned_value_names: set[str],
    sync_functions_dict: dict,
    incompatibilities: dict | None,
    version_selection_strategy: str,
) -> list[ast.ClassDef]:
    synthetic_body: list[ast.AST] = []
    for export_name, spec in class_exports.items():
        for version in versions:
            source_name = spec.get("versions", {}).get(str(version), export_name)
            class_node = top_level_by_version[version].get(source_name)
            if not isinstance(class_node, ast.ClassDef):
                logger.error_log(f"Class export not found: {export_name} v{version}")
                continue
            class_copy = copy.deepcopy(class_node)
            class_copy.name = f"{export_name}__{version}__"
            class_copy = VersionedValueNameRewriter(versioned_value_names, version).visit(class_copy)
            synthetic_body.append(class_copy)

    synthetic_module = ast.Module(body=synthetic_body, type_ignores=[])
    symbol_table = SymbolTable()
    SymbolTableBuilder(symbol_table).visit(synthetic_module)

    out: list[ast.ClassDef] = []
    for export_name in class_exports:
        state_sync_components = sync_functions_dict.get(export_name, ([], []))
        incompatibility = incompatibilities.get(export_name) if incompatibilities else None
        out.append(build_unified_class(
            export_name,
            state_sync_components,
            symbol_table,
            incompatibility,
            version_selection_strategy,
        ))
    return out
