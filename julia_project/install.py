import subprocess
import shutil
import os
import sys
import pathlib
import datetime
import logging
import tomli
import find_libpython


LOGGER = logging.getLogger('julia_project.install')

std_flags = ['-q', '--history-file=no', '--startup-file=no', '--optimize=0']


def reset_env_var(var_name, old_val):
    if old_val:
        os.environ[var_name] = old_val
    elif os.getenv(var_name):
        del os.environ[var_name]
        # os.unsetenv(var_name)) this does nothing


# Try to print output as it is received
def run_julia(commands=None, julia_exe=None, depot_path=None, clog=False, no_stderr=False):
    if julia_exe is None:
        julia_exe = shutil.which("julia")
    old_depot = os.getenv("JULIA_DEPOT_PATH")
    try:
        if depot_path is not None:
            depot_path = os.path.abspath(depot_path)
            os.environ["JULIA_DEPOT_PATH"] = depot_path
        stderr_dest = subprocess.DEVNULL if no_stderr else subprocess.STDOUT
        process = subprocess.Popen(
            [julia_exe, *std_flags, '-e',  commands],
            stdout=subprocess.PIPE, stderr=stderr_dest, encoding='utf8'
        )
        stdout_output = ''
        while True:
            output = process.stdout.readline()
            stdout_output = stdout_output + output # bad accumulation
            if not no_stderr:
                sys.stdout.write(output)
            if process.poll() is not None:
                break
    except subprocess.CalledProcessError as err:
        if clog:
            print(err.stderr)
        raise err
    except Exception as err:
        print("!!!!!!!!!!! Got an err ", type(err))
        raise err
    finally:
        reset_env_var("JULIA_DEPOT_PATH", old_depot)
    return stdout_output


# Print output only at end of command
def old_run_julia(commands=None, julia_exe=None, depot_path=None, clog=False):
    if julia_exe is None:
        julia_exe = shutil.which("julia")

    old_depot = os.getenv("JULIA_DEPOT_PATH")
    try:
        if depot_path is not None:
            depot_path = os.path.abspath(depot_path)
            os.environ["JULIA_DEPOT_PATH"] = depot_path
        result = subprocess.run(
            [julia_exe, *std_flags, '-e', commands], check=True, capture_output=True, encoding='utf8'
        )
    except subprocess.CalledProcessError as err:
        if clog:
            print(err.stderr)
        raise err
    finally:
        reset_env_var("JULIA_DEPOT_PATH", old_depot)
    if clog:
        print(result.stdout)
        print(result.stderr)
    return result


# We could also parse the toml and look for name. But, we go by directory name
# Eg "General.toml", "QuantumRegistry"
def is_registry_installed(name, depot_path=None):
    if depot_path is None:
        depot_path = os.path.join(str(pathlib.Path.home()), ".julia")
    registry = os.path.join(depot_path, "registries", name)
    if registry.endswith("toml"):
        return os.path.isfile(registry)
    return os.path.isdir(registry)


# This takes perhaps 2s to run if it errors because Registry is installed.
def install_registry_from_url(registry_url, julia_exe=None, depot_path=None, clog=False):
    com = f'import Pkg; Pkg.Registry.add(Pkg.RegistrySpec(url = "{registry_url}"))'
    return run_julia(commands=com, julia_exe=julia_exe, depot_path=depot_path, clog=clog)


# TODO: We could activate the project via JULIA_PROJECT as well.
# We would reset it in a `finally` block
def run_pkg_commands(project_path, commands, julia_exe=None, depot_path=None, clog=False, no_stderr=False):
    if not os.path.isdir(project_path) and not os.path.isfile(project_path):
        raise FileNotFoundError(f"{project_path} does not exist")
    com = f'import Pkg; Pkg.activate("{project_path}"); ' + commands
    return run_julia(commands=com, julia_exe=julia_exe, depot_path=depot_path, clog=clog, no_stderr=no_stderr)


def _parse_toml(file_name):
    with open(file_name, 'rb') as fp:
        toml = tomli.load(fp)
    return toml


def parse_project(project_path):
    toml_path = get_project_toml(project_path)
    return _parse_toml(toml_path)


# TODO: Could use uuids too
def is_package_in_project(project_path, package_name):
    """
    Return True if `package_name` is in the (Julia)Project.toml in `project_path`.

    If package_name is a list of package names, return a list of results.
    """
    toml = parse_project(project_path)
    packs = toml["deps"].keys()
    if isinstance(package_name, str):
        return package_name in packs
    if isinstance(package_name, list):
        return [pn in packs for pn in package_name]
    raise TypeError("Excpecting str or list")


