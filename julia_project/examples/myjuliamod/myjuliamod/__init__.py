# This only creates the JuliaProject instance, but does not install or initialize the Julia environment
# The user must take some action to install and initialize. For example myjuliamod.project.ensure_init()
from ._julia_project import project

# You may choose to uncomment the following, in which case the julia installation is
# checked and initialized every time the user does `import myjuliamod`.
#
# In the files hellomod.py and _julia_project.py we included code to automatically
# load a submodule (hellomod) after initialization, and to import symbols into
# the myjuliamod namespace. Those tricks are not necessary if you uncomment the following.
#
# project.ensure_init()
# import hellomod
# from hellomod import hello
#
# In practice, you probably would not want to import both hellomod and hello.
