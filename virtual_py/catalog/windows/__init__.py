from .win_server_2022 import TEMPLATES as win_server_2022_templates
from .win_server_2019 import TEMPLATES as win_server_2019_templates
from .win10_eval import TEMPLATES as win10_eval_templates
from .win11_arm import TEMPLATES as win11_arm_templates

from .windows_11 import TEMPLATES as windows_11_templates

TEMPLATES = windows_11_templates + \
    win_server_2022_templates\
    + win_server_2019_templates\
    + win10_eval_templates\
    + win11_arm_templates
