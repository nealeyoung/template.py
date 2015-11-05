#!/usr/bin/env python -w

import sys
import os

from .compile_pyt import compile_pyt
from . import file_extension, host_module, host_module_globals

# See Python 3 documentation for sys.meta_path.


class _Loader:
    def find_module(self, template_module_name, path=None):
        return self if template_module_name.startswith("template.") else None

    def load_module(self, template_module_name):
        # print("--- loading template", module_name, "---",
        #       file=sys.stderr)
        assert template_module_name.startswith("template.")
        try:
            return sys.modules[template_module_name]
        except KeyError:
            pass

        filename = template_module_name[len("template."):] + \
            file_extension

        for d in sys.path:
            path = os.path.join(d, filename)
            if os.path.isfile(path):
                break
        else:
            print("import template, file not found:",
                  filename, file=sys.stderr)
            raise ImportError

        return exec_file_in_host_module(path, template_module_name)

loader = _Loader()


def exec_file_in_host_module(path, template_module_name):
    global host_module_globals, host_module

    assert os.path.splitext(path)[1] == file_extension

    sys.modules.setdefault(template_module_name, host_module)

    # print("INJECTING", filename, file=sys.stderr)
    code_obj = compile_pyt(path)
    exec(code_obj, host_module_globals)

    return host_module
