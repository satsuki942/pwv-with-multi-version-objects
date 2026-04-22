import ast

from .skeleton_generator import build_skeleton
from .constructor_generator import build_constructor
from .stub_method_generator import build_stub_methods
from .components import build_getattr_setattr_methods, build_sync_components
from ..symbol_table.symbol_table import SymbolTable
from ....common.util import logger
from ....common.util.constants import DEFAULT_VERSION_SELECTION_STRATEGY

def build_unified_class(
    class_name: str,
    state_sync_components: tuple,
    symbol_table: SymbolTable,
    incompatibility: dict | None = None,
    version_selection_strategy: str = DEFAULT_VERSION_SELECTION_STRATEGY,
) -> ast.ClassDef:
    """
    versionedクラス群のASTを単一の統合クラスASTへ組み立てる。
    """
    logger.debug_log(f"Building unified class for: {class_name}")

    # --- 統合クラスの骨格生成 ---
    sync_asts = state_sync_components[1] if state_sync_components else []
    new_class_ast = build_skeleton(class_name, symbol_table, sync_asts)

    # --- コンストラクタ生成 ---
    constructor_ast = build_constructor(symbol_table, class_name)

    # --- スタブメソッド生成 ---
    stub_methods = build_stub_methods(
        symbol_table,
        class_name,
        version_selection_strategy,
    )

    # --- __getattr__/__setattr__ 生成 ---
    getattr_setattr_methods = build_getattr_setattr_methods(class_name, incompatibility)

    # --- 状態同期コンポーネント生成 ---
    sync_methods = build_sync_components(class_name, state_sync_components)

    additions: list[ast.AST] = []
    if constructor_ast:
        additions.append(constructor_ast)
    additions.extend(stub_methods)
    additions.extend(getattr_setattr_methods)
    additions.extend(sync_methods)
    new_class_ast.body.extend(additions)

    # --- 完成したクラスASTを返す ---
    return new_class_ast
