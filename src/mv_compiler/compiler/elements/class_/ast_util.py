import ast
from typing import Optional, Tuple

from ...versioning import parse_sync_function_name, parse_versioned_name

UNVERSIONED_CLASS_TAG = "normal"

SWITCH_TO_VERSION_METHOD_NAME = "_switch_to_version"

def get_version_instances_singleton_name(class_name: str) -> str:
    """
    versionインスタンスのシングルトン名を生成する。
    """
    return f"_{class_name.upper()}_VERSION_INSTANCES_SINGLETON"

def get_current_state_field_name(class_name: str) -> str:
    """
    現在状態フィールド名を生成する。
    """
    return f"_{class_name.lower()}_current_state"

def get_switch_to_version_method_name(class_name: str) -> str:
    """
    バージョン切替メソッド名を生成する。
    """
    return f"_{class_name.lower()}_switch_to_version"

def get_primary_class_def(tree: ast.AST) -> Optional[ast.ClassDef]:
    """
    ASTから最初のクラス定義ノードを返す。
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            return node
    return None

def get_all_class_defs(tree: ast.AST) -> list[ast.ClassDef]:
    """
    AST内の全クラス定義ノードを返す。
    """
    class_defs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_defs.append(node)
    return class_defs

def get_class_version_info(class_node: ast.ClassDef) -> Tuple[Optional[str], Optional[str]]:
    """
    クラス定義からベース名とバージョン番号文字列（例: "1", "2"）を抽出する。

    戻り値:
        (base_name, version_number_string)。versionedでない場合は (None, None)。
    """
    return parse_versioned_name(class_node.name)

def get_class_version_info_from_name(class_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    クラス名からベース名とバージョン番号文字列（例: "1", "2"）を抽出する。

    戻り値:
        (base_name, version_number_string)。versionedでない場合は (None, None)。
    """
    return parse_versioned_name(class_name)

def get_impl_class_name(version_num_str: str) -> str:
    """
    実装クラス名を生成する。
    """
    return f"_V{version_num_str}_Impl"

def get_instance_field_name(version_num_str: str) -> str:
    """
    インスタンスフィールド名を生成する。
    """
    return f"_v{version_num_str}_instance"

def get_sync_function_version_info(func_node: ast.FunctionDef) -> Tuple[Optional[int], Optional[int]]:
    """
    sync関数のASTから、名前に含まれる from/to のバージョン番号を抽出する。
    
    例: 'sync_from_v1_to_v2' -> (1, 2)

    戻り値:
        (from_version, to_version)。一致しない場合は (None, None)。
    """
    return parse_sync_function_name(func_node.name)

