# template.py

Syntactic sugar for convenient templating in Python 3.

## Format strings via string dequoting

WIthin string constants, {{ ... }} subtrings are "dequoted":

        b = 'hello'
        x = "{{b}} world"

        assert x == "hello world"  # this assertion passes

(Under the hood, the assignment to x above is translated into

        x = "".join(str(b), " world")

Dequoting can be nested.)

## Functions concatenate expression statements.

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

## All templates share the global namespace

When template files are imported, each is executed directly in the
namespace of the top-level file.  Breaking modularity in this way
makes it easy to define a base template with parameters and blocks,
which can be over-ridden to customize the template.  For example,
suppose file `base.pyt` contains

    in file base.pyt:

        x = 'default x'
        y = 'default y'
        
        def f():
            'default f {{x}} {{y}}'

        def render():
            f(1)

Then file `custom.pyt` can contain

    in file custom.pyt:

        #/usr/bin/env python3

        import template.base

        x = 'custom x'
        def f():
            'custom f {{x}} {{y}}'

        assert render() == "custom f custom x default y"   # passes

In `custom.pyt`, the variable `x` refers to the same variable as it
does within `base.pyt`.  Likewise for the functions `f` and `render`.

## Automatic execution of "render()"

After a template file executes, the function `render()` is
automatically called (with no arguments).  The output is printed to
`sys.stdout`.  In the example above, executing the file `custom.pyt`
will print "custom f custom x default y".

## How to make Python treat a file as a "template file"?

For Python to treat a file named "xxx.pyt" as a template file
(enabling the features above), the file name must end in ".pyt".
Also, one of two other things has to happen:

1. Another file imports file `xxx.pyt` via `import template.xxx` (the
"template" prefix must be there!)  or

2. File `xxx.pyt` is executed directly (e.g. via a shell command such
as `python3 xxx.pyt` or just `xxx.pyt`) *and* file `xxx.pyt` imports
the `template` module (either via `import template` or `import
template.base`).


