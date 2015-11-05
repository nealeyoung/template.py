#!/usr/bin/env python -w

import sys
import os

from .compile import compile_template_file
from . import file_extension, host_module, host_module_globals


class _Loader:
    def find_module(self, template_module_name, path=None):
        ''' See Python 3 documentation for sys.meta_path '''
        return self if template_module_name.startswith("template.") else None

    def load_module(self, template_module_name):
        '''
        Load template module (as a result of import template.xxx)
        '''
        assert template_module_name.startswith("template.")
        try:
            return sys.modules[template_module_name]
        except KeyError:
            pass

        filename = template_module_name[len("template."):] + \
            file_extension

        for d in sys.path:
            file_path = os.path.join(d, filename)
            if os.path.isfile(file_path):
                break
        else:
            print("import template, file not found:",
                  filename, file=sys.stderr)
            raise ImportError

        sys.modules.setdefault(template_module_name, host_module)

        return exec_template_in_host_module(file_path)

loader = _Loader()


def exec_template_in_host_module(filename):
    '''
    Compile template file and execute it in host module namespace
    '''
    global host_module_globals, host_module

    assert os.path.splitext(filename)[1] == file_extension

    # print("INJECTING", filename, file=sys.stderr)
    code_obj = compile_template_file(filename)
    exec(code_obj, host_module_globals)

    return host_module
