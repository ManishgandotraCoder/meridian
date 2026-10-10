import argparse
import sys
from pathlib import Path

from provision.render import ProvisionError, render_all


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Meridian environment grants and host config.")
    parser.add_argument(
        "--output",
        default="build/environments",
        help="Directory to write per-environment manifests into.",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        written = render_all(root, root / args.output)
    except (ProvisionError, ValueError, OSError) as exc:
        print("provision failed: %s" % exc, file=sys.stderr)
        sys.exit(1)
    for path in written:
        print(path.relative_to(root))


if __name__ == "__main__":
    main()
