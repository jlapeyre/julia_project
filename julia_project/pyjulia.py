import os
import sys
import importlib
import logging
from . import utils

from .calljulia import CallJulia

from . import lib
from . import questions

import logging
LOGGER = logging.getLogger('julia_project.pyjulia')

LOGGER.info("importing julia module")
import julia
from julia import JuliaError
import julia.api


class PyJulia(CallJulia):


    julia = julia

    def __init__(self,
                 julia_path,
                 depot_dir=None,
                 data_path=None,
                 depot=None,
                 julia_system_image=None,
                 questions=None,
                 use_sys_image=None,
                 ):
        self.julia_path = julia_path
        self.depot_dir = depot_dir
        self.data_path = data_path
        self.julia_system_image = julia_system_image
        self.questions = questions
        self.use_sys_image = use_sys_image


    def seval(self, _str):
        return julia.Main.eval(_str.strip())

    # This seems to work with multiple top-level expressions
    def seval_all(self, _str):
        return julia.Main.eval(_str.strip())


    def simple_import(self, module : str):
        """
        import the julia module `module` and return the python-wrapped module.

        `Example = self.simple_import("Example")`
        """
        return importlib.import_module("julia." + module)


    def _maybe_set_depot(self):
        if self.questions.results['depot']:
            os.environ["JULIA_DEPOT_PATH"] = self.depot_dir
            LOGGER.info("Using private depot.")
        else:
            LOGGER.info("Using default depot.")


    def _load_JuliaInfo(self):
        self._maybe_set_depot()
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
        if not is_pycall_built:
            self.questions.ask_questions()

        info = self._load_JuliaInfo() # Make new info so we pick up depot env var in case depot changed
        if is_pycall_built and not is_compatible_python and not self.questions.results['depot']:
            self.deal_with_incompatibility()
            # sys.stdout.write(questions._INCOMPATIBLE_PYTHON_QUESTION)
            # prompt = "Choose one of 1, 2, 3: "
            # while True:
            #     sys.stdout.write(prompt)
            #     choice = input()
            #     if choice not in ("1", "2", "3"):
            #         sys.stdout.write("Please respond with '1', '2' or '3'\n")
            #     else:
            #         break
            # if choice == '1':
            #     self.questions.results['depot'] = False
            #     self.questions.ask_questions() # ask remaining questions before working
            #     julia.install()
            # elif choice == '2':
            #     self.questions.results['depot'] = True
            #     self.questions.ask_questions()
            #     info = self._load_JuliaInfo()
            # else:
            #     raise julia.core.UnsupportedPythonError(info)

        api = julia.api.LibJulia.from_juliainfo(info)
        LOGGER.info("Loaded LibJulia.")

        if not info.is_pycall_built():
            LOGGER.info("PyCall not built. Installing julia module.")
            if self.data_path:
                utils.maybe_remove(os.path.join(self.data_path, "Manifest.toml"), LOGGER)
            # TODO: Do we need/want to do the following? If so, we need to create
            # julia_system_image earlier, ie, by now.
            # self._maybe_remove(self.sys_image_manifest_toml)
            self.questions.ask_questions()
            if os.path.exists(self.julia_path):
                julia.install(julia=self.julia_path)
            else:
                julia.install()
        else:
            LOGGER.info("PyCall is already built.")

        self.api = api
        self.info = info
        self.libjulia = lib.LibJulia(api.libjulia, api.libjulia_path, api.bindir)


    def deal_with_incompatibility(self):
        sys.stdout.write(questions._INCOMPATIBLE_PYTHON_QUESTION)
        prompt = "Choose one of 1, 2, 3: "
        while True:
            sys.stdout.write(prompt)
            choice = input()
            if choice not in ("1", "2", "3"):
                sys.stdout.write("Please respond with '1', '2' or '3'\n")
            else:
                break
        if choice == '1':
            self.questions.results['depot'] = False
            self.questions.ask_questions() # ask remaining questions before working
            julia.install()
        elif choice == '2':
            self.questions.results['depot'] = True
            self.questions.ask_questions()
            info = self._load_JuliaInfo()
        else:
            raise julia.core.UnsupportedPythonError(info)


    def start_julia(self, abort=False):
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
            p1 = os.path.join(self.data_path, "Project.toml")
            p2 = os.path.join(self.data_path, "JuliaProject.toml")
            # Activate before PyCall is imported so that we get the correct one
            if os.path.exists(p1) or os.path.exists(p2):
                LOGGER.info("Activating julia project before loading PyCall")
                cmd = f'import Pkg; Pkg.activate("{self.data_path}")'
                self.api.jl_eval_string(bytes(cmd.encode('utf8')))
                LOGGER.info(cmd)
                if not (os.path.exists(os.path.join(self.data_path, "Manifest.toml"))
                    or
                    os.path.exists(os.path.join(self.data_path, "JuliaManifest.toml"))
                    ):
                    cmd = 'import Pkg; Pkg.resolve(); Pkg.instantiate()'
                    self.api.jl_eval_string(bytes(cmd.encode('utf8')))
                    LOGGER.info(cmd)

            if abort:
                print("Please try restarting")
                sys.exit(0)
            # These do more than import Python symbols. They import the Julia modules
            # They are then accesible outside of this Python scope
            import julia.Base
            import julia.Main
            LOGGER.info("PyCall, Base, and Main imported")
        except JuliaError as err:
            print("An error occured when initializing Julia.")
            print(f"The error is: {err}.")
            if self.questions.results['depot'] is not True:
                self.questions.results['depot'] = True
                print("This is likely a misconfigured PyCall.")
                self.deal_with_incompatibility()
                # Following is probably *not* what we want.
                # It probably results in an uncaught exception.
                # We may need to start over at an earlier point. Or perhaps the user must restart.
                self.start_julia(abort=True)
                # print("Trying again with a private depot to get a private PyCall.")
                # print("Try restarting after installation and it may work.")
                # print(f"Alternatively, restart python and set the environment variable JULIA_DEPOT_PATH to {self.depot_dir}")
                # print("before importing your project")
                # print("You will be asked to restart python, but an enormous stack trace will be printed after the prompt.")
            else:
                print("Already using a private depot. No more ideas.")
                print("You might try to rebuild or uninstall PyCall.")
                raise
        except:
            raise
