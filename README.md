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

julia_project = JuliaProject(
    name="mymodule",
    package_path=mymodule_path,
    registry_url = "git@github.com:myuser/MyModuleRegistry.git",
    logging_level = logging.INFO # or WARN, or ERROR
    )

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

create_sysimage(packages; sysimage_path="sys_mymodule.so",
                precompile_execution_file="compile_exercise_script.jl")
```
The system image file name `sys_mymodule.so` will be expected by `JuliaProject`.
You can override this with the argument `sys_image_file=a_different_image.so` to
to `JuliaProject`.

#### Arguments to JuliaProject

```python
package_path,
registry_url=None,
sys_image_dir="sys_image",
sys_image_file=None,
logging_level=None,
console_logging=False
```

If `logging_level` is `None`, then `logging.INFO` will be used.

If `registry_url` is `None`, then no registry will be installed (other than
the General registry by `pyjulia`)

If `console_logging` is `True` the log messages are echoed to the console.

#### Location of julia executable

`JuliaProject` will look in the package top level for the installation `./julia/` and
executable `./julia/bin/julia`. This can be a symlink to an installation. If this
fails, then `JuliaProject` looks in your `PATH`.

#### Warning

This package is very new and is neither well tested nor documented.
