# julia_project

This package provides the class `JuliaProject` for managing a
[Julia project](https://pkgdocs.julialang.org/v1.7/environments/) that lives inside
a Python package and is accessed via [pyjulia](https://github.com/JuliaPy/pyjulia) (the Python module "julia").

`julia_project` is meant to provide some automation, hand holding, and error checking.
The intended use is as follows. You want to create a Python package that calls some Julia packages
via pyjulia. You create a directory representing the top level of a Python package, with
a `setup.py` and `requirements.txt` and the Python code. You create a `Project.toml` file
in the top level describing the Julia packages for the project. You might do
`source ./venv`; `pip install -r requirements.txt`; `pip install -e .`.

### Using julia_project

Then `import mymodule` will do the following

* Offer to download and install Julia if it is not found.
* Check that the `julia` package is installed. I.e. check that `PyCall` is installed and built, etc.
* Optionally download and install a Julia registry.
* Look for the Julia executable in various places
* Optionally load a custom Julia system image.
* Instantiate the Julia project.
* Provide a Python function that compiles a system image that will be found the next
  time `mymodule` is imported. The scripts and environment for compilation are found in
  a specified subdirectory of the Python project.
* Write info about all of the above to a log file

Here is a brief example

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

#### Compiling

Make a folder `./sys_image/` in the top level of your Python package. Add `Project.toml` file.
This typically contains the same dependencies as the top-level `Project.toml`. Perhaps a few
more or less.
Add a script `compile_julia_project.jl`. Typical contents are
```julia
using PackageCompiler

packages = [:PyCall, :APackage, :AnotherPackge]

create_sysimage(packages; sysimage_path="sys_julia_project.so",
                precompile_execution_file="compile_exercise_script.jl")
```
The system image name must be "sys_julia_project.so".
The precompilation can be done however you like, or not at all. The name "compile_exercise_script.jl"
is only an example.
After compiling, the system image file will be renamed from
`sys_julia_project.so`, to a name that includes the version of the julia exectuable
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
* `sys_image_file_base` -- the base name of the Julia system image. The system image file will be `sys_image_file_base + "-" + a_julia_version_string + ".so"`.
* `logging_level` -- if `None`, then `logging.INFO` will be used.
* `console_logging` -- if `True`, then the log messages are echoed to the console.

#### Location of julia executable

`JuliaProject` will look in the package top level for the installation `./julia/` and
executable `./julia/bin/julia`. This can be a symlink to an installation. If this
fails, then  looks in your `PATH`. If this fails, `JuliaProject` will download
and install Julia after prompting you.

#### Warning

This package is very new and is neither well tested nor documented.
