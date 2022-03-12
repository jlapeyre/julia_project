import os
import ctypes
import subprocess
import logging

import juliacall
# Comment in original source:
from juliacall import CONFIG

from .calljulia import CallJulia # interface
from . import lib
from . import utils

# This is perhaps heavier than we need. It borrows from pyjulia
# from . import libjulia as libjulia_mod


LOGGER = logging.getLogger('julia_project.juliacall')
LOGGER.info("importing julia_project/juliacall")


def load_libjulia(julia_path,
         project_path=None,
         system_image=None):
    # Find the Julia executable and project
    CONFIG['exepath'] = exepath = julia_path # juliapkg.executable()
    CONFIG['project'] = project = project_path # juliapkg.project()

    # Find the Julia library
    cmd = [exepath, '--project='+project, '--history-file=no',
           '--startup-file=no', '-O0', '--compile=min', '-e',
           'import Libdl; print(abspath(Libdl.dlpath("libjulia")))']
    CONFIG['libpath'] = libjulia_path = subprocess.run(cmd, check=True, capture_output=True, encoding='utf8').stdout
    assert os.path.exists(libjulia_path)
    LOGGER.info(f"libjulia_path: {libjulia_path}")

    current_dir = os.getcwd()

    julia_toplevel = os.path.dirname(os.path.dirname(libjulia_path))
    bindir = os.path.realpath(os.path.join(julia_toplevel, "bin"))

    try:
        os.chdir(os.path.dirname(libjulia_path))
        CONFIG['lib'] = libjulia = ctypes.PyDLL(libjulia_path, ctypes.RTLD_GLOBAL) # <-- avoids segfault
        if os.getenv("JULIA_PROJECT") != project:
            print("JULIA_PROJECT NOT SET!")
            os.environ['JULIA_PROJECT'] = project
        LOGGER.info(f"setting JULIA_PROJECT = {project}")
        if system_image is not None and os.path.exists(system_image):
            LOGGER.info(f"jl_init_with_image({bindir.encode('utf8')},{system_image.encode('utf8')}")
            libjulia.jl_init_with_image__threading.argtypes = []
            libjulia.jl_init_with_image__threading.restype = None
            libjulia.jl_init_with_image__threading(
                bindir.encode('utf8'),
                system_image.encode('utf8'))
        else:
            LOGGER.info("jl_init with default system image")
            libjulia.jl_init__threading.argtypes = []
            libjulia.jl_init__threading.restype = None
            libjulia.jl_init__threading()
        LOGGER.info("libjulia inited.")
        libjulia.jl_eval_string.argtypes = [ctypes.c_char_p]
        libjulia.jl_eval_string.restype = ctypes.c_void_p
    finally:
        os.chdir(current_dir)

    return libjulia, libjulia_path, bindir


def init_pythoncall(libjulia, project_path):
    os.environ['JULIA_PYTHONCALL_PROJECT'] = project_path
    if utils.has_manifest_toml(project_path):
        do_resolve = "false"
    else:
        do_resolve = "true"
    script = f'''
             try
                import Pkg
                Pkg.activate(ENV["JULIA_PYTHONCALL_PROJECT"], io=devnull)
                pt = Base.parsed_toml(Pkg.project().path)
                if ! any(==("PythonCall"), keys(pt["deps"]))
                    Pkg.add("PythonCall")
                    Pkg.resolve()
                    Pkg.instantiate()
                elseif {do_resolve}
                    Pkg.resolve()
                    Pkg.instantiate()
                end
                try
                    import PythonCall
                catch
                    Pkg.resolve()
                    Pkg.instantiate()
                    import PythonCall
                end
            catch err
                print(stderr, "ERROR: ")
                showerror(stderr, err, catch_backtrace())
                flush(stderr)
                rethrow()
            end
            '''
    LOGGER.info("Activating project")
    res = libjulia.jl_eval_string(script.encode('utf8'))
    if res is None:
        raise Exception('PythonCall.jl did not start properly')

    CONFIG['inited'] = True
    LOGGER.info("Done juliacall init .....")


class JuliaCall(CallJulia):

    julia = juliacall

    def __init__(self,
                 julia_path,
                 project_path=None,
                 julia_system_image=None,
                 use_sys_image=None,
                 ):
        self.julia_path = julia_path
        self.project_path = project_path
        self.julia_system_image = julia_system_image
        self._is_initialized = False
        self.use_sys_image = use_sys_image


    # bug requires stripping.
    def seval(self, _str):
        return juliacall.Main.seval(_str.strip())


    def seval_all(self, _str):
        expr = juliacall.Main.Meta.parseall(_str)
        return juliacall.Main.eval(expr)


    def simple_import(self, module : str):
        """
        import the julia module `module` and return the python-wrapped module.
            `Example = self.simple_import("Example")`
        """
        self.seval("import " + module)
        return self.seval(module)


    def start_julia(self):
        if not self._is_initialized:
            if CONFIG['inited']:
                LOGGER.info("CONFIG['inited'] is true, but we are not reall initialized.")
            LOGGER.info("Initializing julia.")
            if self.use_sys_image is not False:
                system_image = self.julia_system_image.sys_image_path
            else:
                system_image = None
            libjulia, libjulia_path, bindir = load_libjulia(
                self.julia_path,
                project_path=self.project_path,
                system_image=system_image
            )
            init_pythoncall(libjulia, self.project_path)
            self.libjulia = lib.LibJulia(libjulia, libjulia_path, bindir)
            self._is_initialized = True
            CONFIG['inited'] = True
