import ast
import re
from typing import Optional, Tuple

VERSIONED_CLASS_PATTERN = re.compile(r"(.+)__(\d+)__$")
SYNC_FUNC_PATTERN = re.compile(r"_?sync_from_v(\d+)_to_v(\d+)")
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
    match = VERSIONED_CLASS_PATTERN.match(class_node.name)
    if match:
        base_name = match.group(1)
        version_num_str = match.group(2)
        return base_name, version_num_str
    return None, None

def get_class_version_info_from_name(class_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    クラス名からベース名とバージョン番号文字列（例: "1", "2"）を抽出する。

    戻り値:
        (base_name, version_number_string)。versionedでない場合は (None, None)。
    """
    match = VERSIONED_CLASS_PATTERN.match(class_name)
    if match:
        base_name = match.group(1)
        version_num_str = match.group(2)
        return base_name, version_num_str
    return None, None

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
    match = SYNC_FUNC_PATTERN.match(func_node.name)
    if match:
        from_version = int(match.group(1))
        to_version = int(match.group(2))
        return from_version, to_version
    return None, None

