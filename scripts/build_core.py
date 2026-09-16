"""Export the identical bundled Core as a standalone source ZIP and wheel.

Only pure core modules are packaged. The manifest binds files and source commit;
consumers must verify its trusted commit/release and SHA256 before importing.
"""
from __future__ import annotations
import argparse
import base64
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / 'custom_components' / 'lotto_645' / 'lotto_core'


def write_zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            out.writestr(info, data)


def build(destination: Path, commit: str = 'working-tree') -> dict:
    if commit != 'working-tree' and not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Expected immutable 40-character Git commit')
    destination.mkdir(parents=True, exist_ok=True)
    init = (CORE/'__init__.py').read_text()
    version = re.search(r'CORE_VERSION = "([0-9.]+)"', init).group(1)
    manifest_ha = json.loads((CORE.parent/'manifest.json').read_text())
    if manifest_ha['version'] != version:
        raise ValueError('HA and Core versions differ')
    files = {f'lotto_core/{p.relative_to(CORE).as_posix()}': p.read_bytes()
             for p in sorted(CORE.rglob('*'))
             if p.is_file() and p.suffix in {'.py', '.json'} and '__pycache__' not in p.parts}
    requirements = [*manifest_ha['requirements'], "tzdata==2025.2; sys_platform == 'win32'"]
    file_hashes = {name: sha256(data).hexdigest() for name,data in files.items()}
    manifest = {'schema_version':1, 'api_version':1, 'core_version':version,
                'repository':'1bobby-git/HA-Lotto-645', 'source_commit':commit,
                'package':'lotto-645-core', 'entrypoint':'lotto_core.api:generate_json',
                'requires_python':'>=3.11', 'requirements':requirements,
                'files':file_hashes}
    manifest_bytes=(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
    license_bytes=(ROOT/'LICENSE').read_bytes()
    readme=(ROOT/'docs/CORE_API.md').read_bytes()
    # Source archive is directly importable and pip-installable; no HA parent package.
    project='''[build-system]\nrequires = ["setuptools>=68"]\nbuild-backend = "setuptools.build_meta"\n[project]\nname = "lotto-645-core"\nversion = "'''+version+'''"\nrequires-python = ">=3.11"\ndependencies = '''+json.dumps(requirements)+'''\n[project.scripts]\nlotto-core = "lotto_core.cli:main"\n[tool.setuptools.packages.find]\ninclude = ["lotto_core*"]\n'''
    source={**files,'core-manifest.json':manifest_bytes,'LICENSE':license_bytes,'README.md':readme,'pyproject.toml':project.encode()}
    source_path=destination/f'lotto-core-{version}.zip';write_zip(source_path,source)
    # PEP 427 pure-Python wheel. RECORD hashes and sizes cover every installed file.
    dist=f'lotto_645_core-{version}.dist-info'
    metadata=f'Metadata-Version: 2.1\nName: lotto-645-core\nVersion: {version}\nSummary: Standalone generation core shared with HA-Lotto-645\nRequires-Python: >=3.11\nLicense: MIT\n'
    metadata+=''.join(f'Requires-Dist: {req}\n' for req in requirements)
    wheel={**files,f'{dist}/METADATA':metadata.encode(),f'{dist}/WHEEL':b'Wheel-Version: 1.0\nGenerator: lotto-core-export\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
           f'{dist}/entry_points.txt':b'[console_scripts]\nlotto-core = lotto_core.cli:main\n',
           f'{dist}/LICENSE':license_bytes,f'{dist}/core-manifest.json':manifest_bytes}
    record=io.StringIO(newline='');writer=csv.writer(record,lineterminator='\n')
    for name,data in sorted(wheel.items()):
        digest=base64.urlsafe_b64encode(sha256(data).digest()).rstrip(b'=').decode()
        writer.writerow([name,'sha256='+digest,str(len(data))])
    writer.writerow([f'{dist}/RECORD','','']);wheel[f'{dist}/RECORD']=record.getvalue().encode()
    wheel_path=destination/f'lotto_645_core-{version}-py3-none-any.whl';write_zip(wheel_path,wheel)
    (destination/'lotto-core-manifest.json').write_bytes(manifest_bytes)
    outputs=[source_path,wheel_path,destination/'lotto-core-manifest.json']
    (destination/'SHA256SUMS.txt').write_text(''.join(f'{sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in outputs))
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'dist')
    parser.add_argument('--commit',default='working-tree')
    args=parser.parse_args()
    print(json.dumps(build(args.output,args.commit),ensure_ascii=False))
