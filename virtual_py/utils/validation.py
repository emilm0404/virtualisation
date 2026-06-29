import re

# input validation to prevent shell injection attacks.
# we reject any vm or checkpoint name containing special characters.
def validate_vm_name(name: str) -> None:
    if not re.match(r"^[a-zA-Z0-9_\-\. ]+$", name):
        raise ValueError(f"invalid vm name '{name}'. only alphanumeric characters, dashes, dots, underscores, and spaces are allowed.")

def validate_checkpoint_name(name: str) -> None:
    if not re.match(r"^[a-zA-Z0-9_\-\. ]+$", name):
        raise ValueError(f"invalid checkpoint name '{name}'. only alphanumeric characters, dashes, dots, underscores, and spaces are allowed.")

def validate_path(path: str) -> None:
    # block redirection and command chaining characters that allow escaping strings.
    # colons, slashes, spaces, and dots are allowed.
    forbidden = [";", "&", "|", "$", "`", '"', "<", ">", "\n", "\r"]
    for char in forbidden:
        if char in path:
            raise ValueError(f"invalid character '{char}' detected in disk path: '{path}'")
