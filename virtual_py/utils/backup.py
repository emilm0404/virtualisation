import os
import sys
import shutil
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from virtual_py import get_provider

async def create_backup(vm_name: str, output_path: str):
    provider = get_provider()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        vm_export_dir = os.path.join(tmpdir, "export")
        os.makedirs(vm_export_dir, exist_ok=True)
        
        # export the vm settings and metadata.
        await provider.export_vm(vm_name, vm_export_dir)
        
        # on linux/kvm we also need to copy the disk images.
        if sys.platform != "win32":
            xml_file = os.path.join(vm_export_dir, f"{vm_name}.xml")
            if os.path.exists(xml_file):
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                # find all disk image source files in the xml.
                for source in root.findall(".//devices/disk/source"):
                    file_path = source.get("file")
                    if file_path and os.path.exists(file_path):
                        # copy disk file to export directory.
                        shutil.copy2(file_path, vm_export_dir)
        
        # pack the export folder into a tarball.
        with tarfile.open(output_path, "w:gz") as tar:
            tar.add(vm_export_dir, arcname=os.path.basename(vm_export_dir))
