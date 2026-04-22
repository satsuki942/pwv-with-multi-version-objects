import ast
from dataclasses import dataclass
from typing import Literal

SIGNATURE_INSPECT_ALIAS = "_mvo_inspect"
SIGNATURE_BIND_HELPER_NAME = "_mvo_can_bind"


@dataclass
class ParameterInfo:
    """関数・メソッド引数1つ分の情報を保持するデータクラス。"""
    name: str
    type: str
    has_default_value: bool
    kind: Literal[
        'POSITIONAL_ONLY',
        'POSITIONAL_OR_KEYWORD',
        'VAR_POSITIONAL',
        'KEYWORD_ONLY',
        'VAR_KEYWORD',
    ]

    def __eq__(self, other):
        if not isinstance(other, ParameterInfo):
            return NotImplemented

        if self.kind in ('VAR_POSITIONAL', 'VAR_KEYWORD'):
            return self.kind == other.kind

        return (
            self.name == other.name
            and self.type == other.type
            and self.has_default_value == other.has_default_value
            and self.kind == other.kind
        )


def create_parameter_infos(function_node: ast.FunctionDef, skip_first_arg: bool = False) -> list[ParameterInfo]:
    parameters: list[ParameterInfo] = []
    args = function_node.args
    pos_args = args.posonlyargs + args.args
    defaults_start_index = len(pos_args) - len(args.defaults)

    for i, arg in enumerate(args.posonlyargs):
        if skip_first_arg and i == 0:
            continue

        parameters.append(ParameterInfo(
            name=arg.arg,
            type=ast.unparse(arg.annotation) if arg.annotation else "any",
            has_default_value=(i >= defaults_start_index),
            kind='POSITIONAL_ONLY',
        ))

    for i, arg in enumerate(args.args):
        if skip_first_arg and not args.posonlyargs and i == 0:
            continue

        combined_index = len(args.posonlyargs) + i
        parameters.append(ParameterInfo(
            name=arg.arg,
            type=ast.unparse(arg.annotation) if arg.annotation else "any",
            has_default_value=(combined_index >= defaults_start_index),
            kind='POSITIONAL_OR_KEYWORD',
        ))

    if args.vararg:
        parameters.append(ParameterInfo(
            name=args.vararg.arg,
            type=ast.unparse(args.vararg.annotation) if args.vararg.annotation else "any",
            has_default_value=False,
            kind='VAR_POSITIONAL',
        ))

    for i, arg in enumerate(args.kwonlyargs):
        parameters.append(ParameterInfo(
            name=arg.arg,
            type=ast.unparse(arg.annotation) if arg.annotation else "any",
            has_default_value=args.kw_defaults[i] is not None,
            kind='KEYWORD_ONLY',
        ))

    if args.kwarg:
        parameters.append(ParameterInfo(
            name=args.kwarg.arg,
            type=ast.unparse(args.kwarg.annotation) if args.kwarg.annotation else "any",
            has_default_value=False,
            kind='VAR_KEYWORD',
        ))

    return parameters


def build_signature_runtime_support() -> list[ast.AST]:
    return ast.parse(f"""
import inspect as {SIGNATURE_INSPECT_ALIAS}

def {SIGNATURE_BIND_HELPER_NAME}(func, args, kwargs, extra_kwargs=None):
    bind_kwargs = dict(kwargs)
    if extra_kwargs is not None:
        for name in extra_kwargs:
            if name in bind_kwargs:
                return False
        bind_kwargs.update(extra_kwargs)
    try:
        {SIGNATURE_INSPECT_ALIAS}.signature(func).bind(*args, **bind_kwargs)
    except TypeError:
        return False
    return True
""").body


def create_signature_bind_check_call(
    func: ast.expr,
    extra_kwargs: ast.expr | None = None,
) -> ast.Call:
    args: list[ast.expr] = [
        func,
        ast.Name(id="args", ctx=ast.Load()),
        ast.Name(id="kwargs", ctx=ast.Load()),
    ]
    if extra_kwargs is not None:
        args.append(extra_kwargs)
    return ast.Call(
        func=ast.Name(id=SIGNATURE_BIND_HELPER_NAME, ctx=ast.Load()),
        args=args,
        keywords=[],
    )
