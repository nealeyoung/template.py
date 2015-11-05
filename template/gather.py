#!/usr/bin/env python3

import functools
import sys

active = None


def gather(expr_value):
    if active is not None and expr_value not in ('', None):
        active.append(str(expr_value))


def decorator(fn):
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
