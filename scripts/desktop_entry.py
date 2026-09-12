"""PyInstaller entry point for the Windows desktop preview."""

import sys


if __name__ == "__main__":
    if "--r4-scene-worker" in sys.argv:
        from bimchange_agent.r4_scene_worker import main
    elif "--smoke-r4" in sys.argv:
        from bimchange_agent.r4_smoke import main
    else:
        from bimchange_agent.desktop_app import main
    raise SystemExit(main())
