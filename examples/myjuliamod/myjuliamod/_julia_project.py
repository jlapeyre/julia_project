import julia
import logging

from julia_project import JuliaProject

import os
myjuliamod_path = os.path.dirname(os.path.abspath(__file__))

julia_project = JuliaProject(
    name="myjuliamod",
    package_path=myjuliamod_path,
    preferred_julia_versions = ['1.7', '1.6', 'latest'],
    env_prefix = 'MYJULIAMOD_',
    logging_level = logging.INFO, # or logging.WARN,
    console_logging=False
)

julia_project.run()

# logger = julia_project.logger

# Directory of Julia source files that may be loaded via Python
julia_src_dir = julia_project.julia_src_dir

def compile_myjuliamod():
    """
    Compile a system image for `myjuliamod` in the subdirectory `./sys_image/`. This
    system image will be loaded the next time you import `myjuliamod`.
    """
    julia_project.compile_julia_project()


def update_myjuliamod():
    """
    Remove possible stale Manifest.toml files and compiled system image.
    Update Julia packages and rebuild Manifest.toml file.
    Before compiling, it's probably a good idea to call this method, then restart Python.
    """
    julia_project.update()
