import logging
import os
import sys
from os.path import dirname
import shutil
import julia
from julia.api import LibJulia, JuliaInfo
#import jill.utils
import find_julia
from ._julia_system_image import JuliaSystemImage
from ._utils import query_yes_no


_QUESTIONS = {'install' : "No Julia installation found. Would you like jill.py to download and install Julia?",
              'compile' :
"""
I can compile a system image after installation.
Compilation may take a few, or many, minutues. You may compile now, later, or never.
Would you like to compile a system image after installation?
""",
              'depot' :
"""
You can install all of the Julia packages and package information in a module-specific "depot",
that is, one specific to this Python module. This may allow you to use Julia with python projects
that have different Python installation locations.
Or you can install packages in the standard per-user Julia "depot".
Would you like to use a python-module-specific depot for Julia packages?
"""
              }

_INCOMPATIBLE_PYTHON_QUESTION = """
The currently running libpython is different from the one that was used to build
the required Julia package PyCall.jl.
They are required to be the same. I can take one of three actions:
1. "Rebuild" PyCall to use the currently running libpython. This means PyCall will no
 longer work with the libpython that it was previously built with.
2. Create a Julia depot specific to this python package. All Julia packages, including PyCall,
as well as cached, compiled code will be stored in this depot. The version of PyCall in your
main depot (the one currently causing this problem) and the one in your new python-package-specific depot
can coexist. This will duplicate a lot of the data stored in your main depot.
3. Print a more detailed error message and exit.
"""

