"""Bake verdicts.json into a standalone index.html (opens offline, no server).

    python website/demo/build.py
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    template = (HERE / "template.html").read_text(encoding="utf-8")
    data = json.loads((HERE / "verdicts.json").read_text(encoding="utf-8"))
    # Compact JSON; escape "</" so no string can close the inline <script>.
    payload = json.dumps(data, separators=(",", ":")).replace("</", r"<\/")
    if template.count("__VERDICTS__") != 1:
        raise SystemExit("template.html must contain exactly one __VERDICTS__ placeholder")
    (HERE / "index.html").write_bytes(template.replace("__VERDICTS__", payload).encode("utf-8"))
    print(f"wrote {HERE / 'index.html'}")


if __name__ == "__main__":
    main()
