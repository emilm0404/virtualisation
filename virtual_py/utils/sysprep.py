import os
from io import BytesIO
from typing import Optional
import pycdlib

def create_unattend_iso(
    output_path: str,
    hostname: str,
    admin_password: str,
    raw_unattend_xml: Optional[str] = None
) -> None:
    """
    Creates an ISO containing an autounattend.xml file for Windows Sysprep.
    """
    if raw_unattend_xml:
        xml_content = raw_unattend_xml
    else:
        # Base template for bypassing OOBE and setting local administrator password
        xml_content = f"""<?xml version="1.0" encoding="utf-8"?>
<unattend xmlns="urn:schemas-microsoft-com:unattend">
    <settings pass="oobeSystem">
        <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <OOBE>
                <HideEULAPage>true</HideEULAPage>
                <HideLocalAccountScreen>true</HideLocalAccountScreen>
                <HideOEMRegistrationScreen>true</HideOEMRegistrationScreen>
                <HideOnlineAccountScreens>true</HideOnlineAccountScreens>
                <HideWirelessSetupInOOBE>true</HideWirelessSetupInOOBE>
                <NetworkLocation>Work</NetworkLocation>
                <ProtectYourPC>1</ProtectYourPC>
            </OOBE>
            <UserAccounts>
                <AdministratorPassword>
                    <Value>{admin_password}</Value>
                    <PlainText>true</PlainText>
                </AdministratorPassword>
            </UserAccounts>
            <AutoLogon>
                <Password>
                    <Value>{admin_password}</Value>
                    <PlainText>true</PlainText>
                </Password>
                <Enabled>true</Enabled>
                <LogonCount>1</LogonCount>
                <Username>Administrator</Username>
            </AutoLogon>
            <FirstLogonCommands>
                <SynchronousCommand wcm:action="add">
                    <CommandLine>cmd.exe /c powershell -Command "Enable-PSRemoting -SkipNetworkProfileCheck -Force"</CommandLine>
                    <Description>Enable WinRM</Description>
                    <Order>1</Order>
                </SynchronousCommand>
                <SynchronousCommand wcm:action="add">
                    <CommandLine>cmd.exe /c powershell -Command "Set-NetFirewallRule -DisplayGroup 'Windows Remote Management' -Enabled True -Profile Any"</CommandLine>
                    <Description>Enable WinRM Firewall</Description>
                    <Order>2</Order>
                </SynchronousCommand>
            </FirstLogonCommands>
        </component>
    </settings>
    <settings pass="specialize">
        <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <ComputerName>{hostname[:15]}</ComputerName>
        </component>
    </settings>
</unattend>
"""

    iso = pycdlib.PyCdlib()
    iso.new(interchange_level=1, joliet=True, vol_ident="UNATTEND")

    xml_bytes = xml_content.encode("utf-8")
    iso.add_fp(
        BytesIO(xml_bytes),
        len(xml_bytes),
        "/AUTOUNATTEND.XML;1",
        rr_name="autounattend.xml",
        joliet_path="/autounattend.xml"
    )

    iso.write(output_path)
    iso.close()
