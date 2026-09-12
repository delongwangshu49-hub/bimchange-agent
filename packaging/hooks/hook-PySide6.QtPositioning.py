"""WebEngine needs the native positioning DLL, not external GPS providers.

The offline viewer does not request geolocation or read GPS/serial devices.
"""
from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [(source, destination) for source, destination in binaries
            if "position" not in destination.replace("\\", "/").split("/")]
