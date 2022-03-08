import os
import sys
import importlib
import logging
from . import utils

from .calljulia import CallJulia

from . import lib

import logging
LOGGER = logging.getLogger('julia_project.pyjulia')

LOGGER.info("importing julia module")
import julia
from julia import JuliaError
import julia.core
import julia.api


class PyJulia(CallJulia):

    julia = julia

    def __init__(self,
                 julia_path,
                 project_path=None,
                 julia_system_image=None,
                 use_sys_image=None,
                 ):
        self.julia_path = julia_path
        self.project_path = project_path
        self.julia_system_image = julia_system_image
        self.use_sys_image = use_sys_image


    def seval(self, _str):
        return julia.Main.eval(_str.strip())

    # This seems to work with multiple top-level expressions
    def seval_all(self, _str):
        return julia.Main.eval(_str.strip())


    # For before all PyCall/pyjulia code is loaded
    def _seval(self, cmd):
        self.api.jl_eval_string(bytes(cmd.encode('utf8')))


    def simple_import(self, module : str):
        """
        import the julia module `module` and return the python-wrapped module.

        `Example = self.simple_import("Example")`
        """
        return importlib.import_module("julia." + module)


    def _load_JuliaInfo(self):
        _info = julia.api.JuliaInfo.load(julia=self.julia_path)
        LOGGER.info("Loaded JuliaInfo.")
        return _info

    # Note, that this doesn't start the Julia runtime. It does everything to prepare for starting.
    def init_julia_module(self):
        info = self._load_JuliaInfo()
        is_compatible_python = info.is_compatible_python()
        is_pycall_built = info.is_pycall_built()
        LOGGER.info("is_pycall_built = %r", is_pycall_built)
        LOGGER.info("is_compatible_python = %r", is_compatible_python)
        # Both or the following should be prevented by install.py. Except if libpython statically linked.
        if not is_pycall_built:
            raise Exception("PyCall is not built.")
        if not is_compatible_python:
            raise julia.core.UnsupportedPythonError(info)

        api = julia.api.LibJulia.from_juliainfo(info)
        LOGGER.info("Loaded LibJulia.")
        self.api = api
        self.info = info
        self.libjulia = lib.LibJulia(api.libjulia, api.libjulia_path, api.bindir)


    def start_julia(self):
        if os.getenv("JULIA_PROJECT") != self.project_path:
            print("JULIA_PROJECT NOT SET!")
        self.init_julia_module()
        sys_image_path = self.julia_system_image.sys_image_path
        if os.path.exists(sys_image_path):
            if self.use_sys_image is not False:
                self.api.sysimage = sys_image_path
                LOGGER.info("Loading system image %s", sys_image_path)
                try:
                    import juliacall
                    # Unfortunately, PythonCall does a lot of work just by existing in the system image.
                    # So this will slow startup time significantly.
                    # But, because we have PYTHON_JULIACALL_NOINIT = yes, if PythonCall is *not* in
                    # the system image, import juliacall is very fast.
                    LOGGER.info("Loading juliacall to avoid segfault in case PythonCall is in sysimage.")
                except:
                    pass
            else:
                LOGGER.info("Custom system image found, but will not be used")
        else:
            LOGGER.info(f"No custom system image found: {sys_image_path}.")

        # Both the path and possibly the sysimage have been set. Now initialize Julia.
        LOGGER.info("Initializing julia")
        try:
            self.api.init_julia()
            LOGGER.info("api.init_julia() done")
            import julia.Base
            import julia.Main
            import julia.Pkg # Don't remove this, we assume Pkg is imported later
            LOGGER.info("PyCall, Base, and Main imported")
        except JuliaError as err:
            print("An error occured when initializing Julia.")
            raise
        except:
            raise
