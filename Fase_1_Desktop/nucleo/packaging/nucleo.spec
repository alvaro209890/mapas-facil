# -*- mode: python ; coding: utf-8 -*-
# PyInstaller onedir — F1-11. Gerado/consumido por packaging/empacotar.py.
# Não embute arcpy nem Referencias_IMAP. `shared/` é copiado depois do build.

from pathlib import Path

block_cipher = None

# SPECPATH = pasta que contém este .spec (packaging/)
raiz_packaging = Path(SPECPATH).resolve()
raiz_nucleo = raiz_packaging.parent
entrada = raiz_packaging / "entrada.py"

hiddenimports = [
    "mapasfacil_nucleo",
    "mapasfacil_nucleo.__main__",
    "argon2",
    "argon2.low_level",
    "keyring.backends",
    "keyring.backends.Windows",
    "keyring.backends.null",
    "keyring.backends.chainer",
    "jsonschema",
    "ulid",
    "shapely",
    "shapely.geometry",
    "pyproj",
    "shapefile",
    "fitz",
    "matplotlib",
    "matplotlib.backends.backend_agg",
    "openpyxl",
    "PIL",
    "numpy",
    "certifi",
]

a = Analysis(
    [str(entrada)],
    pathex=[str(raiz_nucleo)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "arcpy",
        "tkinter",
        "test",
        "unittest",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="nucleo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="nucleo",
)
