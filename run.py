"""Launch from a source checkout without installing the project itself."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

if __name__ == "__main__":
    if "--probe-worker" in sys.argv:
        import json

        from before.probes import worker

        print(json.dumps(worker(json.load(sys.stdin))))
    elif len(sys.argv) > 1 and sys.argv[1] == "cli":
        from before.cli import main

        raise SystemExit(main(sys.argv[2:]))
    else:
        from before.app import main

        main()
