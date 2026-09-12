"""Native desktop input; no bundled virtual keyboard or tablet TUIO server."""
from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [(source, destination) for source, destination in binaries
            if not {"platforminputcontexts", "generic"}.intersection(
                destination.replace("\\", "/").split("/"))]
