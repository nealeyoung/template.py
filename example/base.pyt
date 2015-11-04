#!/usr/bin/env python3

# the next line just allows this file
# to be executed as a standalone template
import template

x = 'default x'
y = 'default y'


def f():
    'default'
    ' f {{x}}'

assert f() == "default f default x"


def render():
    '{{f()}} {{y}}'

assert render() == "default f default x default y"
