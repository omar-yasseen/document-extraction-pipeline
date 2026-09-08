"""
One command that runs the whole thing, for demos and first-time users.

    python demo.py

Processes samples/, prints the routing decisions, then opens the review queue
in your browser. No second command, no copying a localhost URL.

The individual scripts (extract.py, run.py, review.py) still exist and are
still the real interface - this just removes the friction from the thirty
seconds when someone is watching.
"""

import threading
import webbrowser

import run as pipeline
from review import OUT, app

URL = "http://127.0.0.1:5000"


def main() -> int:
    print("=" * 62)
    print("  Invoice extraction pipeline")
    print("=" * 62)
    print()

    # Reuse the batch runner exactly as-is rather than duplicating its logic.
    import sys
    sys.argv = ["run.py", "samples"]
    code = pipeline.main()
    if code != 0:
        return code

    print()
    print("=" * 62)
    print(f"  Opening the review queue at {URL}")
    print("  Press ctrl-c to stop.")
    print("=" * 62)
    print()

    OUT.mkdir(exist_ok=True)
    # Fire the browser once the server has had a moment to bind the port.
    threading.Timer(1.2, lambda: webbrowser.open(URL)).start()
    app.run(port=5000, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
