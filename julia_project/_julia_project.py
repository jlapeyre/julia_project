import logging
import os
import shutil
import importlib
import distutils.dir_util
import find_julia
from .julia_system_image import JuliaSystemImage
from . import utils

from .environment import EnvVars
from .questions import ProjectQuestions


# The depot referred to here is the default depot, i.e. ~/.julia
# This true even if the user requests a "private" depo.
# In the latter case, we will have a depot within the default depot.
def _get_project_data_path():
    env_path = utils._get_virtual_env_path()
    if env_path is None:
        env_path = utils._default_depot_path()
    return os.path.join(env_path, "julia_project")


def _calljulia_lib(calljulia, logger=None):
    if calljulia == "pyjulia":
        if logger:
            logger.info("importing PyJulia")
        from .pyjulia import PyJulia
        return PyJulia
    if calljulia == "juliacall":
        if logger:
            logger.info("importing JuliaCall")
        from .juliacall import JuliaCall
        return JuliaCall
    raise ValueError(f"calljulia must be 'pyjulia' or 'juliacall'. Got {calljulia}")


def _validate_calljulia(calljulia):
    if calljulia not in ["pyjulia", "juliacall", None]:
        raise ValueError(f'calljulia must be one of "pyjulia", "juliacall", `None`. Got {calljulia}')



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
    version_spec : str or object, optional
        A Julia version specification that the Julia executable must satisfy. Default "^1".
    strict_version : bool  If `True` disallow prerelease (development) versions of Julia. Default `True`.
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
                 version_spec=None,
                 strict_version=True,
                 sys_image_dir="sys_image",
                 sys_image_file_base=None,
                 env_prefix="JULIA_PROJECT_",
                 depot=None,
                 post_init_hook=None,
                 logging_level=None,
                 console_logging=False,
                 calljulia = "pyjulia",
                 ):

        self.name = name
        self.package_path = package_path
        self.julia_src_dir = os.path.join(self.package_path, "julia_src") # TODO get rid of this ??
        self.julia_path = None
        self.registry_url = registry_url
        self.sys_image_dir = sys_image_dir
        self.input_sys_image_dir = os.path.join(self.package_path, self.sys_image_dir)
        self.sys_image_file_base = sys_image_file_base # May be None
        self._env_vars = EnvVars(env_prefix)
        self._logging_level = logging_level
        self._console_logging = console_logging
        self.questions = ProjectQuestions(depot=depot, env_vars=self._env_vars)
        self._init_flags = {"initialized": False, "initializing": False, "disabled": False}
        self._post_init_hook = post_init_hook
        os.environ['PYCALL_JL_RUNTIME_PYTHON'] = shutil.which("python")
        self._find_julia = None # instance of FindJulia
        self.version_spec = version_spec
        self.strict_version = strict_version
        _validate_calljulia(calljulia)
        self._calljulia_name = calljulia
        self._use_sys_image = None


    def _in_inst_dir(self, rel_path):
        """Return absolute path from path relative to installation dir."""
        return os.path.join(self.package_path, rel_path)


    def _in_data_dir(self, rel_path):
        return os.path.join(self._project_data_path, rel_path)


    def _set_project_path(self):
        data_path = _get_project_data_path()
        self._project_data_path = os.path.join(data_path, self.name + "-" + self.julia_version)
        os.makedirs(self._project_data_path, exist_ok = True)
        os.environ["JULIA_PROJECT"] = self._project_data_path
        self.logger.info(f'os.environ["JULIA_PROJECT"] = {self._project_data_path}')
        self.manifest_toml = self._in_data_dir("Manifest.toml")
        self.data_project_toml = self._in_data_dir("Project.toml")
        self.data_julia_project_toml = self._in_data_dir("JuliaProject.toml")
        utils.update_copy(self.project_toml, self.data_project_toml)
        utils.update_copy(self.julia_project_toml, self.data_julia_project_toml)


    def disable_init(self):
        self._init_flags['disabled'] = True


    def enable_init(self):
        self._init_flags['disabled'] = False


    def ensure_init(self, calljulia=None, depot=None, use_sys_image=None):
        """
        Initializes the Julia project if it has not yet been initialized.

        Initialization includes searching for the Julia executable, optionally installing it,
        if not found. Resolving package requirements and downloading and installing them.
        Optionally compiling a system image.

        Args:
            calljulia : str The interface library to use, either "pyjuia" or "juliacall". Default "pyjulia"
            depot : bool If True, install a Julia depot (where packages are stored) in the data
                directory for this project. If False or None, use the default, common, Julia depot.
                Using a project-specific depot avoids the possibility that PyCall.jl will be rebuilt
                frequently if it is used in different projects.
            sys_image : bool If `False`, then don't load a custom system image, even if it is present.
        """
        if not self._init_flags['initialized'] and not self._init_flags['initializing'] and not self._init_flags['disabled']:
            if use_sys_image is not None:
                self._use_sys_image = use_sys_image
            _validate_calljulia(calljulia)
            if calljulia is not None:
                self._calljulia_name = calljulia
            self.questions.results['depot'] = depot
            try:
                self._init_flags['initializing'] = True
                self.init()
            finally:
                self._init_flags['initializing'] = False


    def _set_input_toml_paths(self):
        self.project_toml = self._in_inst_dir("Project.toml")
        self.julia_project_toml = self._in_inst_dir("JuliaProject.toml")


    def init(self):
        """Run all steps to initialize and load Julia and the Julia project."""
        self._setup_logging()  # level=self._logging_level, console=self._console_logging
        self.logger.info("")
        self.logger.info("JuliaProject.init()")
        self.questions.logger = self.logger
        self.questions.read_environment_variables()
        self._set_input_toml_paths()
        self.find_julia()
        if self.julia_path is None:
            raise FileNotFoundError("No julia executable found")
        self.logger.info(f"julia path: {self.julia_path}")
        self.julia_version = utils.julia_version_str(self.julia_path)
        self.logger.info("Julia version: %s.", self.julia_version)
        self._set_project_path()
        self.data_sys_image_dir = self._in_data_dir(self.sys_image_dir)
        if os.path.exists(self.input_sys_image_dir):
            self.logger.info(f"Copying/updating installed system image directory {self.data_sys_image_dir}")
            distutils.dir_util.copy_tree(
                self.input_sys_image_dir, self.data_sys_image_dir, update=1)
        else:
            self.logger.info(f"System image dir source not found at {self.input_sys_image_dir}")
        # if not os.path.exists(self.data_sys_image_dir):
        #     shutil.copytree(self.input_sys_image_dir, self.data_sys_image_dir)
        depot_path = self._in_data_dir("depot")
        if os.path.isdir(depot_path) and not self.questions.results['depot'] == False:
            self.questions.results['depot'] = True
            self.logger.info("Found existing Python-project specific Julia depot")
        self.julia_system_image = JuliaSystemImage(
            self.name,
            sys_image_dir=self.data_sys_image_dir,
            sys_image_file_base=self.sys_image_file_base,
            julia_version = self.julia_version,
            )
        calljulia_lib = _calljulia_lib(self._calljulia_name, self.logger)
        # Create instance of PyJulia or JuliaCall
        self.calljulia = calljulia_lib(
            self.julia_path,
            depot_dir=depot_path,
            data_path=self._project_data_path,
            julia_system_image=self.julia_system_image,
            use_sys_image=self._use_sys_image,
            questions=self.questions,
        )
        # Ugh. Don't really like doing it this way.
        self.julia_system_image.set_calljulia(self.calljulia)
        # Start the Julia runtime via libjulia
        self.calljulia.start_julia()
        self.julia = self.calljulia.julia # More convenient to get at this level
        self._load_julia_utils()
        # Either `julia` or `juliacall`: The Python/Julia interface module.
        self.julia = self.calljulia.julia
        # Redundant
