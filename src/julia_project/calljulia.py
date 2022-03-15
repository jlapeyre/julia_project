# Is there any way to enforce this ?

class CallJulia:

    def seval(self, code: str):
        """Evaluate `code` in Julia. Only one toplevel statement allowed"""

    def seval_all(self, code: str):
        """Evaluate `code` in Julia"""

    # These properties are defined
    # self.julia_path = None
    # self.depot_dir = None
    # self.data_path = None
    # self.julia_system_image = None
    # self.questions = None
    # self.libjulia # : lib.LibJulia
