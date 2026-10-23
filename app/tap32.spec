# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: Tap32.exe (jeden plik, bez konsoli). Budowanie: build_exe.ps1

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = [
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
    "comtypes.stream",
    "win32timezone",
    *collect_submodules("pycaw"),
    *collect_submodules("tap32"),
]

a = Analysis(
    ["tap32/__main__.py"],
    pathex=["."],
    binaries=[],
    datas=[("tap32/assets", "tap32/assets")],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore", "PySide6.QtQuick", "PySide6.QtQml"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Tap32",
    icon="tap32/assets/tap32.ico",
    console=False,
    debug=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
)
