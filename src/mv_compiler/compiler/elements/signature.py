import ast
from dataclasses import dataclass
from typing import Literal


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
        parameters.append(ParameterInfo(
            name=arg.arg,
            type=ast.unparse(arg.annotation) if arg.annotation else "any",
            has_default_value=(i >= defaults_start_index),
            kind='POSITIONAL_ONLY',
        ))

    for i, arg in enumerate(args.args):
        if skip_first_arg and i == 0:
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


def create_signature_check_condition(params: list[ParameterInfo]) -> ast.AST:
    """
    実行時引数 (*args, **kwargs) が関数・メソッドシグネチャに合致するかを
    静的に判定するための複合ブール式を生成する。
    """
    # 前提: 位置専用引数、キーワード専用引数、可変長引数は未完全対応。
    param_names = [p.name for p in params]
    num_params = len(param_names)
    required_param_indices = [i for i, p in enumerate(params) if not p.has_default_value]

    conditions = []

    conditions.append(ast.Compare(
        left=ast.Call(func=ast.Name(id='len', ctx=ast.Load()), args=[ast.Name(id='args', ctx=ast.Load())], keywords=[]),
        ops=[ast.LtE()],
        comparators=[ast.Constant(value=num_params)],
    ))

    conditions.append(ast.Compare(
        left=ast.Call(func=ast.Attribute(value=ast.Name(id='kwargs', ctx=ast.Load()), attr='keys', ctx=ast.Load()), args=[], keywords=[]),
        ops=[ast.LtE()],
        comparators=[ast.Set(elts=[ast.Constant(value=name) for name in param_names])],
    ))

    for i, name in enumerate(param_names):
        conditions.append(ast.UnaryOp(
            op=ast.Not(),
            operand=ast.BoolOp(op=ast.And(), values=[
                ast.Compare(
                    left=ast.Call(func=ast.Name(id='len', ctx=ast.Load()), args=[ast.Name(id='args', ctx=ast.Load())], keywords=[]),
                    ops=[ast.Gt()],
                    comparators=[ast.Constant(value=i)],
                ),
                ast.Compare(
                    left=ast.Constant(value=name),
                    ops=[ast.In()],
                    comparators=[ast.Name(id='kwargs', ctx=ast.Load())],
                ),
            ]),
        ))

    for i in required_param_indices:
        name = param_names[i]
        conditions.append(ast.BoolOp(op=ast.Or(), values=[
            ast.Compare(
                left=ast.Call(func=ast.Name(id='len', ctx=ast.Load()), args=[ast.Name(id='args', ctx=ast.Load())], keywords=[]),
                ops=[ast.Gt()],
                comparators=[ast.Constant(value=i)],
            ),
            ast.Compare(
                left=ast.Constant(value=name),
                ops=[ast.In()],
                comparators=[ast.Name(id='kwargs', ctx=ast.Load())],
            ),
        ]))

    conditions.append(ast.Compare(
        left=ast.BinOp(
            left=ast.Call(func=ast.Name(id='len', ctx=ast.Load()), args=[ast.Name(id='args', ctx=ast.Load())], keywords=[]),
            op=ast.Add(),
            right=ast.Call(func=ast.Name(id='len', ctx=ast.Load()), args=[ast.Name(id='kwargs', ctx=ast.Load())], keywords=[]),
        ),
        ops=[ast.LtE()],
        comparators=[ast.Constant(value=num_params)],
    ))

    return ast.BoolOp(op=ast.And(), values=conditions)
