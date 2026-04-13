import pytest
import os
import stat
import zipfile
import tarfile
from pathlib import Path
from vibehack.toolkit.provisioner import _safe_extract

def test_safe_extract_zip_ignores_symlink_and_dirs(tmp_path):
    archive_path = tmp_path / "test.zip"
    dest_path = tmp_path / "dest"
    dest_path.mkdir()

    with zipfile.ZipFile(archive_path, 'w') as zf:
        # 1. Directory
        dir_info = zipfile.ZipInfo("dir/")
        zf.writestr(dir_info, "")

        # 2. Symlink
        sym_info = zipfile.ZipInfo("symlink_file")
        sym_info.create_system = 3 # UNIX
        sym_info.external_attr = 0xA0000000 | (0o777 << 16)
        zf.writestr(sym_info, "/etc/passwd")

        # 3. Regular file
        reg_info = zipfile.ZipInfo("normal.txt")
        zf.writestr(reg_info, "hello")

    _safe_extract(archive_path, dest_path)

    # Directory 'dir' should not be extracted
    assert not (dest_path / "dir").exists()

    # Symlink should not be extracted
    assert not (dest_path / "symlink_file").exists()

    # Regular file should be extracted
    assert (dest_path / "normal.txt").exists()
    assert (dest_path / "normal.txt").read_text() == "hello"

def test_safe_extract_tar_ignores_symlink(tmp_path):
    archive_path = tmp_path / "test.tar.gz"
    dest_path = tmp_path / "dest"
    dest_path.mkdir()

    with tarfile.open(archive_path, 'w:gz') as tar:
        # 1. Symlink
        sym_info = tarfile.TarInfo("symlink_file")
        sym_info.type = tarfile.SYMTYPE
        sym_info.linkname = "/etc/passwd"
        tar.addfile(sym_info)

        # 2. Regular file
        reg_info = tarfile.TarInfo("normal.txt")
        reg_info.size = 5
        import io
        tar.addfile(reg_info, io.BytesIO(b"hello"))

    _safe_extract(archive_path, dest_path)

    # Symlink should not be extracted
    assert not (dest_path / "symlink_file").exists()

    # Regular file should be extracted
    assert (dest_path / "normal.txt").exists()
    assert (dest_path / "normal.txt").read_text() == "hello"
