import os

class EnvVars:

    def __init__(self,
                 env_prefix="JULIA_PROJECT_",
                 ):
        self.env_prefix = env_prefix


    def envname(self, env_var):
        return self.env_prefix + env_var


    def getenv(self, env_var):
        return os.getenv(self.env_prefix + env_var)