def _add_packages_string(packages_to_add):
    return ";".join([f'Pkg.add("{name}")' for name in packages_to_add])


def instantiate(project_path, julia_exe=None, depot_path=None, clog=False, packages_to_add=None):
    if packages_to_add is None:
        add_pkg_str = ''
    else:
        add_pkg_str = _add_packages_string(packages_to_add)
    result = run_pkg_commands(project_path, add_pkg_str +  '; Pkg.instantiate()',
                            julia_exe=julia_exe, depot_path=depot_path, clog=clog)
    manifest_toml = get_manifest_toml(project_path)
    if manifest_toml is None:
        raise Exception(f"Instantiation of project failed, no Manifest.toml created in {project_path}.")
    # For some reason Project.toml ends up slightly more recent, triggering init on next startup
    touch(manifest_toml)
    return result


def resolve(project_path, julia_exe=None, depot_path=None, clog=False, packages_to_add=None):
    if packages_to_add is None:
        add_pkg_str = ''
    else:
        add_pkg_str = _add_packages_string(packages_to_add)
    result = run_pkg_commands(project_path, add_pkg_str + '; Pkg.resolve()',
                            julia_exe=julia_exe, depot_path=depot_path, clog=clog)
    manifest_toml = get_manifest_toml(project_path)
    if manifest_toml is None:
        raise Exception(f"Instantiation of project failed, no Manifest.toml created in {project_path}.")

    touch(manifest_toml)
    return result


def add_general_registry(project_path, julia_exe=None, depot_path=None, clog=False):
    return run_pkg_commands(project_path, 'Pkg.Registry.add("General")',
                            julia_exe=julia_exe, depot_path=depot_path, clog=clog)


def registry_update(project_path, julia_exe=None, depot_path=None, clog=False):
    if is_registry_installed("General.toml", depot_path=depot_path):
        com = 'Pkg.Registry.update()'
    else:
        com = 'Pkg.Registry.add("General")'
    return run_pkg_commands(project_path, com,
                            julia_exe=julia_exe, depot_path=depot_path, clog=clog)


def ensure_general_registry(project_path, julia_exe=None, depot_path=None, clog=False):
    if not is_registry_installed("General.toml", depot_path=depot_path):
        msg = "Installing general registry"
        LOGGER.info(msg)
        if clog:
            print(msg)
        result = add_general_registry(project_path, julia_exe=julia_exe, depot_path=depot_path, clog=clog)
        if not is_registry_installed("General.toml", depot_path=depot_path):
            raise Exception("Installation of General registry failed.")
        return result
    return None


def ensure_registry_from_url(registry_name, registry_url, julia_exe=None, depot_path=None, clog=False):
    if not is_registry_installed(registry_name, depot_path=depot_path):
        msg = f"Installing registry {registry_name}"
        LOGGER.info(msg)
        if clog:
            print(msg)
        install_registry_from_url(registry_url, julia_exe=julia_exe, depot_path=depot_path, clog=clog)
        if not is_registry_installed(registry_name, depot_path=depot_path):
            raise Exception(f"Installation of registry {registry_name} failed.")


def get_project_toml(proj_dir):
    pt = os.path.join(proj_dir, "JuliaProject.toml")
    if os.path.exists(pt):
        return pt
    pt = os.path.join(proj_dir, "Project.toml")
    if os.path.exists(pt):
        return pt
    return None



def get_manifest_toml(proj_dir):
    proj_toml = get_project_toml(proj_dir)
    if proj_toml is None:
        raise FileNotFoundError("Project.toml is missing while searching for Manifest.toml")
    if proj_toml.endswith("Project.toml"):
        mt = os.path.join(proj_dir, "Manifest.toml")
        if os.path.exists(mt):
            return mt
        return None
    assert proj_toml.endswith("JuliaProject.toml")
    mt = os.path.join(proj_dir, "JuliaManifest.toml")
    if os.path.exists(mt):
        return mt
    return None


def manifest_mtime(project_path):
    manifest_toml = get_manifest_toml(project_path)
    manifest_time = os.path.getmtime(manifest_toml)
    return manifest_time



def need_resolve(project_path, depot_path):
    need_resolve_res, _ = _need_resolve(project_path, depot_path)
    return need_resolve_res


