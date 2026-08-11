"""PyInstaller entry point for the Windows portable build."""

from __future__ import annotations

from ghdl_studio.app import main

if __name__ == "__main__":
    raise SystemExit(main())
