The ``all_non_platform`` extra has been renamed to ``all``,
with the former name being a compatibility alias.  Platform-specific extras
such as ``macos_platform`` and ``windows_platform`` have also been deprecated;
their dependencies have been moved into the ``all`` extra with appropriate
environment markers.  Optional dependencies in ``all`` are now also included
in ``dev`` for convenience.