def _need_resolve(project_path, depot_path):
    if (depot_path is not None and os.path.isdir(depot_path)
        and (
            (not os.path.isdir(os.path.join(depot_path, "registries")))
            or
            (not os.path.isdir(os.path.join(depot_path, "packages")))
            or
            (not os.path.isdir(os.path.join(depot_path, "compiled")))
            )
        ):
        LOGGER.info(f"need_resolve: packages and/or registries missing from depo: {depot_path}")
        return (True, None)
    proj_toml = get_project_toml(project_path)
    manifest_toml = get_manifest_toml(project_path)
    if manifest_toml is None:
        LOGGER.info("need_resolve: No Manifest.toml")
        return (True, None)
    proj_time = os.path.getmtime(proj_toml)
    manifest_time = os.path.getmtime(manifest_toml)
    if proj_time > manifest_time:
        LOGGER.info(f"need_resolve: Project.toml newer than Manifest.toml. Difference: {proj_time - manifest_time}.")
        return (True, manifest_time)
    LOGGER.info("need_resolve: No need to resolve or instantiate found.")
    return (False, manifest_time)


def touch(file_path):
    now = datetime.datetime.now()
    set_file_mutimes(file_path, now)


def set_file_mutimes(file_path, dt):
    dt_epoch = dt.timestamp()
    os.utime(file_path, (dt_epoch, dt_epoch))


def ensure_project_ready(project_path=None, julia_exe=None, depot_path=None,
                         registries=None, clog=False, preinstall_callback=None,
                         packages_to_add=None,
                         force=False):
    """
    Check that Julia project is properly installed, taking action if not.

    - project_path : the directory containing Project.toml
    - julia_exe :  path to the Julia exectuable. default which("julia")
    - depot_path : optional value for JULIA_DEPOT_PATH
    - registries : dict whose keys are registry names and values are urls
        The general registry is always installed.
    - packages_to_add : optional list of package names that will be added to
        the project if not already present.
    - preinstall_callback : called before any work is done
    - force : perform installation steps even if not needed. Some of these
      steps may check if action is needed, and these checks are not overridden.
    - clog : bool Print some log information to the console.
    """
    LOGGER.info(f"ensure_project_ready:  project {project_path}, depot {depot_path}")
    if project_path is None:
        project_path = "."

    if packages_to_add is not None:
        LOGGER.info(f"Want packages in project: {packages_to_add}")
        pack_iter = zip(packages_to_add, is_package_in_project(project_path, packages_to_add))
        needed_packs = [p for (p, v) in pack_iter if not v]
        LOGGER.info(f"Need to add packages not in project: {needed_packs}")
    else:
        needed_packs = None

    need_resolve_res, start_manifest_time = _need_resolve(project_path, depot_path)
    if (not need_resolve_res) and (not force) and not needed_packs:
        LOGGER.info("Project needs no installation or updating")
        return None
    LOGGER.info(f"Installing or instantiating project: project {project_path}, depot {depot_path}")
    if preinstall_callback is not None: # We are not using this
        LOGGER.info("Running preinstall_callback.")
        preinstall_callback()
    ensure_general_registry(project_path, julia_exe=julia_exe, depot_path=depot_path, clog=clog)
    if registries is not None:
        if not isinstance(registries, dict):
            raise TypeError(f"registries must be a dict. Got type {type(registries)}.")
        for reg_name in registries.keys():
            url = registries[reg_name]
            ensure_registry_from_url(reg_name, url, julia_exe=julia_exe, depot_path=depot_path, clog=clog)
    msg = "Instantiating project..."
    LOGGER.info(msg)
    if clog:
        print(msg)
    res = instantiate(project_path, julia_exe=julia_exe, depot_path=depot_path, clog=clog, packages_to_add=needed_packs)
#    except: Probably don't want this
#        res = resolve(project_path, julia_exe=julia_exe, depot_path=depot_path, clog=clog)

    if start_manifest_time is not None:
        end_manifest_time = manifest_mtime(project_path)
        if start_manifest_time == end_manifest_time: # nothing changed
            manifest_toml = get_manifest_toml(project_path)
            touch(manifest_toml) # prevent instantiating next time

    return res


_get_pycall_libpython_str = '''
function  get_pycall_libpython()
    pycall_jl = Base.find_package("PyCall")
    if isnothing(pycall_jl)
        return (nothing, nothing, "not installed")
    end
    deps_jl = joinpath(dirname(dirname(pycall_jl)), "deps", "deps.jl")
    if ! isfile(deps_jl)
        return (nothing, nothing, "not built")
    end
    include(deps_jl) # not a great way to do this
    return (libpython, python, "ok")
end
'''


