#import julia
import os
from . import utils
from . import install

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
        # self.sys_image_path is the path for the system image written upon compilation. This
        # file will be renamed after compilation.
        self.sys_image_path = self._in_sys_image_dir(
            self.sys_image_file_base + "-" + self.julia_version + utils.SHLIB_SUFFIX
        )
        self.compiled_system_image = self._in_sys_image_dir("sys_julia_project" + utils.SHLIB_SUFFIX)


    # This must be set after __init__, because calljulia is instantiated with data from self
    def set_calljulia(self, calljulia):
        self.calljulia = calljulia


    def _in_sys_image_dir(self, rel_path):
        """Return absolute path from path relative to system image build dir."""
        return os.path.join(self.sys_image_dir, rel_path)


    def clean(self):
        """
        Delete some files created when installing Julia packages. These are Manifest.toml files
        and a compiled system image.
        """
        for _file in [self._in_sys_image_dir("Manifest.toml"), self._in_sys_image_dir("JuliaManifest.toml"),
                      self.sys_image_path]:
            utils.maybe_remove(_file)


    def compile(self):
        """
        Compile a system image for the dependent Julia packages in the subdirectory `./sys_image/`. This
        system image will be loaded the next time you import the Python module.
        """
        Main = self.calljulia.julia.Main
        Pkg = self.calljulia.julia.Pkg
        current_path = Main.pwd()
        current_project = Pkg.project().path
        old_julia_project = os.getenv("JULIA_PROJECT")
        try:
            self._compile()
        except:
            print("Exception when compiling system image.")
            raise
        finally:
            install.reset_env_var("JULIA_PROJECT", old_julia_project)
            Main.cd(current_path)
            Pkg.activate(current_project)


    def _compile(self):
        """
        Compile a Julia system image with all requirements for the julia project.
        """
        Main = self.calljulia.julia.Main
        Pkg = self.calljulia.julia.Pkg
        if not os.path.isdir(self.sys_image_dir):
            msg = f"Can't find directory for compiling system image: {self.sys_image_dir}"
            raise FileNotFoundError(msg)

        if not utils.has_project_toml(self.sys_image_dir):
            msg = utils.no_project_toml_message(self.sys_image_dir)
            LOGGER.error(msg)
            raise FileNotFoundError(msg)
        for _file in [self._in_sys_image_dir("Manifest.toml"), self._in_sys_image_dir("JuliaManifest.toml")]:
            utils.maybe_remove(_file)
        Main.eval('ENV["PYCALL_JL_RUNTIME_PYTHON"] = Sys.which("python")')
        Pkg.activate(self.sys_image_dir)
        os.environ["JULIA_PROJECT"] = self.sys_image_dir
        pycall_loaded = Main.is_loaded("PyCall")
        pythoncall_loaded = Main.is_loaded("PythonCall")
        deps = install.parse_project(self.sys_image_dir)["deps"].keys() # This is faster
#        deps = Main.parse_project()["deps"].keys()
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
        Main.cd(self.sys_image_dir)
        try:
            Pkg.resolve()
        except: # Assume that failure of resolve is because update() has not been called
            msg = "Pkg.resolve() failed. Updating packages."
            LOGGER.info(msg)
            Pkg.update()
            Pkg.resolve()
        Pkg.instantiate()

        # Following will also perform compilation, with more granual error messages
        # But, it is harder to read.
        # cj = self.calljulia
        # PackageCompiler = cj.simple_import("PackageCompiler")
        # Libdl = cj.simple_import("Libdl")
        # cj.seval_all("""
        #    ENV["PYCALL_JL_RUNTIME_PYTHON"] = Sys.which("python")
        #    ENV["PYTHON"] = Sys.which("python")
        # """)
        # Main.include("packages.jl")
        # if pycall_loaded:
        #     LOGGER.info("push!(packages, :PyCall)")
        #     cj.seval_all("push!(packages, :PyCall)")
        # if pythoncall_loaded:
        #     LOGGER.info("push!(packages, :PythonCall)")
        #     cj.seval_all("push!(packages, :PythonCall)")
        # cj.seval('sysimage_path = joinpath(@__DIR__, "sys_julia_project." * Libdl.dlext)')
        # cj.seval_all("""PackageCompiler.create_sysimage(packages; sysimage_path=sysimage_path,
        # precompile_execution_file=joinpath(@__DIR__, "compile_exercise_script.jl"))""")

        packages_file = os.path.join(self._in_sys_image_dir("packages.jl"))
        if not os.path.exists(packages_file):
            raise FileNotFoundError(f'{packages_file} does not exist')

        _bool = {True: "true", False: "false"}

        cscript = f'''
        import PackageCompiler
        using Libdl: Libdl
        let
          ENV["PYCALL_JL_RUNTIME_PYTHON"] = Sys.which("python")
          ENV["PYTHON"] = Sys.which("python")
          packages = include("packages.jl")
          if {_bool[pycall_loaded]}
             push!(packages, :PyCall)
          end
          if {_bool[pythoncall_loaded]}
             push!(packages, :PythonCall)
          end
          sysimage_path = joinpath(@__DIR__, "sys_julia_project." * Libdl.dlext)

          if isfile("compile_exercise_script.jl")
            PackageCompiler.create_sysimage(packages; sysimage_path=sysimage_path,
                precompile_execution_file=joinpath(@__DIR__, "compile_exercise_script.jl"),
                incremental=true,
                project=joinpath(@__DIR__, "."))
          else
            PackageCompiler.create_sysimage(packages; sysimage_path=sysimage_path,
                incremental=true,
                project=joinpath(@__DIR__, "."))
          end
        end
        '''
        LOGGER.info(f"Running compile script.")
        self.calljulia.seval_all(cscript)
        if os.path.isfile(self.compiled_system_image):
            LOGGER.info("Compiled image found: %s.", self.compiled_system_image)
            os.rename(self.compiled_system_image, self.sys_image_path)
            LOGGER.info("Renamed compiled image to: %s.", self.sys_image_path)
            if not os.path.isfile(self.sys_image_path):
                LOGGER.error("Failed renamed compiled image to: %s.", self.sys_image_path)
                raise FileNotFoundError(self.compiled_system_image)
        else:
            raise FileNotFoundError(self.compiled_system_image)
