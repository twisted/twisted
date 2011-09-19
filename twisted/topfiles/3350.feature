twisted.protocols.portforward now uses flow control between its client and server connections to avoid having to buffer an unbounded amount of data when one connection is slower than the other.
