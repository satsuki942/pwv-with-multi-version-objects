import ast
import re
import copy

from ..template_util import get_template_string
from ..ast_util import get_switch_to_version_method_name
from ....common.util import logger

def build_sync_components(
    class_name: str,
    state_sync_components: tuple | None,
) -> list[ast.FunctionDef]:
    """
    syncモジュール内の関数を staticmethod として生成する。
    """
    if not state_sync_components:
        return []

    _, sync_functions = state_sync_components
    logger.debug_log(f"Injecting {len(sync_functions)} sync functions for {class_name}")

    out: list[ast.FunctionDef] = []
    for func_node in sync_functions:
        func_copy = copy.deepcopy(func_node)
        func_copy.decorator_list.append(ast.Name(id='staticmethod', ctx=ast.Load()))
        out.append(func_copy)

    return out

# 暫定
def build_getattr_setattr_methods(
    class_name: str,
    incompatibility: dict | None = None,
) -> list[ast.FunctionDef]:
    """
    動的属性アクセスのための __getattr__/__setattr__ を生成する。
    """
    if incompatibility is None:
        return []

    getter_template_string = get_template_string("getter_template.py")
    setter_template_string = get_template_string("setter_template.py")
    switch_method_name = get_switch_to_version_method_name(class_name)

    out: list[ast.FunctionDef] = []
    for version, attr_list in incompatibility.items():
        for attr in attr_list:
            logger.debug_log(
                f"Injecting __getattr__ and __setattr__ for attribute '{attr}' in version {version}"
            )
            getter_template_copy = re.sub(r'\[ATTR\]', attr, getter_template_string)
            getter_template_copy = re.sub(r'\[VERSION\]', str(version), getter_template_copy)
            getter_template_copy = re.sub(r'_SWITCH_TO_VERSION_PLACEHOLDER', switch_method_name, getter_template_copy)
            template_ast_getter = ast.parse(getter_template_copy).body[0]

            setter_template_copy = re.sub(r'\[ATTR\]', attr, setter_template_string)
            setter_template_copy = re.sub(r'\[VERSION\]', str(version), setter_template_copy)
            setter_template_copy = re.sub(r'_SWITCH_TO_VERSION_PLACEHOLDER', switch_method_name, setter_template_copy)
            template_ast_setter = ast.parse(setter_template_copy).body[0]

            out.append(template_ast_getter)
            out.append(template_ast_setter)

    return out
