#import julia
import os
from . import utils

import logging
LOGGER = logging.getLogger('julia_project.system_image') # shorten this?


class JuliaSystemImage:
    """
    This class manages compilation of a Julia system image.
    """
    def __init__(self,
                 name,
                 sys_image_dir, # Absolute, not relative path!
                 julia_version = None,
                 sys_image_file_base=None,
                 ):
        self.sys_image_dir = sys_image_dir
        if sys_image_file_base is None:
            sys_image_file_base = "sys_" + name
        self.sys_image_file_base = sys_image_file_base
        self.julia_version = julia_version
        self.set_toml_paths()
        self.set_sys_image_paths()


    # This must be set after __init__, because calljulia is instantiated wit data from self
    def set_calljulia(self, calljulia):
        self.calljulia = calljulia


    def _in_sys_image_dir(self, rel_path):
        """Return absolute path from path relative to system image build dir."""
        return os.path.join(self.sys_image_dir, rel_path)


    def get_sys_image_file_name(self):
        """Return the filename of the system image written upon compilation. This
        file will be renamed after compilation.
        """
        # self.version_raw = self.julia_info.version_raw # Make this a dict, or use JuliaInfo
        return self.sys_image_file_base + "-" + self.julia_version + utils.SHLIB_SUFFIX


    def set_sys_image_paths(self):
        self.sys_image_path = self._in_sys_image_dir(self.get_sys_image_file_name())
        self.compiled_system_image = self._in_sys_image_dir("sys_julia_project" + utils.SHLIB_SUFFIX)


    def set_toml_paths(self):
        self.sys_image_project_toml = self._in_sys_image_dir("Project.toml")
        self.sys_image_julia_project_toml = self._in_sys_image_dir("JuliaProject.toml")
        self.sys_image_manifest_toml = self._in_sys_image_dir("Manifest.toml")


    def clean(self):
        """
        Delete some files created when installing Julia packages. These are Manifest.toml files
        and a compiled system image.
        """
        for _file in [self.sys_image_manifest_toml, self.sys_image_path]:
            utils.maybe_remove(_file, LOGGER)


    def compile(self):
        """
        Compile a system image for the dependent Julia packages in the subdirectory `./sys_image/`. This
        system image will be loaded the next time you import the Python module.
        """
        Main = self.calljulia.julia.Main
        Pkg = self.calljulia.julia.Pkg
        current_path = Main.pwd()
        current_project = Pkg.project().path
        try:
            self._compile()
        except:
            print("Exception when compiling")
            raise
        finally:
            Main.cd(current_path)
            Pkg.activate(current_project)


    def _compile(self):
        """
        Compile a Julia system image with all requirements for the julia project.
        """
        Main = self.calljulia.julia.Main
        Pkg = self.calljulia.julia.Pkg
        if not os.path.isdir(self._in_sys_image_dir("")):
            msg = f"Can't find directory for compiling system image: {self._in_sys_image_dir('')}"
            raise FileNotFoundError(msg)

        # self.set_sys_image_paths() # already done
        # TODO: Fix this
        # if self.loaded_sys_image_path == self.sys_image_path:
        #     for msg in ("WARNING: Compiling system image while compiled system image is loaded.",
        #                 f"Consider deleting  {self.sys_image_path} and restarting python."):
        #         print(msg)
        #         LOGGER.warn(msg)
        if not (os.path.isfile(self.sys_image_project_toml) or os.path.isfile(self.sys_image_julia_project_toml)):
            msg = f"Neither \"{self.sys_image_project_toml}\" nor \"{self.sys_iamge_julia_project_toml}\" exist."
            LOGGER.error(msg)
            raise FileNotFoundError(msg)
        utils.maybe_remove(self.sys_image_manifest_toml, LOGGER)
        Main.eval('ENV["PYCALL_JL_RUNTIME_PYTHON"] = Sys.which("python")')
        Pkg.activate(self._in_sys_image_dir(""))
        pycall_loaded = Main.is_loaded("PyCall")
        pythoncall_loaded = Main.is_loaded("PythonCall")
        deps = Main.parse_project()["deps"].keys()
        pycall_in_deps = "PyCall" in deps
        pythoncall_in_deps = "PythonCall" in deps
        if pycall_loaded:
            if not pycall_in_deps:
                Pkg.add("PyCall")
        else:
            if pycall_in_deps:
                Pkg.rm("PyCall")
        if pythoncall_loaded:
            if not pythoncall_in_deps:
                Pkg.add("PythonCall")
        else:
            if pythoncall_in_deps:
                Pkg.rm("PythonCall")
        LOGGER.info("Compiling: probed Project.toml path: %s", Pkg.project().path)
        Main.cd(self._in_sys_image_dir(""))
        try:
            Pkg.resolve()
        except: # Assume that failure of resolve is because update() has not been called
            msg = "Pkg.resolve() failed. Updating packages."
            print(msg)
            LOGGER.info(msg)
            Pkg.update()
            Pkg.resolve()
        Pkg.instantiate()
        _bool = {True: "true", False: "false"}
        cscript = f'''
        using PackageCompiler
        using Libdl: Libdl
        ENV["PYCALL_JL_RUNTIME_PYTHON"] = Sys.which("python")
        ENV["PYTHON"] = Sys.which("python")
        include("packages.jl")
        if {_bool[pycall_loaded]}
           push!(packages, :PyCall)
        end
        if {_bool[pythoncall_loaded]}
           push!(packages, :PythonCall)
        end
        sysimage_path = joinpath(@__DIR__, "sys_julia_project." * Libdl.dlext)

        create_sysimage(packages; sysimage_path=sysimage_path,
             precompile_execution_file=joinpath(@__DIR__, "compile_exercise_script.jl"))
        '''
        LOGGER.info(f"Running compile script.")
        self.calljulia.seval_all(cscript)
#        compile_script = "compile_julia_project.jl"
#        Main.include(compile_script)
        if os.path.isfile(self.compiled_system_image):
            LOGGER.info("Compiled image found: %s.", self.compiled_system_image)
            os.rename(self.compiled_system_image, self.sys_image_path)
            LOGGER.info("Renamed compiled image to: %s.", self.sys_image_path)
            if not os.path.isfile(self.sys_image_path):
                LOGGER.error("Failed renamed compiled image to: %s.", self.sys_image_path)
                raise FileNotFoundError(self.compiled_system_image)
        else:
            raise FileNotFoundError(self.compiled_system_image)
