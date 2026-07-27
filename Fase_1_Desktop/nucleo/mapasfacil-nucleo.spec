# -*- mode: python ; coding: utf-8 -*-
"""Empacota o sidecar em `dist/mapasfacil-nucleo/` (onedir).

O electron-builder copia essa pasta para `resources/nucleo` do instalador
(ver `extraResources` em `Fase_1_Desktop/app/package.json`).

    cd Fase_1_Desktop/nucleo
    .venv/Scripts/python.exe -m PyInstaller mapasfacil-nucleo.spec --noconfirm

`shared/` fica ao lado do executável porque `config.raiz_repositorio()` usa
`sys.executable` quando congelado.
"""

from pathlib import Path

# SPECPATH = Fase_1_Desktop/nucleo → parents[1] é a raiz do monorepo.
RAIZ = Path(SPECPATH).resolve().parents[1]
SHARED = RAIZ / "shared"

# Só o que o núcleo lê em runtime. `bases/ibge` entra porque o minimapa T1
# resolve o município a partir dele.
dados_shared = [
    (str(SHARED / "catalog"), "shared/catalog"),
    (str(SHARED / "schemas"), "shared/schemas"),
    (str(SHARED / "galeria"), "shared/galeria"),
    (str(SHARED / "templates"), "shared/templates"),
    (str(SHARED / "contract_version.json"), "shared"),
]
if (SHARED / "bases").is_dir():
    dados_shared.append((str(SHARED / "bases"), "shared/bases"))

a = Analysis(
    ["mapasfacil_nucleo/__main__.py"],
    pathex=[SPECPATH],
    binaries=[],
    datas=dados_shared,
    # keyring resolve o backend do Windows por plugin: sem o import explícito
    # o cofre some do bundle e as chaves SEMA/DeepSeek não são gravadas.
    hiddenimports=[
        "keyring.backends.Windows",
        "keyring.backends.SecretService",
        "keyring.backends.fail",
        "win32timezone",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "IPython"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="mapasfacil-nucleo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="mapasfacil-nucleo",
)
