# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parent
    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from solaris.web_app import main as web_main

    return int(web_main(sys.argv[1:]) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
