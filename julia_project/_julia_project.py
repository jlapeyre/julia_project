import logging
import os
from os.path import dirname
import shutil
import julia
import jill.install
import jill.utils

# try:
#     jill.install.get_installed_bin_path
# except:
from ._jill_install import get_installed_bin_paths

_QUESTIONS = {'install' : "No Julia installation found. Would you like jill.py to download and install Julia?",
              'compile' : "Compilation takes four minutes and can be done at any time.\nWould you like to compile a system image after installation?"}


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
    """

    def __init__(self,
                 name,
                 package_path,
                 registry_url=None,
                 preferred_julia_versions = ['1.7', '1.6', 'latest'],
                 sys_image_dir="sys_image",
                 sys_image_file_base=None,
                 env_prefix="JULIA_PROJECT_",
                 logging_level=None,
                 console_logging=False,
                 ):

        self.name = name
        self.package_path = package_path
        self.registry_url = registry_url
        self.preferred_julia_versions = preferred_julia_versions
        self.sys_image_dir = sys_image_dir
        if sys_image_file_base is None:
            sys_image_file_base = "sys_" + name
        self.sys_image_file_base = sys_image_file_base

        self.env_prefix = env_prefix
        self._logging_level = logging_level
        self._console_logging = console_logging
        self._question_results = {'install': None, 'compile': None}
        self._SETUP = False


    def setup(self):
        self.setup_logging()  # level=self._logging_level, console=self._console_logging)
        self.logger.info("Initing JuliaProject")
        self.read_environment_variables()
        self._SETUP = True


    def run(self):
        if not self._SETUP:
            self.setup()
        self.find_julia()
        self.init_julia_module()
        self.set_paths()
        self.start_julia()
        self.diagnostics_after_init()
        self.check_and_install_julia_packages()

    def _envname(self, env_var):
        return self.env_prefix + env_var


    def _getenv(self, env_var):
        return os.getenv(self.env_prefix + env_var)


    def get_preferred_bin_path(self):
        bin_paths = get_installed_bin_paths()
        if bin_paths is None:
            return None
        for pref in self.preferred_julia_versions:
            bin_path = bin_paths.get(pref)
            if bin_path:
                return bin_path
        return next(iter(bin_paths.values())) # Take the first one


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


    def _ask_questions(self):
        for q in self._question_results.keys():
            if self._question_results[q] is None:
                result = jill.utils.query_yes_no(_QUESTIONS[q])
                self._question_results[q] = result


    def find_julia(self):
        logger = self.logger
        julia_path = None
        result = self._getenv("JULIA_PATH")
        if result:
            self.julia_path = result
            self._question_results['install'] = False
            logger.info(f"Using path {self._envname('JULIA_PATH')} = {self.julia_path}")
            return None
        else:
            logger.info(f"Env variable {self._envname('JULIA_PATH')} not set.")

        # The canonical place to look for a Julia installation is ./julia/bin/julia
        julia_directory_in_toplevel = os.path.join(self.package_path, "julia")
        julia_executable_under_toplevel = os.path.join(julia_directory_in_toplevel, "bin", "julia")
        if os.path.exists(julia_executable_under_toplevel) and not julia_path:
            julia_path = julia_executable_under_toplevel
            logger.info("Using executable from julia installation in julia project toplevel '%s'.", julia_path)
        elif os.path.exists(julia_directory_in_toplevel):
            if os.path.isdir(julia_directory_in_toplevel):
                msg = "WARNING: directory ./julia/ found under toplevel, but ./julia/bin/julia not found."
                logger.info(msg)
                print(msg)
            else:
                msg = "WARNING: ./julia found under toplevel, but it is not a directory as expected."
                logger.warn(msg)
                print(msg)
        else:
            logger.info("No julia installation found at '%s'.", julia_directory_in_toplevel)
#            path = get_installed_bin_path(self.preferred_julia_versions)
            path = self.get_preferred_bin_path()
            if path is not None:
                julia_path = path
                logger.info("jill.py Julia installation found: %s.", julia_path)
            else:
                logger.info("No jill.py Julia installation found.")
        if julia_path is None:
            which_julia = shutil.which("julia")
            if which_julia:
                logger.info("Found julia on PATH: %s.", which_julia)
                julia_path = which_julia
            else:
                logger.info("No julia found on PATH.")
                logger.info("Asking to install via jill.py")
                self._ask_questions()
                if self._question_results['install']:
                    logger.info("Installing via jill.py")
                    jill.install.install_julia(confirm=True) # Prompt to install Julia via jill
#                    path = get_installed_bin_path(self.preferred_julia_versions)
                    path = self.get_preferred_bin_path()
                    if path is not None:
                        julia_path = path
                        logger.info("Fresh jill.py Julia installation found: %s.", julia_path)
                    else:
                        logger.info("No fresh jill.py Julia installation found.")
                else:
                    logger.info("User refused installing Julia via jill.py")

        if self._question_results['install'] is None:
            self._question_results['install'] = False
        self.julia_path = julia_path


    def init_julia_module(self):
        julia_path = self.julia_path
        logger = self.logger
        from julia.api import LibJulia, JuliaInfo

        def load_julia(julia_path, logger):
            if os.path.exists(julia_path):
                api = LibJulia.load(julia=julia_path)
                info = JuliaInfo.load(julia=julia_path)
            else:
                logger.info("Searching for julia in user's path")
                api = LibJulia.load()
                info = JuliaInfo.load()
            return api, info
        (api, info) = load_julia(julia_path, logger)
        logger.info("Loaded LibJulia and JuliaInfo.")
        logger.info("Julia version_raw: %s.", info.version_raw)
        self.version_raw = info.version_raw

        if not info.is_pycall_built():
            logger.info("PyCall not built. Installing julia module.")
            self._ask_questions()
            if os.path.exists(julia_path):
                julia.install(julia=julia_path)
            else:
                julia.install()

        self.api = api
        self.info = info


    def get_sys_image_file_name(self):
        return self.sys_image_file_base + "-" + self.version_raw + julia.find_libpython.SHLIB_SUFFIX


    def set_paths(self):
        self.project_toml = os.path.join(self.package_path, "Project.toml")
        self.manifest_toml = os.path.join(self.package_path, "Manifest.toml")
        full_sys_image_dir_path = os.path.join(self.package_path, self.sys_image_dir)
        self.full_sys_image_dir_path = full_sys_image_dir_path
        self.sys_image_path = os.path.join(full_sys_image_dir_path, self.get_sys_image_file_name())
        self.sys_image_project_toml = os.path.join(full_sys_image_dir_path, "Project.toml")
        self.sys_image_manifest_toml = os.path.join(full_sys_image_dir_path, "Manifest.toml")
        self.compiled_system_image = os.path.join(full_sys_image_dir_path, "sys_julia_project" + julia.find_libpython.SHLIB_SUFFIX)


    def start_julia(self):
        logger = self.logger
        self.sys_image_path_exists = os.path.exists(self.sys_image_path)

        if self.sys_image_path_exists:
            self.api.sysimage = self.sys_image_path
            logger.info("Loading system image %s", self.sys_image_path)
        else:
            logger.info("No custom system image found: %s.", self.sys_image_path)

        # Both the path and possibly the sysimage have been set. Now initialize Julia.
        logger.info("Initializing julia")
        self.api.init_julia()


    def diagnostics_after_init(self):
        # TODO replace several calls for info below using the JuliaInfo object
        # Import these to reexport
        logger = self.logger
        from julia import Main
        logger.info("Julia version %s", Main.string(Main.VERSION))

        self.loaded_sys_image_path = Main.eval('unsafe_string(Base.JLOptions().image_file)')
        logger.info("Probed system image path %s", self.loaded_sys_image_path)

        # Maybe useful
        from julia import Base
        julia_cmd = julia.Base.julia_cmd()
        logger.info("Probed julia command: %s", julia_cmd)

        from julia import Pkg
        if not os.path.isfile(self.project_toml):
            msg = f"File \"{self.project_toml}\" does not exist."
            logger.error(msg)
            raise FileNotFoundError(msg)
        # Activate the Julia project
        Pkg.activate(self.package_path) # Use package data in Project.toml
        logger.info("Probed Project.toml path: %s", Pkg.project().path)

        self.julia_src_dir = os.path.join(self.package_path, "julia_src")


    def check_and_install_julia_packages(self):
        logger = self.logger
        from julia import Pkg
        ### Instantiate Julia project, i.e. download packages, etc.
        # Assume that if built system image exists, then Julia packages are installed.
        if self.sys_image_path_exists or os.path.isfile(self.manifest_toml):
            logger.info("Julia project packages found.")
        else:
            print("Julia packages not installed, installing...")
            logger.info("Julia packages not installed or found.")
            self._question_results['install'] = False
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
                self.compile_julia_project()

    def compile_julia_project(self):
        from julia import Main
        current_path = Main.pwd()
        try:
            self._compile_julia_project()
        except:
            pass
        Main.cd(current_path)
        Pkg.activate(self.package_path)


    def _compile_julia_project(self):
        """
        Compile a Julia system image with all requirements for the julia project.
        """
        from julia import Main, Pkg
        logger = self.logger
        if not os.path.isdir(self.full_sys_image_dir_path):
            msg = f"Can't find directory for compiling system image: {self.full_sys_image_dir_path}"
            raise FileNotFoundError(msg)

        if self.loaded_sys_image_path == self.sys_image_path:
            for msg in ("WARNING: Compiling system image while compiled system image is loaded.",
                        f"Consider deleting  {self.sys_image_path} and restarting python."):
                print(msg)
                logger.warn(msg)
        if not os.path.isfile(self.sys_image_project_toml):
            msg = f"File \"{self.sys_image_project_toml}\" does not exist."
            logger.error(msg)
            raise FileNotFoundError(msg)
        if os.path.isfile(self.sys_image_manifest_toml):
            os.remove(self.sys_image_manifest_toml)
        from julia import Pkg
        Main.eval('ENV["PYCALL_JL_RUNTIME_PYTHON"] = Sys.which("python")')
        Pkg.activate(self.full_sys_image_dir_path)
        logger.info("Compiling: probed Project.toml path: %s", Pkg.project().path)
        Main.cd(self.full_sys_image_dir_path)
        try:
            Pkg.resolve()
        except:
            msg = "Pkg.resolve() failed. Updating packages."
            print(msg)
            logger.info(msg)
            Pkg.update()
            Pkg.resolve()
        Pkg.instantiate()
        compile_script = "compile_julia_project.jl"
        logger.info(f"Running compile script {compile_script}.")
        Main.include(compile_script)
        if os.path.isfile(self.compiled_system_image):
            logger.info("Compiled image found: %s.", self.compiled_system_image)
            os.rename(self.compiled_system_image, self.sys_image_path)
            logger.info("Renamed compiled image to: %s.", self.sys_image_path)
            if not os.path.isfile(self.sys_image_path):
                logger.error("Failed renamed compiled image to: %s.", self.sys_image_path)
                raise FileNotFoundError(self.compiled_system_image)
        else:
            raise FileNotFoundError(self.compiled_system_image)


    def update(self):
        logger = self.logger
        if os.path.isfile(self.manifest_toml):
            logger.info(f"Removing {self.manifest_toml}")
            os.remove(self.manifest_toml)
        if os.path.isfile(self.sys_image_manifest_toml):
            logger.info(f"Removing {self.sys_image_manifest_toml}")
            os.remove(self.sys_image_manifest_toml)
        if os.path.isfile(self.sys_image_path):
            logger.info(f"Removing {self.sys_image_path}")
            os.remove(self.sys_image_path)

        from julia import Pkg
        Pkg.activate(self.package_path)
        logger.info("Updating Julia packages")
        Pkg.update()
        Pkg.resolve()
        Pkg.instantiate()