#        self.logger.info(f'Is PyCall loaded: {self.julia.Main.is_loaded("PyCall")}')
        self.logger.info(f'PyCall version: {self.julia.Main.pycall_version()}')
#        self.logger.info(f'Is PythonCall loaded: {self.julia.Main.is_loaded("PythonCall")}')
        self.logger.info(f'PythonCall version: {self.julia.Main.pythoncall_version()}')
        self.activate_project()
        self.diagnostics_after_init()
        self.check_and_install_julia_packages()
        if self._post_init_hook is not None:
            self._post_init_hook()
        self._init_flags['initialized'] = True


    def _load_julia_utils(self):
        srcdir = os.path.dirname(os.path.realpath(__file__))
        utilf = os.path.join(srcdir, "utils.jl")
        self.calljulia.seval(f'include("{utilf}")')


    def _setup_logging(self):
        self.logger = logging.getLogger('julia_project')
        if self._logging_level is None:
             # fh = logging.NullHandler() # probably don't need this
            return None

        result = self._env_vars.getenv("LOG_PATH")
        if result:
            self.log_file_path = result
        else:
            self.log_file_path = self.name + '.log'
        fh = logging.FileHandler(self.log_file_path)
        logging_level = self._logging_level
        self.logger.setLevel(logging_level)
        fh.setLevel(logging_level)
