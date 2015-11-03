# template.py

Syntactic sugar for convenient templating in Python 3.

Module template.py modifies Python semantics as described below.  To
try it, download the template.py module.  Additional documentation
will be available via `pydoc template`.  .

## Format strings via string dequoting

WIthin string constants, {{ ... }} subtrings are "dequoted":

        b = 'B'
        x = "a {{b}} c"
        assert x == "a B c"  # this assertion passes

Under the hood, the assignment to x above is translated into

        x = "".join("a ", str(b), " c")

## Concatenating expressions within functions

Each function definition in the template file is modified so that,
when the function executes, whenever a statement that consists of an
expression is executed, the value of that expression is remembered,
and when the function returns, if it would otherwise return "None",
the return value of None is replaced by the concatenation of the
remembered expression values:

        def f():
            for i in range(3):
                " i={{i}}"

        assert f() == " i=0 i=1 i=2"    # this assertion passes

## All templates share the global namespace

When template files are imported, each is executed directly in the
namespace of the top-level file.  Breaking modularity in this way
makes it easy to define a base template with parameters and blocks
that can be over-ridden to customize the template.  For example,
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

        assert render() == "custom f custom x default y". # passes

In `custom.pyt`, the variable `x` refers to the same variable as it
does within `base.pyt`.  Likewise for the functions `f` and `render`.

## Automatic execution of "render()"

If the file that is executed at the top level is a template file, and
it (or one of the template files it imports) defines a function called
`render`, then, at exit, that function will be automatically called
with no arguments, and the output will be printed to sys.stdout.  In
the example above, executing the file `custom.pyt` will print out
"custom f custom x default y".

## What makes a file a "template file"?

For Python to treat a file named "xxx.pyt" as a template file
(enabling the features above), the file name must end in ".pyt".
Also, one of two other things has to happen:

1. The file is imported within another via `import template.xxx` .

2. The file is executed directly (e.g. via a shell command such as
`python3 xxx.pyt` or just `xxx.pyt`) *and* the file imports the template
module (either via `import template` or `import template.base).


