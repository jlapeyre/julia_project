# This file should only be used until these features are available in jill.py

import os

import jill.utils
import jill.utils.defaults

from jill.utils.defaults import default_install_dir
from jill.utils import current_architecture, current_system
from jill.utils import latest_version

def _get_installation_dir(preferred_versions=None, only_preferred=False):
    """
    Return the path to a Julia installation. If `preferred_versions` is `None`, then the latest
    stable version is preferred. Otherwise, `preferred_versions` should be a list of versions, which
    are probed in order.  If the path to a preferred version is found, then it is returned.  If no
    preferred version is found and `only_preferred` is `False`, then the first path to an installed
    Julia found is returned.  Otherwise, `None` is returned.

    The preferred versions, if supplied, should have the form `major.minor`, or be `latest`. For
    example, `preferred_versions = ['1.7', 'latest']. If `preferred_versions` is `None`, there is a
    bit of latency while the latest stable version is fetched from a server, unless another jill.py
    function has already fetched and cached it.
    """
    julias_root = default_install_dir()
    if not os.path.isdir(julias_root):
        return None

    if preferred_versions is None:
        stable_version = latest_version("", current_system(), current_architecture()) # e.g. '1.7.0'
        stable_version  = '.'.join(stable_version.split('.')[0:2]) # e.g. '1.7'
        preferred_versions = [stable_version]
    preferred_julia_installations = ["julia-" + x for x in preferred_versions]
    installed_julias = [x for x in os.listdir(julias_root ) if x.startswith("julia")]
    found_installation = None
    for preferred_installation in preferred_julia_installations:
        if preferred_installation in installed_julias:
            found_installation = preferred_installation
            break
    if found_installation:
        return os.path.join(julias_root, found_installation)
    elif installed_julias and not only_preferred:  # Else take the first installation, if there.
        return os.path.join(julias_root, installed_julias[0])
    else:  # Else there are no julia installations
        return None


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


def get_installed_bin_path(preferred_versions=None, only_preferred=False):
    """
    Return the path to a Julia installation. If `preferred_versions` is `None`, then the latest
    stable version is preferred. Otherwise, `preferred_versions` should be a list of versions, which
    are probed in order.  If the path to a preferred version is found, then it is returned.  If no
    preferred version is found and `only_preferred` is `False`, then the first path to an installed
    Julia executable found is returned.  Otherwise, `None` is returned.

    The preferred versions, if supplied, should have the form `major.minor`, or be `latest`. For
    example, `preferred_versions = ['1.7', 'latest']. If `preferred_versions` is `None`, there is a
    bit of latency while the latest stable version is fetched from a server, unless another jill.py
    function has already fetched and cached it.
    """
    installation_path = _get_installation_dir(preferred_versions=preferred_versions, only_preferred=only_preferred)
    if installation_path:
        return os.path.join(installation_path, _get_relative_bin_path())
    else:
        return None


