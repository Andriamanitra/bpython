"""Tools for preparing code to be run in the REPL (removing blank lines,
etc)"""

from codeop import CommandCompiler
from typing import Match
from itertools import tee, islice, chain
import ast
import string
from ..lazyre import LazyReCompile

class NodeVisitor(ast.NodeVisitor):
    def __init__(self):
        self.exprs = []
    def visit_Attribute(self, node: ast.Attribute):
        self.exprs.append(ast.unparse(node))
    def visit_Name(self, node: ast.Expr):
        self.exprs.append(ast.unparse(node))


class DesugaringException(Exception):
    pass


# TODO specifically catch IndentationErrors instead of any syntax errors

indent_empty_lines_re = LazyReCompile(r"\s*")
tabs_to_spaces_re = LazyReCompile(r"^\t+")


def indent_empty_lines(s: str, compiler: CommandCompiler) -> str:
    """Indents blank lines that would otherwise cause early compilation

    Only really works if starting on a new line"""
    initial_lines = s.split("\n")
    ends_with_newline = False
    if initial_lines and not initial_lines[-1]:
        ends_with_newline = True
        initial_lines.pop()
    result_lines = []

    prevs, lines, nexts = tee(initial_lines, 3)
    prevs = chain(("",), prevs)
    nexts = chain(islice(nexts, 1, None), ("",))

    for p_line, line, n_line in zip(prevs, lines, nexts):
        if len(line) == 0:
            # "\s*" always matches
            p_indent = indent_empty_lines_re.match(p_line).group()  # type: ignore
            n_indent = indent_empty_lines_re.match(n_line).group()  # type: ignore
            result_lines.append(min([p_indent, n_indent], key=len) + line)
        else:
            result_lines.append(line)

    return "\n".join(result_lines) + ("\n" if ends_with_newline else "")


def leading_tabs_to_spaces(s: str) -> str:
    def tab_to_space(m: Match[str]) -> str:
        return len(m.group()) * 4 * " "

    return "\n".join(
        tabs_to_spaces_re.sub(tab_to_space, line) for line in s.split("\n")
    )


def preprocess(s: str, compiler: CommandCompiler) -> str:
    return indent_empty_lines(leading_tabs_to_spaces(s), compiler)


def find_first_identifier(source):
    try:
        ast_tree = ast.parse(source)
    except SyntaxError:
        raise DesugaringException("invalid syntax")
    nv = NodeVisitor()
    nv.visit(ast_tree)
    if len(nv.exprs) < 1:
        raise DesugaringException("no identifier names in source")
    return nv.exprs[0]


def desugar(source):
    if source.endswith("??"):
        try:
            identifier = find_first_identifier(source.strip().removesuffix("??"))
            return f'''print({identifier}.__doc__ or "'{identifier}' has no docstring")'''
        except DesugaringException as exc:
            return f"print('Unable to find docs ({exc})')"
    elif source.strip(string.ascii_letters).endswith("!"):
        left, _, right = source.rpartition("!")
        source = f"{right}({left})"
    return source
