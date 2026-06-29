from .centos_7 import TEMPLATES as centos_7_templates
from .centos_8_stream import TEMPLATES as centos_8_stream_templates
from .centos_9_stream import TEMPLATES as centos_9_stream_templates
from .fedora_39 import TEMPLATES as fedora_39_templates
from .fedora_40 import TEMPLATES as fedora_40_templates
from .rocky_8 import TEMPLATES as rocky_8_templates
from .rocky_9 import TEMPLATES as rocky_9_templates
from .alma_8 import TEMPLATES as alma_8_templates
from .alma_9 import TEMPLATES as alma_9_templates
from .archlinux import TEMPLATES as archlinux_templates
from .opensuse_leap_15 import TEMPLATES as opensuse_leap_15_templates
from .opensuse_tumbleweed import TEMPLATES as opensuse_tumbleweed_templates
from .kali_linux import TEMPLATES as kali_linux_templates
from .parrot_os import TEMPLATES as parrot_os_templates
from .mint_21 import TEMPLATES as mint_21_templates
from .pop_os_22 import TEMPLATES as pop_os_22_templates
from .manjaro import TEMPLATES as manjaro_templates
from .gentoo import TEMPLATES as gentoo_templates
from .slackware import TEMPLATES as slackware_templates
from .void_linux import TEMPLATES as void_linux_templates
from .nixos import TEMPLATES as nixos_templates
from .clear_linux import TEMPLATES as clear_linux_templates
from .photon_os import TEMPLATES as photon_os_templates
from .rhel_9 import TEMPLATES as rhel_9_templates
from .oracle_linux_9 import TEMPLATES as oracle_linux_9_templates
from .alpinelinux_edge import TEMPLATES as alpinelinux_edge_templates
from .talos_linux import TEMPLATES as talos_linux_templates
from .coreos import TEMPLATES as coreos_templates
from .ubuntu_22_04 import TEMPLATES as ubuntu_22_04_templates
from .ubuntu_20_04 import TEMPLATES as ubuntu_20_04_templates

from .alpine import TEMPLATES as alpine_templates
from .ubuntu import TEMPLATES as ubuntu_templates
from .debian import TEMPLATES as debian_templates

TEMPLATES = alpine_templates + ubuntu_templates + debian_templates + \
    centos_7_templates\
    + centos_8_stream_templates\
    + centos_9_stream_templates\
    + fedora_39_templates\
    + fedora_40_templates\
    + rocky_8_templates\
    + rocky_9_templates\
    + alma_8_templates\
    + alma_9_templates\
    + archlinux_templates\
    + opensuse_leap_15_templates\
    + opensuse_tumbleweed_templates\
    + kali_linux_templates\
    + parrot_os_templates\
    + mint_21_templates\
    + pop_os_22_templates\
    + manjaro_templates\
    + gentoo_templates\
    + slackware_templates\
    + void_linux_templates\
    + nixos_templates\
    + clear_linux_templates\
    + photon_os_templates\
    + rhel_9_templates\
    + oracle_linux_9_templates\
    + alpinelinux_edge_templates\
    + talos_linux_templates\
    + coreos_templates\
    + ubuntu_22_04_templates\
    + ubuntu_20_04_templates
