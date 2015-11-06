#!/usr/bin/env python3

import ast
import sys
import os
import re
import itertools

from . import decorator_name, gatherer_function_name, file_extension
from . import host_module_globals, template_traceback_frames_hidden

_template_hide_module_in_traceback_ = True

_FILENAME = None


def compile_template_file(filename):
    '''
    Compile template file into a python code object.
    '''

    with open(filename) as f:
        code = f.read()

    # Template file syntax is valid Python syntax,
    # but with slightly different semantics.

    # 1. Parse the template file using Python syntax.
    # Relying on ast.parse to report syntax errors in template.

    template_AST = ast.parse(code, filename=filename, mode='exec')

    # 2. Change the syntax tree to implement the modified semantics.

    global _FILENAME
    _FILENAME = filename        # used by next call
    python_AST = _pyt_to_python.visit(template_AST)
    ast.fix_missing_locations(python_AST)

    # 3. Compile the modified syntax tree as Python.

    with template_traceback_frames_hidden:
        return compile(python_AST, filename, mode='exec', dont_inherit=True)


def _split_by_braces(strng):
    '''
    Split strng into pieces separated by _top level_ pairs of braces.
    e.g. split 'aa{{b{{c}} }}d{{e}}' to ['aa', ' b{{c}} ', 'd', 'e', ''].

    Used below to implement the dequote mechanism.
    '''
    start = depth = 0
    for match in re.finditer(r"{{|}}", strng):
        prev_depth = depth
        depth += 1 if match.group(0) == '{{' else -1
        assert depth >= 0
        if depth == 0 or prev_depth == 0:
            yield strng[start:match.start()]
            start = match.end()
    assert depth == 0
    yield strng[start:len(strng)]


class _Pyt_to_python(ast.NodeTransformer):
    '''Given abstract syntax tree (AST) for a template, transform it into
    a python AST.  See https://greentreesnakes.readthedocs.org/en/latest/.

    '''
    def visit_Str(self, node):
        '''Dequote each string constant (expand {{...}} appropriately).

        '''

        def str_node(substr):
            return ast.Str(s=substr)

        def parse_tree(substr):
            str_substr = "str(%s)" % substr
            filename_for_parse = "<parse string>"
            try:
                arg_node = ast.parse(str_substr,
                                     filename=filename_for_parse,
                                     mode='eval')
            except SyntaxError:
                if len(substr) > 1000:
                    substr = substr[:1000] + "..."
                print('File "%s", line %s, in substring\n   {{ %s }}' %
                      (_FILENAME, node.lineno, substr),
                      file=sys.stderr)
                print("SyntaxError: invalid syntax", file=sys.stderr)
                sys.exit(1)

            # recursively process the new subtree
            return self.generic_visit(arg_node.body)

        s = node.s
        s = re.sub(r"##.*", "", s)  # remove comments
        if not s:
            return str_node("")

        try:
            # see doc for _split_by_braces
            split = tuple(_split_by_braces(s))
        except AssertionError:
            if len(s) > 1000:
                s = s[:1000] + "..."
            print('File "%s", line %s, in string\n    "%s"' %
                  (_FILENAME, node.lineno, s),
                  file=sys.stderr)
            print("SyntaxError: unbalanced dequote braces", file=sys.stderr)
            sys.exit(1)

        if len(split) == 1:
            return ast.Str(s=split[0])

        args = [f(substr) for (substr, f) in
                zip(split, itertools.cycle((str_node, parse_tree)))]

        # build and return node for "".join(tuple(args))
        func_node = ast.Attribute(value=str_node(""),
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
        Modify the tree to call the gather function on the value of
        each Expr in the template.  (Expr's are statement-expressions.)
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
        Add the decorator to the definition of every function.
        '''
        node = self.generic_visit(node)
        func = ast.Name(id=decorator_name, ctx=ast.Load())
        node.decorator_list.append(func)
        return node

_pyt_to_python = _Pyt_to_python()


def exec_template_in_host_module(filename):
    '''
    Compile template file and execute it in host-module namespace
    '''
    global host_module_globals
    assert os.path.splitext(filename)[1] == file_extension
    codeobj = compile_template_file(filename)

    with template_traceback_frames_hidden:
        exec(codeobj, host_module_globals)
