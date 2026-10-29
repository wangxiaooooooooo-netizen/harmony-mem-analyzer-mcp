#!/usr/bin/env python3
"""打包发布脚本"""
import shutil
import hashlib
import json
import subprocess
import os

def main():
    binary_path = 'dist/mem-analyzer-mcp'
    version = '0.1.0'
    platform_info = {'system': 'darwin', 'arch': 'x64', 'python': '3.12'}

    pkg_name = f'mem-analyzer-mcp-v{version}-{platform_info["system"]}-{platform_info["arch"]}-pyinstaller'
    pkg_dir = f'dist/{pkg_name}'

    shutil.rmtree(pkg_dir, ignore_errors=True)
    os.makedirs(pkg_dir, exist_ok=True)

    # 复制二进制
    exe_name = os.path.basename(binary_path)
    shutil.copy2(binary_path, os.path.join(pkg_dir, exe_name))

    # 生成校验和
    sha256 = hashlib.sha256(open(binary_path, 'rb').read()).hexdigest()
    with open(os.path.join(pkg_dir, 'SHA256SUMS'), 'w') as f:
        f.write(f'{sha256}  {exe_name}\n')

    # 生成元数据
    build_date = subprocess.run(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ'], capture_output=True, text=True).stdout.strip()
    metadata = {
        'name': 'mem-analyzer-mcp',
        'version': version,
        'platform': platform_info,
        'tool': 'pyinstaller',
        'python': platform_info['python'],
        'sha256': sha256,
        'build_date': build_date,
    }
    with open(os.path.join(pkg_dir, 'metadata.json'), 'w') as f:
        json.dump(metadata, f, indent=2)

    # 打包压缩
    archive = shutil.make_archive(f'dist/{pkg_name}', 'gztar', pkg_dir)
    print(f'发布包已生成: {archive}')

if __name__ == '__main__':
    main()
