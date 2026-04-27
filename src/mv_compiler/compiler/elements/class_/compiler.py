import ast
import copy

from .builder.unified_class_builder import build_unified_class
from .symbol_table.symbol_table import SymbolTable
from .symbol_table.symbol_table_builder import SymbolTableBuilder
from ...common.util import logger
from ..entity import entity_source_node


def build_unified_classes_for_module(
    class_entities: dict,
    top_level_by_version: dict[int, dict[str, ast.AST]],
    versions: list[int],
    sync_functions_dict: dict,
    incompatibilities: dict | None,
    version_selection_strategy: str,
) -> list[ast.ClassDef]:
    """class entityを、version切替可能な統合クラスASTへ変換する。

    Args:
        class_entities: class kindに絞り込まれた正規化済みentity spec。
        top_level_by_version: versionごとのトップレベル定義索引。
        versions: 当該モジュールで宣言されているversion一覧。
        sync_functions_dict: entity_keyごとの状態同期関数定義。
        incompatibilities: entity_keyごとの非互換メソッド設定。
        version_selection_strategy: 実行時にversionを選ぶ戦略名。

    Returns:
        生成モジュールへ追加する統合クラス定義ASTのリスト。
    """
    synthetic_body: list[ast.AST] = []
    for entity_name, spec in class_entities.items():
        for version in versions:
            class_node = entity_source_node(top_level_by_version, entity_name, spec, version)
            if not isinstance(class_node, ast.ClassDef):
                logger.error_log(f"Class entity not found: {entity_name} v{version}")
                continue
            class_copy = copy.deepcopy(class_node)
            class_copy.name = f"{entity_name}__{version}__"
            synthetic_body.append(class_copy)

    # 既存のSymbolTableBuilderはモジュール単位で走るため、版別クラスだけの一時モジュールを作る。
    synthetic_module = ast.Module(body=synthetic_body, type_ignores=[])
    symbol_table = SymbolTable()
    SymbolTableBuilder(symbol_table).visit(synthetic_module)

    out: list[ast.ClassDef] = []
    for entity_name, spec in class_entities.items():
        mapping_key = spec.get("sync_key", entity_name)
        state_sync_components = sync_functions_dict.get(mapping_key, ([], []))
        incompatibility = incompatibilities.get(mapping_key) if incompatibilities else None
        out.append(build_unified_class(
            entity_name,
            state_sync_components,
            symbol_table,
            incompatibility,
            version_selection_strategy,
        ))
    return out
