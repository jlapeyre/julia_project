# julia_project

This package provides the class `JuliaProject` for managing a
[Julia project](https://pkgdocs.julialang.org/v1.7/environments/) that lives inside
a Python package.
`julia_project` supports two libraries for calling Julia from Python,
[pyjulia](https://github.com/JuliaPy/pyjulia) (the Python module "julia")
and
[juliacall](https://github.com/cjdoris/PythonCall.jl).

`julia_project` is in pypi; it can be installed via `pip install julia_project`. It is meant to be used as a library
in other projects.

`julia_project` is meant to provide some automation, hand holding, and error checking in managing
a Julia dependency in a Python package.

## For the user of a package that uses `julia_project`

Suppose the Python module `mymodule` uses `julia_project` to manage its Julia dependency.
The user of `mymodule` can do the following to import mymodule and install and initialize
the Julia project that `mymodule` depends on.

```python
import mymodule
mymodule.project.ensure_init()
```

See the docstring for `ensure_init` for optional arguments.
The author of `mymodule` may have already called `ensure_init` as step peformed when
`import mymodule` is executed. In this case, calling `ensure_init` again is a no-op.

To compile, or recompile, the Julia project, the user calls `mymodule.project.compile()`.
The compiled Julia system image will be used the next time `mymodule` is imported, speeding up
both startup and the first execution of code.

Calling `mymodule.project.clean()` removes the compiled system image and some other files.
This will force again resolving the Julia package requirements on the next `import mymodule`.
Calling `mymodule.project.clean_all()` will remove the entire project tree.
This is a kind of "factory reset". The next time you run `project.ensure_init()` a new directory will be created
and populated with files from the installation directly.

Calling `mymodule.project.update()` checks for compatible updates of Julia packages that
are direct or indirect dependencies of `mymodule`, and performs the update.

If you want to handle installation and initialization of the Julia project and packages yourself, you can do
```python
import mymodule
mymodule.project.disable_init()
```
Then subsequent calls to `ensure_init`, explicit or otherwise will do nothing. `project.enable_init()`
will enable initialization if it has been disabled.

If someone else has called `mymodule.project.disable_init()` and you want to override it, you
can call `mymodule.project.enable_init()`.

## Choosing pyjulia or juliacall

Pass either "juliacall" or "pyjulia" as the argument `calljulia` to `ensure_init`.
For example

```python
import mymodule
myjuliamod.project.ensure_init(calljulia="juliacall")
```

## Using `julia_project` to call Julia functions

A Python-package author can use `find_julia` to provide a custom interface to Julia resources.
The author may provide an full-featured or thin interface. In any case it is sometimes
useful to access the Julia/Python interface library directly.
You can also get the imported Python library, either `julia` (i.e. `pyjulia`) or `juliacall` like this
```python
myjuliamod.project.julia
```

For example, the Julia module `Main` may be accessed like this.
```python
Main = myjuliamod.project.julia.Main
Main.sind(90) # 1.0
```

The semantics and syntax of Python modules `julia` and `juliacall` are quite different.
But, `julia_project` provides a minimal common layer.
For example,
```python
Example = project.simple_import("Example")
```
imports the Julia module `Example`.

Some parts of managing the Julia project are particular to either `pyjulia` or
`juliacall`. These are handled by the classes `PyJulia` and `JuliaCall`.
And `project.calljulia` is an instance of one of these.

## For the author of a package using `julia_project`

The intended use is as follows.
You want to create a Python package that calls some Julia packages via pyjulia.
You create a directory representing the top level of a Python package,
with a `setup.py` and `requirements.txt` and the Python code
in a directory `mymodule`.
You create a file `./mymodule/Project.toml` describing the Julia packages for the project.
In a Python source file in `./mymodule/`, you create an instance of `julia_project.JuliaProject`
that manages the Julia project. Call this instance `project` and import it into mymodule.
For example, in `_julia_project.py`, you might have `project = julia_project.JuliaProject([args])`.
And in `__init__.py` of `mymodule` you have `from _julia_project.py import project`.
(See [the example directory](./examples/myjuliamod)).

### What julia_project does

Then `import mymodule; mymodule.project.ensure_init()` will do the following

* Look for the Julia executable in various places using [`find_julia`](https://github.com/jlapeyre/find_julia)
* Offer to download and install Julia if it is not found.
* Optionally create a private Julia depot for `mymodule` to avoid possible issues with
  `PyCall` in different Python environments.
* Check that the `julia` (or `juliacall`) package is installed.
  I.e. check that `PyCall`, or `PythonCall` is installed and built, etc.
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
project = JuliaProject(
    name="mymodule",
    package_path=mymodule_path,
    registries = {"MyModuleRegistry" : "git@github.com:myuser/MyModuleRegistry.git"},
    logging_level = logging.INFO # or WARN, or ERROR,
    )

# If the following is omitted, the user of mymodule must call it explicitly.
project.ensure_init() # This exectutes all the management features listed above
```

* Create `./mymodule/Project.toml` (or `./mymodule/JuliaProject.toml`)  for the Julia project.

#### Compiling

Make a folder `./mymodule/sys_image/`. Add a file `./mymodule/sys_image/Project.toml` (or `./mymodule/sys_image/JuliaProject.toml`)
This typically contains the same dependencies as the top-level `Project.toml`. Perhaps a few more or less.
Add a script `./mymodule/sys_image/packages.jl` containing an `Array{Symbol}` of packages to be
included in the image.
```julia
[:APackage, :AnotherPackage]
```

* You don't need to include `PyCall` or `PythonCall`.

* Optionally include a file `compile_exercise_script.jl` that will passed as `precompile_execution_file`.

* After compiling, the system image file will be renamed from `sys_julia_project.so` (or
   `dll`, or `dylib`) to a name that includes the version of the julia exectuable that
   built it. The latter is the file name that will be searched for the next time you
   import `mymodule`.

* The project is compiled by calling the method `JuliaProject.compile` either explicitly or during the installation.

#### Arguments to JuliaProject

```python
name,
package_path,
registries=None,
version_spec="^1.6",
strict_version=True,
sys_image_dir="sys_image",
sys_image_file_base=None,
calljulia="pyjulia",
env_prefix="JULIA_PROJECT_",
post_init_hook=None,
depot=None,
logging_level=None,
console_logging=False
```

* `name` -- the name of the module, e.g. "mymodule". Used only in the logger and the name of the system image.
* `package_path` -- path to the top level of `mymodule`.
* `registry_url` -- if `None` then no registry will be installed (other than
       the General registry, if not already installed.)
* `version_spec` -- A julia [version compatibility specification](https://pkgdocs.julialang.org/v1/compatibility/). The julia
      executable must satisfy this specification.
* `strict_version` -- If `True` prerelease (development) versions of Julia are disallowed when applying `version_spec`.
* `sys_image_dir` -- the directory in which scripts for compiling a system image, and the system images, are found. This is
   relative to the top level of `mymodule`.
* `sys_image_file_base` -- the base name of the Julia system image. The system image file will be `sys_image_file_base + "-" + a_julia_version_string + ".ext"`,
    where `ext` is the dynamic lib extension for your platform.
* `calljulia` -- The julia-from-python interface library. One of two Python packages "pyjulia" and "juliacall".
* `env_prefix` -- Prefix for environment variables to set project options
* `depot` -- If `True`, then a private depot in the `mymodule` installation directory will be used.
* `post_init_hook` -- A function that will be called immediately before `ensure_init` returns.
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

* `JULIA_PROJECT_DEPOT` -- If set to `y`, then a private Julia depot will be created in a directory `depot` under the
  `mymodule` installation directory. The depot contains all downloaded registries, packages, precompiled packages, and
   many other data related to your julia installation. Set to `n` to use the standard depot. If it is unset, you may
   be prompted for your choice.

#### Location of julia executable

`JuliaProject` will look in the following locations, in order

* The environment variable `JULIA_PROJECT_JULIA_PATH`. With `JULIA_PROJECT_` optionally replaced by `env_prefix` described above.

* In the package top level for the installation `./julia/`

* A julia installation from `jill.py`, with preferred versions specified as above.

* Your system or shell PATH variable.

* A fresh installation of julia via `jill.py` after asking if you want to download and install.

#### Building `PyCall`

Installing and using `PyCall` is sometimes easy and sometimes confusing. The latter happens if
you try to use `PyCall` with different Python environments. The whole issue can be avoided
by using a private, or Python-package-specific Julia "depot".
Any of the following will create and use such a depot.

* Enable a new depot by passing the argument `depot=True` when initializing your `JuliaProject` instance.

* The user can set the environment variable `JULIA_PROJECT_DEPOT` described above.

* If no `PyCall.jl` is found, the option to create the package-specific depot will be given.

* If there is a libpython conflict detected during installation you will be prompted to
 create a depot.

The new depot will be used each time `mymodule` is imported. Remove or rename the directory `mymodule/depot`
to prevent this.

When using a new depot, registries, packges, cached precompiled files, and many other things are stored
in the installation directory of the project, e.g. `mymodule`.

This is a heavy solution because it involves duplicating many files if you use Julia for other projects, with Python or not.
But, it does not require that the end user understand anything about the status of your Julia installation, libpython, `PyCall.jl`,
etc.

Using a private depot should also allow `julia_project` to work with conda environments.

#### Testing

TESTS ARE OUTDATED!

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
