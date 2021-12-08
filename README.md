# julia_project

This package provides the class `JuliaProject` for managing a
[Julia project](https://pkgdocs.julialang.org/v1.7/environments/) that lives inside
a Python package and is accessed via [pyjulia](https://github.com/JuliaPy/pyjulia) (the Python module "julia").

`julia_project` is meant to do provide some automation, hand holding, and error checking.
The intended use is as follows. You want to create a Python package that calls some Julia packages
via pyjulia. You create a directory representing the top level of a Python package, with
a `setup.py` and `requirements.txt` and the Python code. You create a `Project.toml` file
in the top level describing the Julia packages for the project. You might do
`source ./venv`; `pip install -r requirements.txt`; `pip install -e .`.
Then `import mymodule` will do the following

* Check that `PyCall` is installed and built, and use the `julia` module to do so.
* Optionally download and install a Julia registry.
* Look for the Julia executable in various places
* Optionally load a custom Julia system image.
* Instantiate the Julia project.
* Provide a Python function that compiles a system image that will be found the next
  time `mymodule` is imported. The scripts and environment for compilation are found in
  a specified subdirectory of the Python project.
* Write info about all of the above to a log file

```python
import os
mymodule_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

julia_project = JuliaProject(
    name="mymodule",
    package_path=mymodule_path,
    registry_url = "git@github.com:myuser/MyModuleRegistry.git",
    logging_level = logging.INFO # or logging.WARN
)
``` 

This package is very new and is neither well tested nor documented.
