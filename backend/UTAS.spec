# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas_crypto, binaries_crypto, hiddenimports_crypto = collect_all('cryptography')
datas_oracle, binaries_oracle, hiddenimports_oracle = collect_all('oracledb')

base_hidden = [
    'auth_helper',
    'uvicorn',
    'fastapi',
    'psycopg2',
    'passlib.handlers.bcrypt',
    'bcrypt',
    'cryptography.hazmat.primitives.ciphers.aead',
]
all_hidden = list(set(base_hidden + hiddenimports_crypto + hiddenimports_oracle))
all_datas = datas_crypto + datas_oracle
all_binaries = binaries_crypto + binaries_oracle

a = Analysis(
    ['app\\main.py'],
    pathex=[],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hidden,
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
    name='UTAS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
