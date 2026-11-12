import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Qt is deliberately imported only by UI tests; all engine/CLI tests work with
# a plain Python interpreter and no Qt dependency.
sys.dont_write_bytecode = True
