import os
import sys
import shutil
import sysconfig

import logging
LOGGER = logging.getLogger('julia_project.utils') # shorten this?

is_windows = os.name == "nt"
is_apple = sys.platform == "darwin"

SHLIB_SUFFIX = sysconfig.get_config_var("SHLIB_SUFFIX")
if SHLIB_SUFFIX is None:
    if is_windows:
        SHLIB_SUFFIX = ".dll"
    else:
        SHLIB_SUFFIX = ".so"
if is_apple:
    # sysconfig.get_config_var("SHLIB_SUFFIX") can be ".so" in macOS.
    # Let's not use the value from sysconfig.
    SHLIB_SUFFIX = ".dylib"


# Copied from jill.py
def query_yes_no(question, default="yes"):
    """Ask a yes/no question via input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")


import subprocess

# From PythonCall
def julia_version_str(exe):
    """
    If exe is a julia executable, return its version as a string. Otherwise return None.
    """
    try:
        proc = subprocess.run([exe, "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except:
        return
    words = proc.stdout.decode('utf-8').split()
    if len(words) < 3 or words[0].lower() != 'julia' or words[1].lower() != 'version':
        return
    return words[2]


# Adapted from PythonCall
def _default_depot_path():
    return (os.environ.get("JULIA_DEPOT_PATH", "").split(";" if os.name == "nt" else ":")[0]
               or os.path.join(os.path.expanduser("~"), ".julia")
               )


# Adapted from PythonCall
def _get_virtual_env_path():
    paths = [os.environ.get('VIRTUAL_ENV'), os.environ.get('CONDA_PREFIX'), os.environ.get('MAMBA_PREFIX')]
    paths = [x for x in paths if x is not None]
    if len(paths) == 0:
        env_path = None
    elif len(paths) == 1:
        env_path = paths[0]
    else:
        raise Exception('You are using some mix of virtual, conda and mamba environments, cannot figure out which to use!')
    return env_path


def maybe_remove(path):
    if os.path.exists(path):
        os.remove(path)
        LOGGER.info(f"Removing {path}")


def update_copy(src, dest):
    """
    Possibly copy `src` to `dest`. No copy unless `src` exists.
    Copy if `dest` does not exist, or mtime of dest is older than
    of `src`.

    Returns: None
    """
    if os.path.exists(src):
        if (not os.path.exists(dest) or
            os.path.getmtime(dest) < os.path.getmtime(src)):
            shutil.copy(src, dest)
    return None


def _project_toml(project_path):
    return os.path.join(project_path, "Project.toml")


def _julia_project_toml(project_path):
    return os.path.join(project_path, "JuliaProject.toml")


def no_project_toml_message(project_path):
    return f'Neither "{_project_toml(project_path)}" nor "{_julia_project_toml(project_path)}" exist.'


def has_project_toml(project_path):
    return (
            os.path.exists(_project_toml(project_path)) or
            os.path.exists(_julia_project_toml(project_path))
    )


def has_manifest_toml(_dir):
    return (
            os.path.exists(os.path.join(_dir, "Manifest.toml")) or
            os.path.exists(os.path.join(_dir, "JuliaManifest.toml"))
    )
