# import julia Surely don't want thisw
import logging
import importlib

from julia_project import JuliaProject

# The top-level directory of the mymodule installation must be
# passed when constructing JuliaProject. We compute this path here.
import os
myjuliamod_path = os.path.dirname(os.path.abspath(__file__))

# You may supply a hook to run after JuliaProject.ensure_init is called.
# For example, here we import hellomod into myjuliamod. The effect is
# as if we had added the line `import .hellomod` to mymjuliamod.__init__.
# We did not do the latter, because that would require checking and
# initializing Julia upon importing myjuliamod. The package author
# (i.e. author of myjuliamod) may wish to avoid the latter.
def _after_init_func():
    importlib.import_module('.hellomod', 'myjuliamod')


project = JuliaProject(
    name="myjuliamod",
    package_path=myjuliamod_path,
    version_spec = "^1.6", # Must be at least 1.6
    env_prefix = 'MYJULIAMOD_', # env variables prefixed with this may control JuliaProject
    logging_level = logging.INFO, # or logging.WARN,
    console_logging=False,
    post_init_hook=_after_init_func, # Run this after ensure_init
#    calljulia_lib = "pyjulia"
#    calljulia = "juliacall"
)
