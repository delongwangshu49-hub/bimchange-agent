"""PyInstaller entry point for the Windows desktop preview."""

from bimchange_agent.desktop_app import main


if __name__ == "__main__":
    raise SystemExit(main())
