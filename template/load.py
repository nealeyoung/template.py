#!/usr/bin/env python -w

import sys
import os

from .compile import exec_template_in_host_module
from . import file_extension, host_module

_template_hide_traceback_ = True


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
                sys.modules.setdefault(template_module_name, host_module)
                exec_template_in_host_module(file_path)
                return host_module

        print("import template, file not found:", filename,
              file=sys.stderr)
        raise ImportError

loader = _Loader()
