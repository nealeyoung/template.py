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
