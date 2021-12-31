import os
import sys
import shutil
import logging

import jill.install
import jill.utils
from ._jill_install import get_installed_bin_paths


class JuliaResults:

    def __init__(self):

        self.julia_env_var_set = False
        self.want_julia_env_var = False
        self.julia_env_var_file = None

        self.want_other_julia_installation = False
        self.other_julia_installation = None
        self.exists_other_julia_not_installation = False
        self.other_julia_executable = None

        self.jill_julia_bin_paths = None
        self.preferred_jill_julia_executable = None

        self.julia_executable_in_path = None

        self.want_jill_install = None
        self.new_jill_installed_executable = None


    def get_julia_executable(self, order=None):
        if order is None:
            order = ['env', 'other', 'jill', 'path']

        found_julias = {'env': self.julia_env_var_file,
                        'other': self.other_julia_executable,
                        'jill': self.preferred_jill_julia_executable,
                        'path': self.julia_executable_in_path}
        for location in order:
            julia = found_julias[location]
            if julia:
                return julia
        return None


class FindJulia:

    def __init__(self,
                 preferred_julia_versions = ['1.7', '1.6', '1.5', 'latest'],
                 strict_preferred_julia_versions = False,
                 julia_env_var=None,
                 other_julia_installations=None,
                 confirm_install=True
                 ):


        self.preferred_julia_versions = preferred_julia_versions
        self.results = JuliaResults()
        if julia_env_var is None:
            self._julia_env_var = "JULIA"
        else:
            self._julia_env_var = julia_env_var
        if not isinstance(other_julia_installations, list) and other_julia_installations is not None:
            self._other_julia_installations = [other_julia_installations]
        else:
            self._other_julia_installations = other_julia_installations
        self.confirm_install = confirm_install


    def get_preferred_bin_path(self):
        if self.results.jill_julia_bin_paths is None:
            return None
        for pref in self.preferred_julia_versions:
            bin_path = self.results.jill_julia_bin_paths.get(pref)
            if bin_path:
                return bin_path
        if self.strict_preferred_julia_versions:
            return None
        return next(iter(results.jill_julia_bin_paths.values())) # Take the first one


    def find_julias(self):
        # Julia executable in environment variable
        if self._julia_env_var:
            self.results.want_julia_env_var = True
            result = os.getenv(self._julia_env_var)
            if result:
                self.results.julia_env_var_set = True
                if os.path.isfile(result):
                    self.results.julia_env_var_file = result

        # jill-installed julia executables
        self.results.jill_julia_bin_paths = get_installed_bin_paths()
        self.results.preferred_jill_julia_executable = self.get_preferred_bin_path()

        self.results.julia_executable_in_path = shutil.which("julia")

        # Other specified julia installation
        if self._other_julia_installations:
            self.results.want_other_julia_installation = True
            for other_julia_installation in self._other_julia_installations:
                if os.path.isdir(other_julia_installation):
                    self.results.other_julia_installation = other_julia_installation
                    julia_path = os.path.join(other_julia_installation, "bin", "julia")
                    if os.path.isfile(julia_path):
                        self.results.other_julia_executable = julia_path
                        break
                elif os.path.exists(other_julia_installation):
                    self.results.exists_other_julia_not_installation = True


    def prompt_and_install_jill_julia(self, not_found=False):
        if self.confirm_install and not_found:
            sys.stdout.write("No julia executable found.")
        if self.confirm_install:
            answer = jill.utils.query_yes_no("Would you like jill.py to download and install Julia?")
        else:
            answer = True
        if answer:
            self.results.want_jill_install = True
            jill.install.install_julia(confirm=self.confirm_install)
            path = self.get_preferred_bin_path()
            if path is None:
                raise FileNotFoundError("jill.py installation of julia failed")
            self.results.new_jill_installed_executable = path
        else:
            self.want_jill_install = False


    def find_one_julia(self, order=None):
        self.find_julias()
        return self.results.get_julia_executable(order=order)


    def get_or_install_julia(self, order=None):
        julia_path = self.find_one_julia(order=order)
        if julia_path:
            return julia_path
        else:
            self.prompt_and_install_jill_julia(not_found=True)