#        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        if self._console_logging:
            ch = logging.StreamHandler()
            ch.setLevel(self._logging_level)
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)


    def find_julia(self):
        def other_questions(): # if one question asked, ask all questions at once
            self.questions.ask_question('compile')
            self.questions.ask_question('depot')

        found_path = find_julia.find_or_install(
            env_var = self._env_vars.envname("JULIA_PATH"),
            answer_yes = (self.questions.results['install'] == True),
            version_spec = (self.version_spec if self.version_spec else "^1"),
            post_question_hook = other_questions,
            strict=(self.strict_version if self.strict_version else True)
            )
        if not found_path:
            self.logger.error("No julia executable found or installed.")
            raise FileNotFoundError("No julia executable found or installed.")
        self.julia_path = found_path
        self.questions.results['install'] = False # prevent from being asked again


    # If we use juliacall.using, the module is not imported into Main.
    def simple_import(self, module : str):
        """
        import the julia module `module` and return the python-wrapped module.
        This works with both `pyjulia` and `juliacall`.

        `Example = self.simple_import("Example")`
        """
        return self.calljulia.simple_import(module)


    def activate_project(self):
        if not (os.path.isfile(self.data_project_toml) or os.path.isfile(self.data_julia_project_toml)):
            msg = f"Neither \"{self.project_toml}\" nor \"{self.julia_project_toml}\" exist."
            logger.error(msg)
            raise FileNotFoundError(msg)
        Pkg = self.simple_import("Pkg")
        # Activate the Julia project
        Pkg.activate(self._project_data_path)
        self.logger.info("Probed Project.toml path: %s", Pkg.project().path)


    def diagnostics_after_init(self):
        # TODO replace several calls for info below using the JuliaInfo object
        # Import these to reexport
        # Main = self.calljulia.calljulia.Main
        # calljulia = self.calljulia.calljulia
        # self.logger.info("Julia version %s", Main.string(Main.VERSION))

        Main = self.julia.Main
        self.logger.info("Julia version %s", Main.string(Main.VERSION))

        self.loaded_sys_image_path = self.calljulia.seval('unsafe_string(Base.JLOptions().image_file)')
        self.logger.info("Probed system image path %s", self.loaded_sys_image_path)

        julia_cmd = self.julia.Base.julia_cmd()
        self.logger.info("Probed julia command: %s", julia_cmd)


    def check_and_install_julia_packages(self):
        logger = self.logger
#        Pkg = self.julia.Pkg
        Pkg = self.simple_import("Pkg")
        ### Instantiate Julia project, i.e. download packages, etc.
        # Assume that if built system image exists, then Julia packages are installed.
        if os.path.isfile(self.manifest_toml):
            logger.info("Julia project Manifest.toml found.")
        else:
            print("No Manifest.toml found. Assuming Julia packages not installed, installing...")
            logger.info("Julia packages not installed or found.")
            self.questions.results['install'] = False
            self.questions.results['depot'] = False # Too late to use depot
            self.questions.ask_questions()
            if self.registry_url:
                logger.info(f"Installing registry from {self.registry_url}.")
                Pkg.Registry.add(Pkg.RegistrySpec(url = self.registry_url))
            else:
                logger.info(f"No registry installation requested.")
            logger.info("Pkg.resolve()")
            Pkg.resolve()
            logger.info("Pkg.instantiate()")
            Pkg.instantiate()
        if self.questions.results['compile']:
            self.compile()


    def compile(self):
        """
        Compile a system image for the dependent Julia packages in the subdirectory `./sys_image/`. This
        system image will be loaded the next time you import the Python module.
        """
        self.julia_system_image.compile()


    def clean(self):
        """
        Delete some files created when installing Julia packages. These are Manifest.toml files
        and a compiled system image.
        """
        for _file in [self.manifest_toml, self._in_inst_dir(self.name + '.log')]:
            utils.maybe_remove(_file, self.logger)
        self.julia_system_image.clean()


    def update(self):
        """
        Update the Julia packages that the Python module depends on.

        First, remove possible stale Manifest.toml files and the compiled system image.
        Then update Julia packages and rebuild Manifest.toml file.
        This may help to work around some errors, for instance when compiling.
        """
        self.clean()
        Pkg = self.simple_import("Pkg")
        self.activate_project()
        self.logger.info("Updating Julia packages")
        Pkg.update()
        Pkg.resolve()
        Pkg.instantiate()
