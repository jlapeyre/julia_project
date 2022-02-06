import sys

# Import the instance of JuliaProject
from ._julia_project import project

# The user may have already called this line to initialize the Julia environment.
# Calls to ensure_init after the first call are no-ops.
# Because we include this line, the user may enter `import myjuliamod.hellomod`
# without having first imported myjuliamod or having run ensure_init().
# Omit this line if you want to force the user to call ensure_init explicitly.
project.ensure_init()


# Import a Julia module. This works with either julia/PyCall or juliacall/PythonCall
Example = project.simple_import("Example")

# Alternatively, For julia/PyCall
# from julia import Example

# And for juliacall/PythonCall
# import juliacall
# juliacall.using(locals(), module="Example", prefix="")


def hello():
    return Example.hello("myjuliamod")

# You may want to do something like the following.
# This has the same effect as putting the following line in __init__.py:
# from .hellomod import hello
# Ths difference is that the previous line would start Julia upon importing myjuliamod, which
# may not be desirable.
sys.modules['myjuliamod'].hello = hello
