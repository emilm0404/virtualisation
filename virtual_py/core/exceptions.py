# base library exception.
class VMException(Exception):
    pass

# thrown when queried domain does not exist on the hypervisor host.
class VMNotFoundError(VMException):
    def __init__(self, name: str, message: str = None):
        self.name = name
        self.message = message or f"Virtual machine '{name}' not found."
        super().__init__(self.message)

# thrown on name collision. prevents double provision errors.
class VMAlreadyExistsError(VMException):
    def __init__(self, name: str, message: str = None):
        self.name = name
        self.message = message or f"Virtual machine '{name}' already exists."
        super().__init__(self.message)

# wrappers for virsh/powershell CLI errors.
# captures return code and stderr for traceback logs.
class HypervisorExecutionError(VMException):
    def __init__(self, command: str, returncode: int, stdout: str, stderr: str, message: str = None):
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.message = message or f"Command '{command}' failed with exit code {returncode}.\nStderr: {stderr}"
        super().__init__(self.message)
