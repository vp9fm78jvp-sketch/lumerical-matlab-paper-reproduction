#!/usr/bin/env python3
"""Install the complete skill directory locally, without bundling commercial tools."""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    source=Path(__file__).resolve().parents[1]
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target',default=str(Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'skills'/source.name))
    p.add_argument('--install-dependencies',action='store_true')
    a=p.parse_args();dest=Path(a.target).expanduser().resolve()
    if dest!=source:
        if dest.exists():p.error('Target already exists; choose another target or update it through git')
        if dest.is_relative_to(source):p.error('Target cannot be inside the source tree')
        shutil.copytree(source,dest,ignore=shutil.ignore_patterns('.git','__pycache__','.pytest_cache','.venv','*.egg-info','work'))
    if a.install_dependencies:subprocess.run([sys.executable,'-m','pip','install','-e',str(dest)],check=True)
    print('Installed skill directory:',dest)
    print('Load SKILL.md in your Agent Skills host. Commercial software/licenses are separate.')
    return 0
if __name__=='__main__':raise SystemExit(main())
