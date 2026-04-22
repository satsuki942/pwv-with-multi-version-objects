import ast

from .symbol_table import SymbolTable
from .class_info import ClassInfo
from .method_info import MethodInfo
from ...signature import create_parameter_infos
from ..ast_util import get_class_version_info, get_class_version_info_from_name, UNVERSIONED_CLASS_TAG
from ....common.util.constants import INITIALIZE_METHOD_NAME

class SymbolTableBuilder(ast.NodeVisitor):
    """
    ソースASTを走査してシンボルテーブルを構築する。
    """
    def __init__(self, symbol_table: SymbolTable):
        self.symbol_table = symbol_table

    def visit_ClassDef(self, node: ast.ClassDef):
        class_name, version = get_class_version_info(node)

        if not class_name:
            # 非バージョンクラス
            class_name = node.name
            is_versioned = False
            version = UNVERSIONED_CLASS_TAG
        else:
            is_versioned = True

        existing_class_info = self.symbol_table.lookup_class(class_name)
        methods_map = existing_class_info.methods if existing_class_info else {}
        versioned_bases_map = existing_class_info.versioned_bases if existing_class_info else {}
        versions_set = set(existing_class_info.versions) if existing_class_info else set()

        # versionedクラスの場合のみ継承関係を収集
        if is_versioned:
            versions_set.add(version)
            bases_for_this_version = []
            for base_node in node.bases:
                parent_base_name = None
                parent_version = None

                if isinstance(base_node, ast.Name):
                    parent_base_name, parent_version = get_class_version_info_from_name(base_node.id)
                    if not parent_base_name:
                        parent_base_name = base_node.id
                        parent_version = UNVERSIONED_CLASS_TAG
                elif isinstance(base_node, ast.Attribute):
                    parent_base_name, parent_version = get_class_version_info_from_name(base_node.attr)
                    if not parent_base_name:
                        parent_base_name = ast.unparse(base_node)
                        parent_version = UNVERSIONED_CLASS_TAG
                else:
                    parent_base_name = ast.unparse(base_node)
                    parent_version = UNVERSIONED_CLASS_TAG

                bases_for_this_version.append((parent_base_name, parent_version))
            
            if bases_for_this_version:
                versioned_bases_map[version] = bases_for_this_version
        
        for member in node.body:
            # メソッド定義の収集
            if isinstance(member, ast.FunctionDef):
                method_info = self._create_method_info(member, version)
                if member.name == '__init__' and is_versioned:
                    method_info.name = INITIALIZE_METHOD_NAME
                    method_info.ast_node.name = INITIALIZE_METHOD_NAME
                methods_map.setdefault(method_info.name, []).append(method_info)

        class_info = ClassInfo(
            class_name=class_name,
            is_versioned=is_versioned,
            versioned_bases=versioned_bases_map,
            methods=methods_map,
            versions=versions_set,
        )
        self.symbol_table.add_class(class_info)

    # --- HELPER METHODS ---
    def _create_method_info(self, method_node: ast.FunctionDef, version: str) -> MethodInfo:
        return MethodInfo(
            name=method_node.name,
            version=version,
            parameters=create_parameter_infos(method_node, skip_first_arg=True),
            ast_node=method_node
        )