class JuliaProject:
    """
    A class to manage a Julia project with a Python front end.

    The Julia project exists within a python module.

    This class manages
    1) Setting up the julia module provided by pyjulia, including building PyCall.jl
    2) Downloading and installing Julia packages (and a registry)
    3) Setting up the Julia module, including loading a custom system image
    4) Loading Julia modules
    5) Compiling a system image for the Julia Project

    Parameters
    ----------
    name : str
        The name of the project. Used to construct system image file name and in the logger.
    package_path : str
        The top level directory of the installed Python project that is using julia_project
    registry_url : str, optional
        The url of a Julia registry. This registry will be installed automatically.
    preferred_julia_versions : list, optional
        A list of preferred jill.py-installed Julia versions. When searching for a jill.py-installed
        Julia the first of these versions found will be recorded. Defaults to `['1.7', '1.6', 'latest']`.
    sys_image_dir : str
        The directory under `package_path` in which the system image is built. Defaults to "system_image".
    sys_image_file_base : str
        The basename for the system image file. The julia version is appended to this name. Defaults to
        `"sys_" + name`.
    env_prefix : str
        A prefix to all environment variables controlling the project. Defaults to "JULIA_PROJECT_".
    depot : bool, optional
        Whether a project-specific depot will be used, rather than the default depot. If `None`, then
        the user may be prompted for a value.
    post_init_hook : function
         A function to call after the init method.
    logging_level
        The logging level. For example `logging.INFO`. Optional. If omitted, then no logging is done.
    console_logging : bool
        If `True` then log to the console as well as to a file.
    """

    def __init__(self,
                 name,
                 package_path,
                 registry_url=None,
                 preferred_julia_versions = None,
                 sys_image_dir="sys_image",
                 sys_image_file_base=None,
                 env_prefix="JULIA_PROJECT_",
                 depot=None,
                 post_init_hook=None,
                 logging_level=None,
                 console_logging=False,
                 ):

        self.name = name
        self.package_path = package_path
        self.julia_src_dir = os.path.join(self.package_path, "julia_src")
        self.julia_path = None
        self.registry_url = registry_url
        if preferred_julia_versions is None:
            preferred_julia_versions = ['1.7', '1.6', 'latest']
        self.preferred_julia_versions = preferred_julia_versions
        self.sys_image_dir = sys_image_dir
        self.sys_image_file_base = sys_image_file_base # May be None
        self.env_prefix = env_prefix
        self._logging_level = logging_level
        self._console_logging = console_logging
        self._question_results = {'install': None, 'compile': None, 'depot': depot}
        self._SETUP = False # What is diff between _SETUP and _INITIALIZE ?
        self._INITIALIZED = False
        self._INITIALIZING = False
        self._DISABLE_INIT = False
        self._post_init_hook = post_init_hook
        os.environ['PYCALL_JL_RUNTIME_PYTHON'] = shutil.which("python")


    def _maybe_set_depot(self):
        if self._question_results['depot']:
            os.environ["JULIA_DEPOT_PATH"] = os.path.join(self.package_path, "depot")
            self.logger.info("Using private depot.")
        else:
            self.logger.info("Using default depot.")


    def _load_JuliaInfo(self):
        self._maybe_set_depot()
        self.logger.info("Loaded JuliaInfo.")
        return JuliaInfo.load(julia=self.julia_path)


    def _in_inst_dir(self, rel_path):
        """Return absolute path from path relative to installation dir."""
        return os.path.join(self.package_path, rel_path)


    def setup(self):
        self.setup_logging()  # level=self._logging_level, console=self._console_logging
        self.logger.info("Initing JuliaProject")
        self.read_environment_variables()
        depot_path =  self._in_inst_dir("depot")
        if os.path.isdir(depot_path) and not self._question_results['depot'] == False:
            self._question_results['depot'] = True
            self.logger.info("Found existing Python-project specific Julia depot")
        self._SETUP = True


    def  disable_init(self):
        self._DISABLE_INIT = True


    def  enable_init(self):
        self._DISABLE_INIT = False


    def ensure_init(self):
        if not self._INITIALIZED and not self._INITIALIZING and not self._DISABLE_INIT:
            try:
                self._INITIALIZING = True
                self.init()
            finally:
                self._INITIALIZING = False


    def init(self):
        """Run all steps to initialize and load Julia and the Julia project."""
        self.run()


    # TODO: deprecate in favor of init above
    def run(self):
        if not self._SETUP:
            self.setup()
        self.set_toml_paths()
        self.find_julia()
        if self.julia_path is None:
            raise FileNotFoundError("No julia executable found")
        self.init_julia_module()
        self.julia_system_image = JuliaSystemImage(
            self.name,
            sys_image_dir=os.path.join(self.package_path, self.sys_image_dir),
            sys_image_file_base=self.sys_image_file_base,
            julia_version = self.info.version_raw,
            logger = self.logger
            )
        self.start_julia()
        self.activate_project()
        self.diagnostics_after_init()
        self.check_and_install_julia_packages()
        if self._post_init_hook is not None:
            self._post_init_hook()
        self._INITIALIZED = True


    def _envname(self, env_var):
        return self.env_prefix + env_var


    def _getenv(self, env_var):
        return os.getenv(self.env_prefix + env_var)


    def read_environment_variables(self):
        result = self._getenv("INSTALL_JULIA")
        if result:
           if result == 'y':
               self._question_results['install'] = True
               self.logger.info(f"read {self._envname('INSTALL_JULIA')} = 'y'")
           elif result == 'n':
               self._question_results['install'] = False
               self.logger.info(f"read {self._envname('INSTALL_JULIA')} = 'n'")
           else:
               raise ValueError(f"{self._envname('INSTALL_JULIA')} must be y or n")
        result = self._getenv("COMPILE")
        if result:
           if result == 'y':
               self._question_results['compile'] = True
               self.logger.info(f"read {self._envname('COMPILE')} = 'y'")
           elif result == 'n':
               self._question_results['compile'] = False
               self.logger.info(f"read {self._envname('COMPILE')} = 'n'")
           else:
               raise ValueError(f"{self._envname('COMPILE')} must be y or n")
        result = self._getenv("DEPOT")
        if result:
           if result == 'y':
               self._question_results['depot'] = True
               self.logger.info(f"read {self._envname('DEPOT')} = 'y'")
           elif result == 'n':
               self._question_results['depot'] = False
               self.logger.info(f"read {self._envname('DEPOT')} = 'n'")
           else:
               raise ValueError(f"{self._envname('DEPOT')} must be y or n")


    def setup_logging(self):
        self.logger = logging.getLogger(self.name)
        if self._logging_level is None:
             # fh = logging.NullHandler() # probably don't need this
            return None

        result = self._getenv("LOG_PATH")
        if result:
            self.log_file_path = result
        else:
            self.log_file_path = self.name + '.log'
        fh = logging.FileHandler(self.log_file_path)
        logging_level = self._logging_level
        self.logger.setLevel(logging_level)
        fh.setLevel(logging_level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        if self._console_logging:
            ch = logging.StreamHandler()
            ch.setLevel(self._logging_level)
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)


    def _ask_question(self, question_key):
        if self._question_results[question_key] is None:
            result = query_yes_no(_QUESTIONS[question_key])
            self._question_results[question_key] = result


    def _ask_questions(self):
        for q in self._question_results.keys():
            self._ask_question(q)


    # The module find_julia provides finding julia with a single function call.
    # Unfortunately, we have this much more complicated logic, because we want to ask all questions at once.
    def find_julia(self):
        if self._question_results['install'] == True:
            confirm_install = True
        else:
            confirm_install = False
        fj = find_julia.FindJulia(
            julia_env_var = self._envname("JULIA_PATH"),
            other_julia_installations = [self._in_inst_dir("julia")],
            confirm_install = confirm_install
            )
        self._find_julia = fj
        julia_path = fj.find_one_julia()
        if julia_path:
            self.julia_path = julia_path
            self._question_results['install'] = False
        else:
            self._ask_question('depot') # ask all questions at once
            self._ask_question('compile')
            fj.prompt_and_install_jill_julia(not_found=True)
            if fj.results.want_jill_install:
                self._question_results['install'] = True
                self.julia_path = fj.results.new_jill_installed_executable
            else:
                self._question_results['install'] = False


    # Note, that this doesn't start the Julia runtime. It does everything to prepare for starting.
    def init_julia_module(self):
        logger = self.logger

        info = self._load_JuliaInfo()
        is_compatible_python = info.is_compatible_python()
        is_pycall_built = info.is_pycall_built()
        logger.info("is_pycall_built = %r", is_pycall_built)
        logger.info("is_compatible_python = %r", is_compatible_python)
        if not is_pycall_built:
            self._ask_questions()

        info = self._load_JuliaInfo() # Make new info so we pick up depot env var in case depot changed
        if is_pycall_built and not is_compatible_python and not self._question_results['depot']:
            sys.stdout.write(_INCOMPATIBLE_PYTHON_QUESTION)
            prompt = "Choose one of 1, 2, 3: "
            while True:
                sys.stdout.write(prompt)
                choice = input()
                if choice not in ("1", "2", "3"):
                    sys.stdout.write("Please respond with '1', '2' or '3'\n")
                else:
                    break
            if choice == '1':
                self._question_results['depot'] = False
                self._ask_questions() # ask remaining questions before working
                julia.install()
            elif choice == '2':
                self._question_results['depot'] = True
                self._ask_questions()
                info = self._load_JuliaInfo()
            else:
                raise julia.core.UnsupportedPythonError(info)


        api = LibJulia.from_juliainfo(info)
        logger.info("Loaded LibJulia.")

        logger.info("Julia version_raw: %s.", info.version_raw)
        self.version_raw = info.version_raw

        if not info.is_pycall_built():
            logger.info("PyCall not built. Installing julia module.")
            self._maybe_remove(self.manifest_toml)
            # TODO: Do we need/want to do the following? If so, we need to create
            # julia_system_image earlier, ie, by now.
            # self._maybe_remove(self.sys_image_manifest_toml)
            self._ask_questions()
            if os.path.exists(self.julia_path):
                julia.install(julia=self.julia_path)
            else:
                julia.install()
        else:
            logger.info("PyCall is already built.")

        self.api = api
        self.info = info


    def set_toml_paths(self):
        self.project_toml = self._in_inst_dir("Project.toml")
        self.julia_project_toml = self._in_inst_dir("JuliaProject.toml")
        self.manifest_toml = self._in_inst_dir("Manifest.toml")


    def start_julia(self):
        logger = self.logger
        sys_image_path = self.julia_system_image.sys_image_path
        if os.path.exists(sys_image_path):
            self.api.sysimage = sys_image_path
            logger.info("Loading system image %s", sys_image_path)
        else:
            logger.info("No custom system image found: %s.", sys_image_path)

        # Both the path and possibly the sysimage have been set. Now initialize Julia.
        logger.info("Initializing julia")
        self.api.init_julia()


    def activate_project(self):
        if not (os.path.isfile(self.project_toml) or os.path.isfile(self.julia_project_toml)):
            msg = f"Neither \"{self.project_toml}\" nor \"{self.julia_project_toml}\" exist."
            logger.error(msg)
            raise FileNotFoundError(msg)
        from julia import Pkg
        # Activate the Julia project
        Pkg.activate(self.package_path) # Use package data in Project.toml
        self.logger.info("Probed Project.toml path: %s", Pkg.project().path)


    def diagnostics_after_init(self):
        # TODO replace several calls for info below using the JuliaInfo object
        # Import these to reexport
        from julia import Main
        self.logger.info("Julia version %s", Main.string(Main.VERSION))

        self.loaded_sys_image_path = Main.eval('unsafe_string(Base.JLOptions().image_file)')
        self.logger.info("Probed system image path %s", self.loaded_sys_image_path)

        # Maybe useful
        from julia import Base
        julia_cmd = julia.Base.julia_cmd()
        self.logger.info("Probed julia command: %s", julia_cmd)


    def check_and_install_julia_packages(self):
        logger = self.logger
        from julia import Pkg
        ### Instantiate Julia project, i.e. download packages, etc.
        # Assume that if built system image exists, then Julia packages are installed.
        if os.path.isfile(self.manifest_toml):
            logger.info("Julia project Manifest.toml found.")
        else:
            print("No Manifest.toml found. Assuming Julia packages not installed, installing...")
            logger.info("Julia packages not installed or found.")
            self._question_results['install'] = False
            self._question_results['depot'] = False # Too late to use depot
            self._ask_questions()
            if self.registry_url:
                logger.info(f"Installing registry from {self.registry_url}.")
                Pkg.Registry.add(Pkg.RegistrySpec(url = self.registry_url))
            else:
                logger.info(f"No registry installation requested.")
            logger.info("Pkg.resolve()")
            Pkg.resolve()
            logger.info("Pkg.instantiate()")
            Pkg.instantiate()
        if self._question_results['compile']:
            self.compile()


    def compile(self):
        """
        Compile a system image for the dependent Julia packages in the subdirectory `./sys_image/`. This
        system image will be loaded the next time you import the Python module.
        """
        self.julia_system_image.compile()


    def _maybe_remove(self, path):
        if os.path.exists(path):
            os.remove(path)
            self.logger.info(f"Removing {path}")


    def clean(self):
        """
        Delete some files created when installing Julia packages. These are Manifest.toml files
        and a compiled system image.
        """
        for _file in [self.manifest_toml, self._in_inst_dir(self.name + '.log')]:
            self._maybe_remove(_file)
        self.julia_system_image.clean()


    def update(self):
        """
        Update the Julia packages that the Python module depends on.

        First, remove possible stale Manifest.toml files and the compiled system image.
        Then update Julia packages and rebuild Manifest.toml file.
        This may help to work around some errors, for instance when compiling.
        """
        self.clean()
        from julia import Pkg
        Pkg.activate(self.package_path)
        self.logger.info("Updating Julia packages")
        Pkg.update()
        Pkg.resolve()
        Pkg.instantiate()
