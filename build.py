#!/usr/bin/env python3
"""Build script for OpenHands Server using PyInstaller."""

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Main build function."""
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # Check if PyInstaller is available
    try:
        subprocess.run(["pyinstaller", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("PyInstaller not found. Please install it with:")
        print("  uv add --dev pyinstaller")
        print("  or run: ./build.sh --install-pyinstaller")
        sys.exit(1)

    # Build the executable
    spec_file = "openhands-server.spec"
    if not Path(spec_file).exists():
        print(f"Creating {spec_file}...")
        create_spec_file(spec_file)

    print("Building executable with PyInstaller...")
    try:
        subprocess.run(["pyinstaller", spec_file], check=True)
        print("Build successful!")

        # Test the executable
        test_executable()

    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        sys.exit(1)


def create_spec_file(spec_file: str) -> None:
    """Create a basic PyInstaller spec file."""
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['openhands_server/sdk_server/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'openhands_server',
        'fastapi',
        'uvicorn',
        'websockets',
        'pydantic',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='openhands-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"""

    with open(spec_file, "w") as f:
        f.write(spec_content)


def test_executable() -> None:
    """Test the built executable."""
    executable_path = Path("dist/openhands-server")
    if not executable_path.exists():
        print("Executable not found at dist/openhands-server")
        sys.exit(1)

    print("Testing executable...")
    try:
        # Test with --help flag
        result = subprocess.run(
            [str(executable_path), "--help"], capture_output=True, text=True, timeout=10
        )

        if result.returncode == 0:
            print("Executable test passed!")
        else:
            print(f"Executable test failed with return code {result.returncode}")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr}")
            sys.exit(1)

    except subprocess.TimeoutExpired:
        print("Executable test timed out")
        sys.exit(1)
    except Exception as e:
        print(f"Executable test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
