## Example Python package using `julia_project`

The code in `myjuliamod` is commented to document some hard-coded
configuration options that the author of the module can choose.

Importing `myjuliamod` imports an instance of `JuliaProject` as `project`.
The latter may be used to initialize the Julia dependencies.
```python
import myjuliamod
myjuliamod.project.ensure_init()
```

`ensure_init` takes an optional keyword argument `depot`. If `depot=True`,
then a Julia depot (package cache) specific to `myjuliamod` will be used.
In the source to `myjuliamod` you can see how calling `ensure_init` also loads
additional Python code and imports symbols into `myjuliamod`.

`myjuliamod` demonstrates how
the author of a module can provide for automatically calling
`ensure_init` when a submodule is imported.
```python
[1]: from myjuliamod import hellomod
  Activating project at `~/code/github/username/julia_project/examples/myjuliamod/myjuliamod`

In [2]: myjuliamod.hello()
Out[2]: 'Hello, myjuliamod'
```

## Main project Project.toml

The only Julia dependency of the python module `myjuliamod` is the package `Example.jl`.
The file `Project.toml` was created by doing `Pkg.activate(".")` in the
appropriate directory and then `Pkg.add("Example")`.


## Project for compilation

Note that `./myjuliamod/sys_iamge/Project.toml` must also include `PackageCompiler` and `PyCall`
