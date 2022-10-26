# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

if __name__ == "__main__":
    import sys

    if sys.version_info >= (3, 8):
        from importlib.metadata import distribution
    else:
        from importlib_metadata import distribution

    ep_name = "trial"
    dist = distribution("twisted")
    for ep in dist.entry_points:
        if ep.group == "console_scripts" and ep.name == ep_name:
            trial = ep
            break
    else:
        raise OSError(f"No console_scripts entry point found for: {ep_name}")

    sys.exit(trial.load()())
