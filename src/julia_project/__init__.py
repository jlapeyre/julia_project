__version__ = "0.1.27"

import os
import sys
import ctypes
import shutil
from ._julia_project import JuliaProject

os.environ["PYTHON_JULIACALL_NOINIT"] = "yes"
os.environ["JULIA_PYTHONCALL_EXE"] = sys.executable or ''
os.environ['JULIA_PYTHONCALL_LIBPTR'] = str(ctypes.pythonapi._handle) or ''
os.environ['PYTHON'] = shutil.which("python") or ''

# This is only for debugging
# import julia
# import julia.core
# julia.core.enable_debug()
