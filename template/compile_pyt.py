#!/usr/bin/env python3

import ast
import sys
import re

from . import decorator_name, gatherer_function_name


def compile_pyt(filename):
    '''
    Return python codeobj for pyt source in filename.
    '''

    with open(filename) as f:
        code = f.read()
    tree = ast.parse(code, filename=filename, mode='exec')
    tree = _Pyt_to_python().visit(tree)
    ast.fix_missing_locations(tree)
    return compile(tree, filename, mode='exec', dont_inherit=True)


def _split_by_braces(strng):
    '''
    Split strng into pieces separated by _top_level_ pairs of braces.
    e.g. split 'aa{{b{{c}} }}d{{e}}' to ['aa', ' b{{c}} ', 'd', 'e', ''].
    For each piece, return (depth, piece). Depth alternates 0 and 1.
    '''
    start = depth = 0
    for match in re.finditer(r"{{|}}", strng):
        prev_depth = depth
        depth += 1 if match.group(0) == '{{' else -1
        if depth < 0:
            raise Exception("unbalanced format string " + strng)
        if depth == 0 or prev_depth == 0:
            yield (prev_depth, strng[start:match.start()])
            start = match.end()
    if depth > 0:
        raise Exception("unbalanced format string " + strng)
    yield (depth, strng[start:len(strng)])


class _Pyt_to_python(ast.NodeTransformer):
    '''
    Transform pyt abstract syntax tree into python AST.
    See e.g. https://greentreesnakes.readthedocs.org/en/latest/.
    '''

    def visit_Str(self, str_node):
        '''
        Replace each string constant with its {{...}} expansion.
        '''
        s = str_node.s
        s = re.sub(r"##.*", "", s)
        split = tuple(_split_by_braces(s))
        if len(split) == 0 or (len(split) == 1 and s == str_node.s):
            return str_node

        args = []
        for depth, substr in split:
            if substr:
                if depth == 0:
                    args.append(ast.Str(s=substr))
                else:
                    try:
                        arg_node = ast.parse("str(" + substr + ")",
                                             filename="<format string>",
                                             mode='eval')
                    except:
                        print("format parse error", file=sys.stderr)
                        print('substring', substr, file=sys.stderr)
                        print('File "' + filename +
                              '", line', str_node.lineno, file=sys.stderr)
                        sys.exit(1)
                    args.append(self.generic_visit(arg_node.body))

        func_node = ast.Attribute(value=ast.Str(""),
                                  attr="join",
                                  ctx=ast.Load())
        call_node = ast.Call(func=func_node,
                             args=[ast.Tuple(elts=args, ctx=ast.Load())],
                             keywords=[],
                             starargs=None,
                             kwargs=None)
        return call_node

    def visit_Expr(self, node):
        '''
        Expr's are statement-expressions.
        Modify the tree to call gather on the value of each.
        '''
        node = self.generic_visit(node)
        func = ast.Name(id=gatherer_function_name,
                        ctx=ast.Load())
        newvalue = ast.Call(func=func,
                            args=[node.value],
                            keywords=[],
                            starargs=None,
                            kwargs=None)
        newexpr = ast.Expr(value=newvalue)
        return newexpr

    def visit_FunctionDef(self, node):
        '''
        Add decorate decorator to every function definition.
        '''
        node = self.generic_visit(node)
        func = ast.Name(id=decorator_name, ctx=ast.Load())
        node.decorator_list.append(func)
        return node
