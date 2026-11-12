# Third-party components

BEFORE application source is MIT licensed (see LICENSE).

The desktop interface uses PySide6 / Shiboken6 and Qt 6.8.3, copyright The Qt
Company Ltd and contributors, available under LGPLv3 / GPLv3 / commercial terms.
This project uses the LGPLv3 option for the Essentials components. The native
portable build keeps their shared libraries as separate files in `_internal`.
The LGPLv3 text is included in `licenses/LGPL-3.0.txt`; GPLv3 (incorporated by
LGPLv3) is included in `licenses/GPL-3.0.txt`.

- PySide sources and license information: https://code.qt.io/cgit/pyside/pyside-setup.git/
- Qt 6.8.3 source archives: https://download.qt.io/official_releases/qt/6.8/6.8.3/
- Qt licensing: https://www.qt.io/licensing/open-source-lgpl-obligations
- Python runtime: https://docs.python.org/3/license.html
- PyInstaller bootloader licensing and exception: https://pyinstaller.org/en/stable/license.html

Portable releases include Python and library notices in `licenses/` and
PyInstaller's collected distribution metadata. Operating-system libraries keep
their upstream licenses. Application icons are original SVG geometry, included
under this repository's MIT license. No external fonts or stock graphics are
bundled.

To replace Qt/PySide, use the source distribution, install a compatible build in
an ordinary virtual environment and run `python run.py`, or rebuild the portable
folder with `python scripts/build.py`. No signature or anti-tamper check prevents
modifying the source or replacing the shared libraries.