def get_pycall_libpython(project_path, julia_exe=None, depot_path=None, clog=False):
    coms = f'include_string(Main, """{_get_pycall_libpython_str}"""); res = get_pycall_libpython(); print(res[1],",",res[2],",",res[3])'
    try:
        result = run_pkg_commands(project_path, commands=coms, julia_exe=julia_exe, depot_path=depot_path, clog=clog, no_stderr=True)
    except subprocess.CalledProcessError as err:
        if clog:
            print(err.stderr)
        raise err
    libpython, python_exe, msg = result.split(",")  # result.stdout.split(",")
    return libpython, python_exe, msg


def test_pycall(project_path, julia_exe=None, depot_path=None, clog=False):
    """Return True if PyCall.jl uses the same libpython as the current process
    and a message explaining the result.
    """
    if julia_exe is None:
        julia_exe = shutil.which("julia")
    pycall_libpython, pycall_python_exe, msg = get_pycall_libpython(project_path, julia_exe=julia_exe, depot_path=depot_path, clog=clog)
    result = {"lib": pycall_libpython, "exe": pycall_python_exe, "msg": msg, "jexe": julia_exe, "this_lib": None}
    if pycall_libpython == "nothing":
        result["pycall_ok"] = False
    else:
        this_libpython = find_libpython.find_libpython()
        result["this_lib"] = this_libpython
        if clog:
            print(f"pycall_libpython={pycall_libpython}  this_libpython={this_libpython}")
        comp = pycall_libpython == this_libpython
        if comp is True:
            result["pycall_ok"] = True
        else:
            result["pycall_ok"] = False
            result["msg"] = "incompatible libpython"
    return result


def is_pycall_ok(result):
    return result["pycall_ok"]


def pycall_test_msg(result):
    return result["msg"]


def is_pycall_lib_incompatible(result):
    return result["msg"] == "incompatible libpython"


def is_pycall_built(result):
    return not (result["msg"] == "not built")


def is_pycall_installed(result):
    return not (result["msg"] == "not installed")


def explain_pycall_test(result):
    if result["msg"] == "incompatible libpython":
        txt = f"""
Your Python and Julia setup have conflicting python libraries:

Julia executable:
    {result["jexe"]}
Python interpreter and libpython used by PyCall.jl:
    {result["exe"]}
    {result["lib"]}
Python interpreter used to import PyJulia and its libpython.
    {sys.executable}
    {result["this_lib"]}
"""
    else:
        txt = str(result)
    return txt


def slow_test_pycall(project_path, julia_exe=None, depot_path=None, clog=False):
    coms = 'import PyCall; print(PyCall.libpython)'
    try:
        result = run_pkg_commands(project_path, commands=coms, julia_exe=julia_exe, depot_path=depot_path, clog=clog)
    except subprocess.CalledProcessError as err:
        msg = err.stderr
        if msg.find("not properly installed"):
            return (False, "not built")
        return (False, "unknown")
    pycall_libpython = result.stdout
    this_libpython = find_libpython.find_libpython()
    if clog:
        print(f"pycall_libpython={pycall_libpython}  this_libpython={this_libpython}")
    result = pycall_libpython == this_libpython
    if result is True:
        return (True, None)
    return (result, "incompatible libpython")


def rebuild_pycall(project_path, python_exe=None, julia_exe=None, depot_path=None, clog=False):
    if python_exe == "conda":
        python_exe = "~/.julia/conda/3/bin/python"
    if python_exe is None:
        python_exe = sys.executable
    coms = 'Pkg.build("PyCall")'
    old_python = os.getenv("PYTHON")
    try:
        os.environ["PYTHON"] = python_exe
        if clog:
            print(f"run_pkg_commands({project_path}, commands={coms}, julia_exe={julia_exe}, depot_path={depot_path}, clog={clog})")
        result = run_pkg_commands(project_path, commands=coms, julia_exe=julia_exe, depot_path=depot_path, clog=clog)
    except subprocess.CalledProcessError as err:
        raise err
    finally:
        reset_env_var("PYTHON", old_python)
    return result


