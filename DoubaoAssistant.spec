# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# --- 关键修改：同时收集 pvporcupine 和 pvrecorder 的所有依赖 ---

# 1. 收集 pvporcupine (唤醒词引擎)
datas_porcupine, binaries_porcupine, hiddenimports_porcupine = collect_all('pvporcupine')

# 2. 收集 pvrecorder (录音引擎) - 这里是你报错缺失的部分
datas_recorder, binaries_recorder, hiddenimports_recorder = collect_all('pvrecorder')

# 3. 合并所有依赖
all_datas = datas_porcupine + datas_recorder
all_binaries = binaries_porcupine + binaries_recorder
all_hiddenimports = hiddenimports_porcupine + hiddenimports_recorder

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=all_binaries,  # 使用合并后的 binaries
    datas=all_datas + [     # 使用合并后的 datas，加上你自己的资源
        ('.env', '.'),     
        ('data', 'data'),  
    ],
    hiddenimports=all_hiddenimports, # 使用合并后的 hiddenimports
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DoubaoAssistant',
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