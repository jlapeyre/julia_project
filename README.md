# julia_project

This package provides the class `JuliaProject` for managing a
[Julia project](https://pkgdocs.julialang.org/v1.7/environments/) that lives inside
a Python package and is accessed via [pyjulia](https://github.com/JuliaPy/pyjulia) (the Python module "julia").

`julia_project` is meant to provide some automation, hand holding, and error checking.
The intended use is as follows.
You want to create a Python package that calls some Julia packages via pyjulia.
You create a directory representing the top level of a Python package,
with a `setup.py` and `requirements.txt` and the Python code
in a directory `mymodule`.
You create a file `./mymodule/Project.toml` describing the Julia packages for the project.
In a Python source file in `./mymodule/`, you create an instance of `julia_project.JuliaProject`
that manages the Julia project.

### What julia_project does

Then `import mymodule` will do the following

* Look for the Julia executable in various places
* Offer to download and install Julia if it is not found.
* Optionally create a private Julia depot for `mymodule` to avoid possible issues with
  `PyCall` in different Python environments.
* Check that the `julia` package is installed.
  I.e. check that `PyCall` is installed and built, etc.
* Optionally download and install a Julia registry.
* Optionally load a custom Julia system image.
* Instantiate the Julia project.
* Provide a Python function that compiles a system image that will be found the next
  time `mymodule` is imported. The scripts and environment for compilation are found in
  a specified subdirectory of the Python project.
* Write info about all of the above to a log file

### Using julia_project to create a project

Here is a brief example. See [the example directory](./examples/myjuliamod) for a complete example.

* Include the following in a file loaded in `./mymodule/`, that is, the directory found by `import mymodule`.
```python
import os
mymodule_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# This just creates an object, but does none of the steps above.
julia_project = JuliaProject(
    name="mymodule",
    package_path=mymodule_path,
    registry_url = "git@github.com:myuser/MyModuleRegistry.git",
    logging_level = logging.INFO # or WARN, or ERROR
    )

julia_project.run() # This exectutes all the management features listed above

def compile_mymodule():
    julia_project.compile_julia_project()
```

* Create `./mymodule/Project.toml` for the Julia project.

#### Compiling

Make a folder `./mymodule/sys_image/`. Add a file `./mymodule/sys_image/Project.toml`.
This typically contains the same dependencies as the top-level `Project.toml`. Perhaps a few
more or less.
Add a script `./mymodule/sys_image/compile_julia_project.jl`. Typical contents are
```julia
using PackageCompiler
using Libdl: Libdl

packages = [:PyCall, :APackage, :AnotherPackage]

sysimage_path = joinpath(@__DIR__, "sys_julia_project." * Libdl.dlext)

create_sysimage(packages; sysimage_path=sysimage_path,
                precompile_execution_file=joinpath(@__DIR__, "compile_exercise_script.jl"))
```
* The system image name must be "sys_julia_project.dylib", "sys_julia_project.dll", or , "sys_julia_project.so".
  The example above will choose the correct suffix.
* `precompile_execution_file` can be whatever you like, or omitted.
*  After compiling, the system image file will be renamed from
   `sys_julia_project.so` (or `dll`, or `dylib`), to a name that includes the version of the julia exectuable
   that built it. The latter is the file name that will be searched for the next time
   you import `mymodule`.

#### Arguments to JuliaProject

```python
name,
package_path,
registry_url=None,
preferred_julia_versions = ['1.7', '1.6', 'latest'],
sys_image_dir="sys_image",
sys_image_file_base=None,
env_prefix="JULIA_PROJECT_",
depot=False,
logging_level=None,
console_logging=False
```

* `name` -- the name of the module, e.g. "mymodule". Used only in the logger and the name of the system image.
* `package_path` -- path to the top level of `mymodule`.
* `registry_url` -- if `None` then no registry will be installed (other than
   the General registry, if not already installed.)
* `preferred_julia_versions` -- a list of preferred julia versions to search for, in order, in the [`jill.py`](https://github.com/johnnychen94/jill.py)
   installation directory. If no preferred version is found, but another jill-installed version is found, it will be used.
* `sys_image_dir` -- the directory in which scripts for compiling a system image, and the system images, are found. This is
   relative to the top level of `mymodule`.
* `sys_image_file_base` -- the base name of the Julia system image. The system image file will be `sys_image_file_base + "-" + a_julia_version_string + ".ext"`,
    where `ext` is the dynamic lib extension for your platform.
* `env_prefix` -- Prefix for environment variables to set project options
* `depot` -- If `True`, then a private depot in the `mymodule` installation directory will be used.
* `logging_level` -- if `None` then no logging will be done. if `logging.INFO`, then detailed info will be logged
* `console_logging` -- if `True`, then the log messages are echoed to the console.

#### Environment variables

* In the following, the prefix `JULIA_PROJECT_` may be changed with the argument `env_prefix` described above. This allows you
  to set environment variables specific to each project that do not interfere.

* `JULIA_PROJECT_JULIA_PATH` may be set to the path to a Julia executable. This will override other possible paths to a Julia executable.

* `JULIA_PROJECT_INSTALL_JULIA` may be set to `y` or `n`. If set, then no interactive query is done to install Julia via `jill.py`.
   Instead the value `y` or `n` is used.

* `JULIA_PROJECT_COMPILE` may be set to `y` or `n`. If set, then no interactive query is done to compile a system image
  after installing packages. Instead the value `y` or `n` is used.

* `JULIA_PROJECT_LOG_PATH` may be set to the path to the log file.

* `JULIA_PROJECT_DEPOT` -- If set, then a private Julia depot will be created in a directory `depot` under the
  `mymodule` installation directory. The depot contains all downloaded registries, packages, precompiled packages, and
   many other data related to your julia installation.

#### Location of julia executable

`JuliaProject` will look in the following locations, in order

* The environment variabel `JULIA_PROJECT_JULIA_PATH`. With `JULIA_PROJECT_` optionally replaced by `env_prefix` described above.

* In the package top level for the installation `./julia/`

* A julia installation from `jill.py`, with preferred versions specified as above.

* Your system or shell PATH variable.

* A fresh installation of julia via `jill.py` after asking if you want to download and install.

#### Building `PyCall`

Installing and using `PyCall` is sometimes easy and sometimes confusing. The latter happens if
you try to use `PyCall` with different Python environments. The whole issue can be avoided
by using a private Julia "depot". You do this by passing the argument `depot=True` when initializing your `JuliaProject` instance.
Alternatively, the user can set the environment variable `JULIA_PROJECT_DEPOT` described above.
In this case, registries, packges, cached precompiled files, and many other things are stored
in the installation directory of the project, e.g. `mymodule`.

This is a heavy solution because it involves duplicating many files if you use Julia for other projects, with Python or not.
But, it does not require that the end user understand anything about the status of your Julia installation, libpython, `PyCall.jl`,
etc.

Using a private depot should also allow `julia_project` to work with conda environments.

#### Testing

You can run tests like this:

```shell
pytest -p julia.pytestplugin  julia_project/tests
```

Tests that don't require a Julia installation may be run like this:

```shell
pytest --no-julia  -p julia.pytestplugin  julia_project/tests
```

#### Warning

This package is very new and is neither well tested nor documented.
