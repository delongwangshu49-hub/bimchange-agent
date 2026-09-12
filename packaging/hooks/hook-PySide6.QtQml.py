"""Collect QtQml's native dependencies, not the unrelated QML import catalog.

The application uses QtWidgets + QWebEngineView with packaged HTML/JavaScript,
not a QQmlApplicationEngine or any QML documents. Keep PyInstaller's native
dependency discovery; omit its blanket collect_qtqml_files() extra. Frozen
WebEngine tests are mandatory before accepting a package built with this hook.
"""
from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [(source, destination) for source, destination in binaries
            if "qmltooling" not in destination.replace("\\", "/").split("/")]
