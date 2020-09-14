# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


class Enum:
    group = None  # type: str

    def __init__(self, label):
        self.label = label

    def __repr__(self) -> str:
        return "<%s: %s>" % (self.group, self.label)

    def __str__(self) -> str:
        return self.label


class StatusEnum(Enum):
    group = "Status"


OFFLINE = Enum("Offline")
ONLINE = Enum("Online")
AWAY = Enum("Away")


class OfflineError(Exception):
    """The requested action can't happen while offline."""
