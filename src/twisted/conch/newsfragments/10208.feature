twisted.conch.ssh now has an alternative Ed25519 implementation using PyNaCl, in order to support platforms that lack OpenSSL >= 1.1.1b.  The new "conch_nacl" extra has the necessary dependency.
