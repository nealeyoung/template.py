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
    import atexit

    import ast

    import imp
    # import importlib

    # ################################################ Gatherer.gather
    # ################################################ Gatherer.decorate

    class Gatherer:
        _active = None

        @classmethod
        def _begin(cls):
            self = cls()
            self.prev = cls._active
            self.strings = []
            cls._active = self

        @classmethod
        def _end(cls):
            self = cls._active
            cls._active = self.prev
            return "".join(self.strings)

        @classmethod
        def gather(cls, segment):
            if (not cls._active) or segment in ('', None):
                return
            segment = str(segment)
            cls._active.strings.append(segment)

        @staticmethod
        def decorate(fn):
            try:
                fn = getattr(fn, '_neal_wraps')
            except AttributeError:
                pass

            @functools.wraps(fn)
            def fn2(*args, **kwds):
                Gatherer._begin()
                result1 = fn(*args, **kwds)
                result2 = Gatherer._end()
                if result1 is None:
                    return result2
                else:
                    if result2 != "":
                        print("template.py warning: discarding gathered value",
                              '"' + result2 + '"', "from function", fn.__name__,
                              file=sys.stderr)
                    return result1

            fn2._neal_wraps = fn
            return fn2

    # ################################################  pyt_file_to_codeobj
    # ################################################

    def _split_top_level(s):
        d = i = 0
        start = 0
        while i+2 <= len(s):
            if s[i:i+2] == '{{':
                if d == 0:
                    yield (0, start, i)
                    start = i+2
                d += 1
                i += 2
            elif s[i:i+2] == '}}':
                d -= 1
                if d < 0:
                    raise Exception("unbalanced format string " + str(d))
                if d == 0:
                    yield (1, start, i)
                    start = i+2
                i += 2
            else:
                i += 1
        if d > 0:
            raise Exception("unbalanced format string " + str(d))
        yield (0, start, len(s))

    gatherer_function_name = "_template_gather_"
    gatherer_function = Gatherer.gather
    decorator_name = "_template_decorator_"
    decorator_function = Gatherer.decorate

    class _Pyt_to_python(ast.NodeTransformer):

        def visit_Expr(self, node):
            '''
            Expr's are top-level expressions whose values are normally discarded.
            Modify the tree to call the gatherer function on each instead.
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
            Add the decorator to every function definition.
            '''
            node = self.generic_visit(node)
            func = ast.Name(id=decorator_name, ctx=ast.Load())
            node.decorator_list.append(func)
            return node

        def visit_Str(self, str_node):
            '''
            Replace each string constant with its {{...}} expansion.
            '''
            s = str_node.s
            s = re.sub(r"##.*", "", s)
            split = tuple(_split_top_level(s))
            if len(split) == 0 or (len(split) == 1 and s == str_node.s):
                return str_node

            args = []
            for to_parse, i, j in split:
                assert i <= j
                if i == j:
                    continue
                if not to_parse:
                    node1 = ast.Str(s=s[i:j])
                else:
                    try:
                        node1 = ast.parse("str(" + s[i:j] + ")",
                                          filename="<format string>",
                                          mode='eval')
                    except:
                        print("format parse error", file=sys.stderr)
                        print('fragment', s[i:j], file=sys.stderr)
                        print('File "' + filename +
                              '", line', str_node.lineno, file=sys.stderr)
                        sys.exit(1)
                    node1 = node1.body
                    node1 = self.generic_visit(node1)
                args.append(node1)

            args = [ast.Tuple(elts=args, ctx=ast.Load())]
            func_node = ast.Attribute(value=ast.Str(""),
                                      attr="join",
                                      ctx=ast.Load())
            call_node = ast.Call(func=func_node,
                                 args=args,
                                 keywords=[],
                                 starargs=None,
                                 kwargs=None)
            return call_node

    _pyt_to_python = _Pyt_to_python().visit

    def pyt_file_to_codeobj(filename):
        '''
        Return python codeobj for pyt source in filename.
        '''

        assert os.path.splitext(filename)[1] == ".pyt"

        with open(filename) as f:
            code = f.read()
        tree = ast.parse(code, filename=filename, mode='exec')
        tree = _pyt_to_python(tree)
        ast.fix_missing_locations(tree)
        codeobj = compile(tree, filename, mode='exec', dont_inherit=True)
        return codeobj

    # ################################################  loader
    # ################################################

    # modify python import system so that
    # import template.XXX
    # calls load_module('template.XXX') below
    class _Loader:
        def find_module(self, fullname, path=None):
            if fullname.startswith("template."):
                return self
            return None

        def load_file(self, path, modulename):
            nonlocal template_globals

            m = imp.new_module(modulename)
            m.__file__ = modulename
            m.__path__ = []
            m.__loader__ = self
            m.about = "This pyt was injected directly into global namespace"
            sys.modules.setdefault(modulename, m)

            # print("INJECTING", filename, file=sys.stderr)

            code_obj = pyt_file_to_codeobj(path)
            exec(code_obj, template_globals)
            return m

        def load_module(self, fullname, directory=None):
            # print("--- loading template", fullname, "---", file=sys.stderr)

            if os.path.splitext(fullname)[1] == ".pyt":
                fullname = fullname[:-len(".pyt")]

            try:
                return sys.modules[fullname]
            except KeyError:
                pass

            assert fullname.startswith("template.")
            filename = fullname[len("template."):]

            if not filename.endswith(".pyt"):
                filename += ".pyt"

            for d in sys.path:
                path = os.path.join(d, filename)
                if os.path.isfile(path):
                    break
            else:
                print("import template, file not found:",
                      filename, file=sys.stderr)
                raise ImportError

            m = self.load_file(path, fullname)
            return m

    loader = _Loader()

    # ################################################  try_render
    # ################################################

    def try_render():
        nonlocal template_globals

        # https://docs.python.org/2/library/atexit.html
        render = template_globals.get("render")
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
    # ################################################

    # print("setting up template system")

    # set up mechanism to support "import template.xxx"
    # for loading template in file "xxx.pyt"
    sys.meta_path.append(loader)

    # but "import template.xx.yy" doesn't work (in case of file "xx.yy.pyt")
    # provide replacement "template.load("xx.yy")"

    global load

    def load(modulename):
        '''
        "template.load('x')" is equivalent to "import template.x",
        except it also works when the module name contains periods.
        '''
        loader.load_module(modulename)

    # all loaded pyt files share globals with the top-level module
    # (we'd prefer the first module with "import template" or
    # "import template.xxx", but that seems harder to do reliably)
    template_globals = inspect.stack()[-1][0].f_globals

    # references to these two globals are injected by pyt_file_to_codeobj
    template_globals[gatherer_function_name] = gatherer_function
    template_globals[decorator_name] = decorator_function

    # atexit.register(render_and_exit)

    # If the file that imported us is a pyt file,
    # reload it as pyt template, then call render() and exit.
    # Note that _template_init() is called only for the forst
    # "import template" or "import template.XXX"
    filename = template_globals['__file__']
    basename, extension = os.path.splitext(filename)
    if extension == '.pyt':
        modulename = "template." + basename
        loader.load_file(filename, modulename)
        status = try_render()
        sys.exit(status)

_template_init()
del _template_init
