# This file should only be used until these features are available in jill.py

import os

import jill.utils
import jill.utils.defaults

from jill.utils.defaults import default_install_dir
from jill.utils import current_architecture, current_system
from jill.utils import latest_version


def _get_relative_bin_path():
    system = current_system()
    if system == "winnt":
        return os.path.join("bin", "julia.exe")
    elif system == "mac":
        return os.path.join("Contents", "Resources", "julia", "bin", "julia")
    elif system == "linux" or system == "freebsd":
        return os.path.join("bin", "julia")
    else:
        raise ValueError(f"Unsupported system {system}")


def get_installed_bin_paths():
    """
    Return a dict whose keys are Julia version strings and whose values are
    absolute paths to the corresponding Julia exectuable. Only jill.py's
    default directory for Julia installations is searched.
    The version strings either equal to `latest` or have the form `major.minor`.
    """
    julias_root = default_install_dir()
    if not os.path.isdir(julias_root):
        return None
    rel_bin_path = _get_relative_bin_path()
    return {x.split("-")[1] : os.path.join(julias_root, x, rel_bin_path) for x in os.listdir(julias_root ) if x.startswith("julia")}
