from . import utils


_QUESTIONS = {'install' : "No Julia installation found. Would you like jill.py to download and install Julia?",
              'compile' :
"""
I can compile a system image after installation.
Compilation may take a few, or many, minutues. You may compile now, later, or never.
Would you like to compile a system image after installation?
""",
              'depot' :
"""
You can install all of the Julia packages and package information in a module-specific "depot",
that is, one specific to this Python module. This may allow you to use Julia with python projects
that have different Python installation locations.
Or you can install packages in the standard per-user Julia "depot".
Would you like to use a python-module-specific depot for Julia packages?
"""
              }

_INCOMPATIBLE_PYTHON_QUESTION = """
The currently running libpython is different from the one that was used to build
the required Julia package PyCall.jl.
They are required to be the same. I can take one of three actions:
1. "Rebuild" PyCall to use the currently running libpython. This means PyCall will no
 longer work with the libpython that it was previously built with.
2. Create a Julia depot specific to this python package. All Julia packages, including PyCall,
as well as cached, compiled code will be stored in this depot. The version of PyCall in your
main depot (the one currently causing this problem) and the one in your new python-package-specific depot
can coexist. This will duplicate a lot of the data stored in your main depot.
3. Print a more detailed error message and exit.
"""

class ProjectQuestions:

    def __init__(self,
                 depot=None,
                 env_vars=None,
                 logger=None,
                 ):
        self.results = {"install": None, "compile": None, "depot": depot}
        if env_vars is None:
            env_vars = EnvVars()
        self.logger = logger
        self._env_vars = env_vars


    def ask_question(self, question_key):
        if self.results[question_key] is None:
            result = utils.query_yes_no(_QUESTIONS[question_key])
            self.results[question_key] = result
            self.logger.info(f"Question '{question_key}', answered {result}")


    def ask_questions(self):
        for q in self.results.keys():
            self.ask_question(q)


    def _read_one_variable(self, var_base_name, question_key):
        var_name = self._env_vars.envname(var_base_name)
        result = self._env_vars.getenv(var_base_name)
        if result:
           if result == 'y':
               self.results[question_key] = True
               self.logger.info(f"read {var_name} = 'y'")
           elif result == 'n':
               self.results[question_key] = False
               self.logger.info(f"read {var_name} = 'n'")
           else:
               raise ValueError(f"{var_name} must be y or n")
        else:
            self.logger.info(f"{var_name} not set")


    def read_environment_variables(self):
        self._read_one_variable("INSTALL_JULIA", "install")
        self._read_one_variable("COMPILE", "compile")
        self._read_one_variable("DEPOT", "depot")
