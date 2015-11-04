#!/usr/bin/env python3

'''Syntactic sugar for convenient template generation in python3.

The "template" module tweaks the python3 import system so that (assuming
the template module is on the python import path) the statement

        import template.xxx

will locate a file "xxx.pyt" by searching sys.path, then execute that
file as python but with modified "template" semantics:

1. Before execution, in every string constant, each {{...}} substring is
"dequoted".  E.g. "a{{b}}c" is replaced by "a" + str(b) + "c".  Dequoting
nests: "a {{f('{{x}} b')}} c" becomes "a " + str(f(str(x) + " b")) + "c".

Also, substrings starting with "##" are removed (until the end of
line; this is for commenting multi-line strings).

2. Each function definition is modified so that during execution of
the function, whenever a statement that consists solely of an
expression is executed, the value of the expression is remembered.
(In normal python it would be discarded.)  If the function then has
return value None, the return value is modified to instead be the
concatenation of the remembered values (cast to str's).  Example: the
function render defined below would return "1 Render a=A, f()=f A B."

        # file child.pyt
        import template
        a = 'A'; b = 'B'; f = lambda: 'f {{a}} {{b}}'
        def render():
            1
            " Render a={{a}}, f()={{f()}}."

3. All .pyt files imported by "import template.xxx" use the namespace
(that is, globals()) of the top-level file (both for variables and for
function definitions).  Example:

         # file parent.pyt
         import template.child
         a = 'X'; f = lambda: 'F {{a}} {{b}}'

Then render() can be called in parent.pyt, and it would return the string
"1 Render a=X, f()=F X B."

4. If the top-level file being executed is itself a .pyt file (and it
executes any "import template" or "import template.xx" statements),
then the top-level file is also executed using template semantics.
(Such import statements should be at the top of the file, before any
non-import statement.)  In this case, the file or one of its importing
files should define a "render" function as in the example above.
After the file is executed, render() is automatically called, and its
return value is printed to sys.stdout.  Hence, executing "python3
parent.pyt" in the shell would print "1 Render a=X. f()=X B.".

'''

__all__ = ["load"]
__path__ = []

global load
load = None                     # reset in _template_init


def _template_init():
    import sys
    import os
    import re

    import functools
    # import itertools

    import inspect
    import types
    # import atexit

    import ast

    import imp
    # import importlib

    file_extension = '.pyt'

    # ################################################ shared_globals

    # All template files are executed in the top-level module namespace.
    # (We'd prefer the namespace of the first module with "import template"
    # or "import template.xxx", but don't know how to find that reliably.)

    shared_globals = inspect.stack()[-1][0].f_globals

    # ################################################  compile_pyt_file

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

    gatherer_function_name = "_template_gather_"
    decorator_name = "_template_decorator_"

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

    def compile_pyt_file(filename):
        '''
        Return python codeobj for pyt source in filename.
        '''
        assert os.path.splitext(filename)[1] == file_extension
        with open(filename) as f:
            code = f.read()
        tree = ast.parse(code, filename=filename, mode='exec')
        tree = _Pyt_to_python().visit(tree)
        ast.fix_missing_locations(tree)
        return compile(tree, filename, mode='exec', dont_inherit=True)

    # ################################################ gather, decorate

    def _gather_factory():
        active = None

        def gather(expr_value):
            if active is None or expr_value in ('', None):
                return
            active.append(str(expr_value))

        def decorate(fn):
            try:
                fn = getattr(fn, '_template_wraps')
            except AttributeError:
                pass

            @functools.wraps(fn)
            def fn2(*args, **kwds):
                nonlocal active

                tmp, active = active, []
                result1 = fn(*args, **kwds)
                result2 = "".join(active)
                active = tmp

                if result1 is None:
                    return result2
                if result2 != "":
                    print("template.py warning: discarding gathered value",
                          '"' + result2 + '"',
                          "from function", fn.__name__,
                          file=sys.stderr)
                return result1

            fn2._template_wraps = fn
            return fn2

        return gather, decorate

    gather, decorate = _gather_factory()

    # references to these two globals are injected by compile_pyt_file
    shared_globals[gatherer_function_name] = gather
    shared_globals[decorator_name] = decorate

    # ################################################  loader

    # Hook into python import system so that
    # 'import template.XXX'
    # exec's XXX.pyt (compiled as pyt file) in the shared_globals namespace.
    # (See Python 3 documentation for sys.meta_path.)

    class _Loader:
        def find_module(self, module_name, path=None):
            return self if module_name.startswith("template.") else None

        def exec_file_in_shared_globals(self, path, module_name):
            nonlocal shared_globals

            # Insert stub module in import module cache
            stub = imp.new_module(module_name)
            stub.__file__ = path
            stub.__path__ = []
            stub.__loader__ = self
            stub.about = path + " was executed in global namespace"
            sys.modules.setdefault(module_name, stub)

            # print("INJECTING", filename, file=sys.stderr)

            code_obj = compile_pyt_file(path)
            exec(code_obj, shared_globals)
            return stub

        def load_module(self, module_name, directory=None):
            # print("--- loading template", module_name, "---",
            #       file=sys.stderr)
            assert module_name.startswith("template.")
            try:
                return sys.modules[module_name]
            except KeyError:
                pass
            filename = module_name[len("template."):] + file_extension
            for d in sys.path:
                path = os.path.join(d, filename)
                if os.path.isfile(path):
                    break
            else:
                print("import template, file not found:",
                      filename, file=sys.stderr)
                raise ImportError

            return self.exec_file_in_shared_globals(path, module_name)

    loader = _Loader()

    # ################################################  try_render

    def try_render():
        nonlocal shared_globals

        # https://docs.python.org/2/library/atexit.html
        render = shared_globals.get("render")
        if isinstance(render, types.FunctionType):
            # print("calling render")
            try:
                print(render(), end="")
                status = 0
            except:
                import traceback
                traceback.print_exc(file=sys.stderr)
                status = 1
        else:
            print("no template render function defined", file=sys.stderr)
            status = 1
        return status

    # ################################################  CODE

    # print("setting up template system")

    # set up support of "import template.xxx"
    sys.meta_path.append(loader)

    # define global load function
    global load

    def load(module_name):
        '''
        "template.load('x')" is equivalent to "import template.x",
        except it also works when the module name contains periods.
        '''
        loader.load_module(module_name)


    # atexit.register(render_and_exit)

    # If the file that imported us is a pyt file,
    # reload it as pyt template, then call render() and exit.
    # Note that template.py code is executed only for the _first_
    # "import template" or "import template.XXX".  We assume
    # this occurs in the top-level (i.e., executed) file.
    filename = shared_globals['__file__']
    basename, extension = os.path.splitext(filename)
    if extension == file_extension:
        module_name = "template." + basename
        loader.exec_file_in_shared_globals(filename, module_name)
        status = try_render()
        sys.exit(status)

_template_init()
del _template_init
