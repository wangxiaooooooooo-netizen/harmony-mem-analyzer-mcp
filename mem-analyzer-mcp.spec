# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = ['fastmcp', 'fastmcp.server', 'fastmcp.client', 'fastmcp.tools', 'fastmcp.resources', 'fastmcp.prompts', 'starlette', 'starlette.applications', 'starlette.routing', 'starlette.middleware', 'uvicorn', 'uvicorn.main', 'uvicorn.config', 'pydantic', 'pydantic.v1', 'pydantic_core', 'rich', 'rich.console', 'rich.text', 'rich.logging', 'typer', 'click', 'shellingham', 'typing_extensions', 'annotated_types']
tmp_ret = collect_all('fastmcp')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('starlette')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('uvicorn')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['/Users/wangdefu/Documents/projects/VibeCodingAI/baseline/mcp/mcp_server/main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'IPython', 'jupyter', 'pytest', 'setuptools', 'pip', 'wheel', 'virtualenv', 'networkx', 'bs4', 'beautifulsoup4', 'sqlite3', 'email_validator', 'jsonschema', 'referencing', 'rpds_py'],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [('O', None, 'OPTION'), ('O', None, 'OPTION')],
    name='mem-analyzer-mcp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity='',
    entitlements_file=None,
)
