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

3. All .pyt files imported by "import template.xxx" are executed in
the namespace (that is, globals()) of the module that imports the
template module (both for variables and for function definitions).
Example:

         # file parent.pyt
         import template.child
         a = 'X'; f = lambda: 'F {{a}} {{b}}'

Then render() can be called in parent.pyt, and it would return the
string "1 Render a=X, f()=F X B."

4. If the module that first imports the template module (via any
"import template" or "import template.xx" statement) is __main__ (the
top-level module, the one that is executed initially), and __main__'s
is itself a .pyt file (its name ends in '.pyt'), then __main__ is also
executed using template semantics.  In this case, the "import
template.."  statements should be at the top of __main__, before any
non-import statement, and __main__ or one of the template files it
imports directly or indirectly should define a "render" function as in
the example above.  After __main__ is executed, render() is
automatically called, and its return value is printed to sys.stdout.
Hence, executing "python3 parent.pyt" in the shell would print "1
Render a=X. f()=X B.".

'''

import sys
import os

import inspect
import types

__all__ = ["load"]

_template_hide_traceback_ = True


# in any traceback, hide stack frames from this package
# http://stackoverflow.com/questions/31949760/how-to-limit-python-traceback-to-specific-files
def _exception_hook(Type, value, tb, original_excepthook=sys.excepthook):
    import traceback as TB
    skip = 1
    while tb:
        if '_template_hide_traceback_' not in tb.tb_frame.f_globals:
            if skip:
                skip -= 1
            else:
                TB.print_tb(tb, limit=1)
        tb = tb.tb_next
    print(Type.__name__ + ":", value, file=sys.stderr)

sys.excepthook = _exception_hook

# ################################################ module constants

file_extension = '.pyt'
gatherer_function_name = '_template_gather_'
decorator_name = '_template_decorator_'

# details of module that imports this module
_importer_stack_depth = next(i for i, f in enumerate(inspect.stack())
                             if i > 1 and f[3] == '<module>')
_importer_stack_frame = inspect.stack()[_importer_stack_depth][0]
_importer_globals = _importer_stack_frame.f_globals
_importer_module_name = _importer_globals['__name__']
_importer_module = sys.modules[_importer_module_name]

importer_filename = _importer_globals['__file__']
importer_is_main = _importer_module_name == '__main__'

assert importer_is_main == \
    (_importer_stack_depth == len(inspect.stack())-1)

host_module = _importer_module
host_module_globals = _importer_module.__dict__

from .gather import gather, decorator
from .load import loader
from .compile import exec_template_in_host_module

# ################################################  CODE

host_module_globals[gatherer_function_name] = gather
host_module_globals[decorator_name] = decorator

# set up support of "import template.xxx"
sys.meta_path.append(loader)


# load is global

def load(module_name):
    '''
    "template.load('x')" is equivalent to "import template.x",
    except it also works when the module name contains periods.
    '''
    loader.load_module(module_name)

# If __main__ imported us and is a pyt file,
# then reload __main__ as pyt template,
# then call render() and exit.

basename, extension = os.path.splitext(importer_filename)

if importer_is_main and extension == file_extension:

    exec_template_in_host_module(importer_filename)

    # https://docs.python.org/2/library/atexit.html
    render = host_module_globals.get("render")
    if isinstance(render, types.FunctionType):
        # error handling handled by sys.excepthook at top of __init__.py
        print(render(), end="")
        sys.exit(0)
    else:
        print("no render function defined for template", file=sys.stderr)
        sys.exit(1)
