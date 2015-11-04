# template.py

Syntactic sugar for convenient templating in Python 3.

## Features

### Format strings via string dequoting

WIthin string constants, {{ ... }} subtrings are "dequoted":

        b = 'hello'
        x = "{{b}} world"

        assert x == "hello world"  # this assertion passes

(Under the hood, the assignment to x above is translated into

        x = "".join(str(b), " world")

Dequoting can be nested.)  Also, substrings starting with "##" are
removed (until the end of line; this is for commenting multi-line
strings).

### Functions concatenate expression statements

Within a function, whenever a statement that consists of a Python
expression is executed, instead of discarding the value of the
expression as Python normally would, the value is remembered.  When
the function returns, if the return value would normally be "None"
(either from `return None` or if no `return` statement is executed),
then the return value of None is replaced by the *concatenation of the
remembered expression values*:

        def f():
            for i in range(3):
                " i {{i}}"

        assert f() == " i 0 i 1 i 2"    # this assertion passes

### All templates share the global namespace

When template files are imported, each is executed directly in the
namespace of the top-level file.  Breaking modularity in this way
makes it easy to define a base template with parameters and blocks,
which can be over-ridden to customize the template.  For example,
suppose file `base.pyt` contains

    in file base.pyt:

        x = 'default x'
        y = 'default y'
    
        def f():
            'default'
            ' f {{x}}'
    
        assert f() == "default f default x"
    
        def render():
            '{{f()}} {{y}}'
    
        assert render() == "default f default x default y"

Then file `custom.pyt` can contain

    in file custom.pyt:

        #!/usr/bin/env python3

        import template.base

        assert \
            set(k for k in globals() if not k.startswith('_')) == \
            set(('x', 'f', 'template', 'y', 'render'))
    
        y = 'custom y'
    
        def f():
            'custom'
            ' f {{x}}'
    
        assert f() == "custom f default x"
        assert render() == "custom f default x custom y"

Importing `base.pyt` via `import template.base` executes `base.pyt`
directly in the namespace of `custom.pyt`, so all variables and
functions defined in `base.pyt` are included directly into
`custom.pyt`.  Consequently, the changes that `custom.py` makes to `y`
and `f` are reflected in the output of `render()`.

### Automatic execution of "render()"

After a template file executes, the function `render()` is
automatically called (with no arguments).  The output is printed to
`sys.stdout`.  In the example above, executing the file `custom.pyt`
will print "custom f custom x default y".

## Installation and usage

Download the template.py file and put in somewhere on your module path.

Then, to make Python treat a file named "xxx.pyt" as a template file
(enabling the features above), the file name must end in ".pyt".
Also, one of two other things has to happen:

1. Another file imports file `xxx.pyt` via `import template.xxx` (the
"template" prefix must be there!)  or

2. File `xxx.pyt` is executed directly (e.g. via a shell command such
as `python3 xxx.pyt` or just `xxx.pyt`) *and* file `xxx.pyt` imports
the `template` module (either via `import template` or `import
template.base`).


