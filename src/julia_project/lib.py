class LibJulia:
    """Store information on loaded libjulia"""

    def __init__(self,
                 libjulia,
                 libjulia_path,
                 bindir
                 ):
        self.libjulia = libjulia
        self.libjulia_path = libjulia_path
        self.bindir = bindir
