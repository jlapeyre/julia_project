## Example Python package using `julia_project`

The first time you do
```python
import myjuliamod
```
The Julia packages should be installed and optionally compiled.


To test, try this
```python
[1]: from myjuliamod import hello
  Activating project at `~/code/github/username/julia_project/examples/myjuliamod/myjuliamod`

In [2]: hello()
Out[2]: 'Hello, myjuliamod'
```

## Main project Project.toml

The mython module `myjuliaod` depends only on the package `Example.jl`. The file `Project.toml` is created by
doing `Pkg.activate(".")` in the appropriate directory and then `Pkg.add("Example")`.


## Project for compilation

Note that `./myjuliamod/sys_iamge/Project.toml` must also include `PackageCompiler` and `PyCall`
