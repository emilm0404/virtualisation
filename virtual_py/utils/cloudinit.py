import os
from io import BytesIO
from typing import List, Optional
import pycdlib


def create_cidata_iso(
    output_path: str,
    hostname: str,
    username: str = "admin",
    password: Optional[str] = None,
    ssh_keys: Optional[List[str]] = None,
    shell_commands: Optional[List[str]] = None,
    raw_user_data: Optional[str] = None,
) -> None:
    # 1. generate the metadata file containing local hostname and ID.
    meta_data = f"instance-id: i-{hostname}\nlocal-hostname: {hostname}\n"

    # 2. generate or use the raw user-data
    if raw_user_data:
        user_data = raw_user_data
    else:
        user_data = "#cloud-config\n"
        user_data += "users:\n"
        user_data += f"  - name: {username}\n"
        if password:
            # stores the plaintext password. in production, pre-hashed keys are preferred.
            user_data += f"    passwd: {password}\n"
            user_data += "    lock_passwd: false\n"
        user_data += "    sudo: ['ALL=(ALL) NOPASSWD:ALL']\n"
        user_data += "    shell: /bin/bash\n"
    
        if ssh_keys:
            user_data += "    ssh_authorized_keys:\n"
            for key in ssh_keys:
                user_data += f"      - {key}\n"
    
        if shell_commands:
            user_data += "runcmd:\n"
            for cmd in shell_commands:
                user_data += f"  - {cmd}\n"

    # 3. package these into a standard ISO-9660 filesystem image.
    iso = pycdlib.PyCdlib()
    iso.new(interchange_level=1, joliet=True, vol_ident="cidata")

    # we encode to raw bytes before loading into pycdlib buffer.
    ud_bytes = user_data.encode("utf-8")
    iso.add_fp(
        BytesIO(ud_bytes),
        len(ud_bytes),
        "/USERDATA.;1",
        rr_name="user-data",
        joliet_path="/user-data"
    )

    md_bytes = meta_data.encode("utf-8")
    iso.add_fp(
        BytesIO(md_bytes),
        len(md_bytes),
        "/METADATA.;1",
        rr_name="meta-data",
        joliet_path="/meta-data"
    )

    iso.write(output_path)
    iso.close()
