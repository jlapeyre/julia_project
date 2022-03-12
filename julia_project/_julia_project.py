import logging
import os
import sys
import shutil
import importlib
import distutils.dir_util
import find_julia
from .julia_system_image import JuliaSystemImage
from . import utils
from . import install

from .environment import EnvVars
from .questions import ProjectQuestions


# The depot referred to here is the default depot, i.e. ~/.julia
# This true even if the user requests a "private" depo.
# In the latter case, we will have a depot within the default depot.
def _get_parent_project_path():
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
    registries : dict, optional
        A dict whose keys are registry names and values are urls of Julia registries.
        These registries will be installed automatically.
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
                 registries=None,
                 version_spec=None,
                 strict_version=False,
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
        self.registries = registries
        self.rel_sys_image_dir = sys_image_dir
        self.package_sys_image_dir = os.path.join(self.package_path, self.rel_sys_image_dir)
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
        if calljulia is None:
            calljulia = "pyjulia"
        _validate_calljulia(calljulia)
        self._calljulia_name = calljulia
        self._use_sys_image = None


    def _in_package_dir(self, rel_path):
        """Return absolute path from path relative to installation dir."""
        return os.path.join(self.package_path, rel_path)


    def _in_project_dir(self, rel_path):
        return os.path.join(self.project_path, rel_path)


    def _set_project_path(self):
        self.project_path = os.path.join(_get_parent_project_path(), self.name + "-" + self.julia_version)
        os.makedirs(self.project_path, exist_ok = True)
        os.environ["JULIA_PROJECT"] = self.project_path
        self.logger.info(f'os.environ["JULIA_PROJECT"] = {self.project_path}')
        self.manifest_toml = self._in_project_dir("Manifest.toml")

        self.project_toml = self._in_project_dir("Project.toml")
        utils.update_copy(self.package_project_toml, self.project_toml)

        utils.update_copy(self._package_julia_project_toml, self._in_project_dir("JuliaProject.toml"))
        if not utils.has_project_toml(self.project_path):
            msg = utils.no_project_toml_message(self.project_path)
            logger.error(msg)
            raise FileNotFoundError(msg)


    def disable_init(self):
        self._init_flags['disabled'] = True


    def enable_init(self):
        self._init_flags['disabled'] = False


    def ensure_init(self, calljulia=None, depot=None, use_sys_image=None,
                    strict_version=None):
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
            if strict_version is not None:
                self.strict_version = strict_version
            self.questions.results['depot'] = depot
            try:
                self._init_flags['initializing'] = True
                self.init()
            finally:
                self._init_flags['initializing'] = False
        elif self._init_flags['initialized'] and calljulia is not None:
            incompat_reinit = ((self.julia.__name__ == 'julia' and calljulia != 'pyjulia')
                               or
                               (self.julia.__name__ == 'juliacall' and calljulia != 'juliacall')
                               )
            if incompat_reinit:
                raise ValueError(f"Can't change library. Already initialzed with '{self.julia.__name__}'")


    def _set_package_toml_paths(self):
        self.package_project_toml = self._in_package_dir("Project.toml")
        self._package_julia_project_toml = self._in_package_dir("JuliaProject.toml")


    def init(self):
        """Run all steps to initialize and load Julia and the Julia project."""
        self._setup_logging()  # level=self._logging_level, console=self._console_logging
        self.logger.info("")
        self.logger.info("JuliaProject.init()")
        self.questions.logger = self.logger
        self.questions.read_environment_variables()
        self._set_package_toml_paths()
        self.find_julia()
        if self.julia_path is None:
            raise FileNotFoundError("No julia executable found")
        self.logger.info(f"julia path: {self.julia_path}")
        self.julia_version = utils.julia_version_str(self.julia_path)
        self.logger.info("Julia version: %s.", self.julia_version)
        self._set_project_path()
        if not utils.has_manifest_toml(self.project_path):
            self._no_manifest_toml_at_start = True  # proxy for first init after installation
        else:
            self._no_manifest_toml_at_start = False
        self.sys_image_dir = self._in_project_dir(self.rel_sys_image_dir)
        if os.path.exists(self.package_sys_image_dir):
            self.logger.info(f"Copying/updating installed system image directory {self.sys_image_dir}")
            distutils.dir_util.copy_tree(
                self.package_sys_image_dir, self.sys_image_dir, update=1)
        else:
            self.logger.info(f"System image dir source not found at {self.package_sys_image_dir}")
        # if not os.path.exists(self.sys_image_dir):
        #     shutil.copytree(self.package_sys_image_dir, self.sys_image_dir)
        possible_depot_path = self._in_project_dir("depot")
        if os.path.isdir(possible_depot_path) and not self.questions.results['depot'] == False:
            self.questions.results['depot'] = True
            self.logger.info("Found existing Python-project specific Julia depot")
        self.julia_system_image = JuliaSystemImage(
            self.name,
            sys_image_dir=self.sys_image_dir,
            sys_image_file_base=self.sys_image_file_base,
            julia_version = self.julia_version,
            )
        calljulia_lib = _calljulia_lib(self._calljulia_name, self.logger)

        if self.questions.results['depot'] == True:
            depot_path = possible_depot_path
        else:
            depot_path = None

        _need_resolve = install.need_resolve(self.project_path, depot_path)
        if _need_resolve:
            self.questions.ask_questions()
            if self.questions.results['depot'] == True: # May have changed depot
                depot_path = possible_depot_path
            else:
                depot_path = None


        def answer_rebuild_callback():
            self.questions.results['depot'] = False # only one or the other
            self.questions.ask_questions()

        def answer_depot_callback():
            self.questions.results['depot'] = True
            self.questions.ask_questions()

        # ensure that packages, registries, etc. are installed

        if self._calljulia_name == "pyjulia":
            packages_to_add = ["PyCall"]
        elif self._calljulia_name == "juliacall":
            packages_to_add = ["PythonCall"]
        else:
            packages_to_add = None

        if self._calljulia_name != "pyjulia":
            install.ensure_project_ready(
                project_path=self.project_path,
                julia_exe=self.julia_path,
                depot_path=depot_path,
                registries=self.registries,
                packages_to_add=packages_to_add,
                clog=True,
                preinstall_callback=None # we now do this above self.questions.ask_questions,
            )
        else:
            install.ensure_project_ready_fix_pycall(
                project_path=self.project_path,
                julia_exe=self.julia_path,
                depot_path=depot_path,
                possible_depot_path=possible_depot_path,
                registries=self.registries,
                packages_to_add=packages_to_add,
                clog=True,
                preinstall_callback=self.questions.ask_questions,
                question_callback=None, # self.questions.deal_with_incompatibility,
                answer_rebuild_callback=answer_rebuild_callback,
                answer_depot_callback=answer_depot_callback
            )

        if self.questions.results['depot'] == True:
            os.environ["JULIA_DEPOT_PATH"] = possible_depot_path
            self.logger.info(f"Using private depot '{possible_depot_path}'")
        else:
            self.logger.info("Using default depot.")

        self.calljulia = calljulia_lib(
            self.julia_path,
            project_path=self.project_path,
            julia_system_image=self.julia_system_image,
            use_sys_image=self._use_sys_image,
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
        self.diagnostics_after_init()
        if self.questions.results['compile']:
            self.compile()
        if self._post_init_hook is not None:
            self._post_init_hook()
        self._init_flags['initialized'] = True


    # For testing. Build PyCall with "wrong" libpython
    def _build_pycall_conda(self):
        install.rebuild_pycall(
            self.project_path,
            python_exe="conda",
            julia_exe=self.julia_path,
            clog=True,
        )


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
            version_spec = (self.version_spec if self.version_spec is not None else "^1"),
            post_question_hook = other_questions,
            strict=(self.strict_version if self.strict_version is not None else True)
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
        self.ensure_init()
        return self.calljulia.simple_import(module)


    def activate_project(self):
        if not utils.has_project_toml(self.project_path):
            msg = utils.no_project_toml_message(self.project_path)
            logger.error(msg)
            raise FileNotFoundError(msg)
        Pkg = self.simple_import("Pkg")
        # Activate the Julia project
        Pkg.activate(self.project_path)
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


    def compile(self):
        """
        Compile a system image for the dependent Julia packages in the subdirectory `./sys_image/`. This
        system image will be loaded the next time you import the Python module.
        """
        self.ensure_init()
        self.julia_system_image.compile()


    def clean(self):
        """
        Delete some files created when installing Julia packages. These are Manifest.toml files
        and a compiled system image.
        """
        self.ensure_init()
        for _file in [self._in_project_dir("Manifest.toml"), self._in_project_dir("JuliaManifest.toml"),
                      self._in_package_dir(self.name + '.log')]:
            utils.maybe_remove(_file)
        self.julia_system_image.clean()


    def clean_all(self):
        project_dir = os.path.join(_get_parent_project_path(), self.name + "-" + self.julia_version)
        if project_dir.find("julia_project") < 0:
            raise ValueError(f"Expecting project path to contain string 'julia_project'")
        if os.path.isdir(project_dir):
            self.logger.info("Removing project directory {project_dir}")
            shutil.rmtree(project_dir)


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
