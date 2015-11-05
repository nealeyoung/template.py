#!/usr/bin/env python3

import functools
import sys

active = None


def gather(value):
    '''
    Append str(value) to currently active list of values.

    The template compiler adds a call to this function for
    every Expr (statement expression) executed, passing in
    the value of the Expr after it is evaluated.
    '''
    if active is not None and value not in ('', None):
        active.append(str(value))


def decorator(fn):
    '''
    Decorate a function to start a new active list of values
    before each execution of the function, and to return
    the concatenated list of gathered values when the function
    returns (if the function would otherwise return None.

    The template compiler adds this decorator to every function
    definition in the template.
    '''
    try:
        fn = getattr(fn, '_template_wraps')
    except AttributeError:
        pass

    @functools.wraps(fn)
    def fn2(*args, **kwds):
        global active

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
