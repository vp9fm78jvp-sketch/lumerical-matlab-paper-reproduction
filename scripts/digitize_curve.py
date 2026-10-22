#!/usr/bin/env python3
"""CLI convenience entry point for digitize; use --help for its real arguments."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paper_repro.cli import main
if __name__=='__main__':raise SystemExit(main(['digitize']+sys.argv[1:]))
