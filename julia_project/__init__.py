import os
import sys
import ctypes
import shutil
from ._version import __version__
from ._julia_project import JuliaProject

os.environ["PYTHON_JULIACALL_NOINIT"] = "yes"
os.environ["JULIA_PYTHONCALL_EXE"] = sys.executable or '' # When does the latter occur?
os.environ['JULIA_PYTHONCALL_LIBPTR'] = str(ctypes.pythonapi._handle)
os.environ['PYTHON'] = shutil.which("python")

# This is only for debugging
# import julia
# import julia.core
# julia.core.enable_debug()
