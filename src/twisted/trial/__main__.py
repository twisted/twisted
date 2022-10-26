# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

if __name__ == "__main__":
    import sys

    if sys.version_info >= (3, 8):
        from importlib.metadata import distribution
    else:
        from importlib_metadata import distribution

    sys.exit(
        next(
            ep
            for ep in distribution("twisted").entry_points
            if (ep.group, ep.name) == ("console_scripts", "trial")
        ).load()()
    )