def ensure_project_ready_fix_pycall(
        project_path=None,
        julia_exe=None,
        depot_path=None,
        registries=None,
        clog=False,
        preinstall_callback=None,
        packages_to_add=None,
        force=False,
        possible_depot_path=None,
        question_callback=None,
        answer_rebuild_callback=None,
        answer_depot_callback=None,
):
    """
        Check that Julia project is properly installed and try to fix PyCall if needed.

        Many of the arguments are passed to `ensure_project_ready`.
        - presintall_callback is a function to be called before installing/updating
        - depot_path if not None will be used as a depot
        - possible_depot_path will be used as a depot if libpython is incompatible and
           user chooses ot use a new depot, even if depot_path was None.
        - question_callback is a function called if libpython is incompatible.
                 It must take one arg: text to be printed before asking.
                 It must return "depot", "rebuild", or raise an error
        - answer_rebuild_callback optional callback called after "rebuild" answer received.
        - answer_depot_callback optional callback called after "depot" answer received.
    """
    for trial_num in (1, 2, 3):
        if trial_num == 1:
            if force is not True:
                force = False
        else:
            force = True
        LOGGER.info(f"Trial {trial_num}: ensure_project_ready")
        ensure_project_ready(project_path, julia_exe, depot_path=depot_path,
                             registries=registries, clog=clog,
                             preinstall_callback=preinstall_callback, packages_to_add=packages_to_add, force=force)
        pycall_result = test_pycall(project_path, julia_exe, depot_path=depot_path, clog=False)
        if is_pycall_lib_incompatible(pycall_result):
            LOGGER.info("Incompatible libpython detected.")
            if question_callback is None:
                question_callback = resolve_incompatibility
            answer = question_callback(explain_pycall_test(pycall_result))
            if answer == "rebuild":
                if answer_rebuild_callback is not None:
                    answer_rebuild_callback()
                rebuild_pycall(project_path, python_exe=sys.executable, julia_exe = julia_exe,
                                       depot_path=depot_path, clog=True)
                pycall_result = test_pycall(project_path, julia_exe, depot_path=depot_path, clog=True)
                if not is_pycall_ok(pycall_result):
                    raise Exception(f"Rebuilding PyCall failed: {explain_pycall_test(pycall_result)}")
                print("Rebuilding PyCall succeeded.")
                return
            if answer == "depot":
                if answer_depot_callback is not None:
                    answer_depot_callback()
                depot_path = possible_depot_path
                LOGGER.info(f"Resolved by choosing new depot: {depot_path}.")
            else:
                raise ValueError("Unrecognized libpython answer")
        elif is_pycall_ok(pycall_result):
            return
        elif not is_pycall_built(pycall_result):
            print("PyCall is not built: building...")
            rebuild_pycall(project_path, python_exe=sys.executable, julia_exe = julia_exe,
                                   depot_path=depot_path, clog=True)
            pycall_result = test_pycall(project_path, julia_exe, depot_path=depot_path, clog=True)
            if not is_pycall_ok(pycall_result):
                raise Exception(f"Rebuilding PyCall failed: {explain_pycall_test(pycall_result)}")
            print("Rebuilding PyCall succeeded.")
            return
        elif not is_pycall_installed(pycall_result):
            print("PyCall is not installed. Instantiating...")
        else:
            raise Exception(f"PyCall is not ok: {explain_pycall_test(pycall_result)}")

    raise Exception("Unable to properly install PyCall")


_INCOMPATIBLE_PYTHON_QUESTION = """
The currently running libpython is different from the one that was used to build
the required Julia package PyCall.jl.
The two libraries are required to be the same. I can take one of three actions:

1. Create a Julia depot specific to this python package. All Julia packages,
including PyCall, as well as cached, compiled code will be stored in this
depot. The version of PyCall in your main depot (the one currently causing this
problem) and the one in your new python-package-specific depot can coexist.

2. "Rebuild" PyCall to use the currently running libpython. This means PyCall will no
 longer work with the libpython that it was previously built with.

3. Print a more detailed error message and exit.

If you are unsure, choose 1.
"""

def resolve_incompatibility(incompat_msg=None):
    if incompat_msg is None:
        incompat_msg = "PyCall: incompatible libpythons"
    sys.stdout.write(_INCOMPATIBLE_PYTHON_QUESTION)
    prompt = "Choose one of 1, 2, 3: "
    while True:
        sys.stdout.write(prompt)
        choice = input()
        if choice not in ("1", "2", "3"):
            sys.stdout.write("Please respond with '1', '2' or '3'\n")
        else:
            break
    if choice == '1':
        return "depot"
    if choice == '2':
        return "rebuild"
    print(incompat_msg)
    raise Exception(incompat_msg)
