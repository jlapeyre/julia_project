from . import utils
from . import environment

_QUESTIONS = {'install' : "No Julia installation found. Would you like jill.py to download and install Julia?",
              'compile' :
"""
I can compile a system image after installation.
Compilation may take a few, or many, minutes. You may compile now, later, or never.
Would you like to compile a system image after installation?
""",
              'depot' :
"""
You can install all of the Julia packages and package information in a
module-specific "depot", that is, one specific to this Python module. This may
allow you to use Julia with python projects that have different Python
installation locations.  If you answer "no", packages will be installed in the
standard per-user Julia "depot".

Would you like to use a python-module-specific depot for Julia packages?
"""
              }


class ProjectQuestions:

    def __init__(self,
                 depot=None,
                 env_vars=None,
                 logger=None,
                 ):
        self.results = {"install": None, "compile": None, "depot": depot}
        if env_vars is None:
            env_vars = environment.EnvVars()
        self.logger = logger
        self._env_vars = env_vars


    def ask_question(self, question_key):
        if self.results[question_key] is None:
            result = utils.query_yes_no(_QUESTIONS[question_key])
            if result is not None:
                self.results[question_key] = result
                self.logger.info(f"Question '{question_key}', answered {result}")
                return result
            else:
                self.logger.info(f"Question '{question_key}', not answered. Possibly interrupted.")
                return None


    def ask_questions(self):
        result = None
        for q in self.results:
            result = self.ask_question(q)
        return result


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
