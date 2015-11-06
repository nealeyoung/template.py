#!/usr/bin/env python3

import functools
import sys

from . import template_traceback_frames_hidden

_template_hide_module_in_traceback_ = True

active = None


def gather(value):
    '''Append str(value) to currently active list of values.

    The compile_template_file adds a call to this function for every
    Expr (statement expression) executed, passing in the value of the
    Expr after it is evaluated.

    '''
    if active is not None and value not in ('', None):
        active.append(str(value))


def decorator(fn):
    '''Decorate the given function. Before the function starts, create a
    new list for gather() above to store its values in.  When the
    function ends, if the function would return None, instead return
    the concatenation of the stored values.

    The compile_template_file adds this decorator to every function
    definition in the template.

    '''
    try:
        fn = getattr(fn, '_template_wraps')
    except AttributeError:
        pass

    @functools.wraps(fn)
    def fn2(*args, **kwds):
        global active

        special_method = fn.__name__.startswith('__')

        if not special_method:
            tmp, active = active, []

        with template_traceback_frames_hidden:
            result1 = fn(*args, **kwds)
        result2 = "".join(active)

        if special_method:
            return result1

        active = tmp            # restore previously active list

        if result1 is None:
            return result2

        if result2 != "":
            print("template warning: discarding gathered value",
                  '"' + result2 + '"',
                  "from function", fn.__name__,
                  file=sys.stderr)

        return result1

    fn2._template_wraps = fn
    return fn2
