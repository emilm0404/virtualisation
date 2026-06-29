import pytest
import os
from unittest.mock import patch, MagicMock
from virtual_py.utils.sysprep import create_unattend_iso

def test_create_unattend_iso_raw():
    with patch("virtual_py.utils.sysprep.pycdlib.PyCdlib") as mock_pycdlib:
        mock_iso = MagicMock()
        mock_pycdlib.return_value = mock_iso

        create_unattend_iso(
            output_path="/fake/unattend.iso",
            hostname="myhost",
            admin_password="mypassword",
            raw_unattend_xml="<test>raw_xml</test>"
        )

        mock_iso.new.assert_called_once_with(interchange_level=1, joliet=True, vol_ident="UNATTEND")
        
        # Verify add_fp was called correctly
        args, kwargs = mock_iso.add_fp.call_args
        assert len(args[0].getvalue()) > 0
        assert b"<test>raw_xml</test>" in args[0].getvalue()
        assert kwargs["rr_name"] == "autounattend.xml"

        mock_iso.write.assert_called_once_with("/fake/unattend.iso")
        mock_iso.close.assert_called_once()

def test_create_unattend_iso_template():
    with patch("virtual_py.utils.sysprep.pycdlib.PyCdlib") as mock_pycdlib:
        mock_iso = MagicMock()
        mock_pycdlib.return_value = mock_iso

        create_unattend_iso(
            output_path="/fake/unattend2.iso",
            hostname="myhost",
            admin_password="mypassword123"
        )

        args, kwargs = mock_iso.add_fp.call_args
        content = args[0].getvalue().decode("utf-8")
        
        assert "myhost" in content
        assert "mypassword123" in content
        assert "Enable-PSRemoting" in content
