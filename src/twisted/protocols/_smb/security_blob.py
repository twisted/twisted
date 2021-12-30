# -*- test-case-name: twisted.protocols._smb.tests -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""Implement the "security buffer" an intricate sub-protocol
used for authentication

Blobs implemented as DER-encoded ASN.1 objects
which in turn encapsulate NTLMv2 challenge-response authentication


much of code adapted from Mike Teo's pysmb """

from typing import cast, Optional

from pyasn1.codec.der import decoder, encoder  # type: ignore
from pyasn1.type import char, constraint, namedtype, namedval, tag, univ  # type: ignore

from twisted.logger import Logger
from twisted.protocols._smb import _base, ntlm

log = Logger()


class BlobManager:
    """
    encapsulates the authentication negotiation state
    callers just send blobs in and out and get a credential

    Currently just wraps a NTLMManager and the whole "Matroska doll" design
    may look silly, but different authentication mechanisms
    may be added over time
    """

    def __init__(self, domain: str) -> None:
        """
        @param domain: the server NetBIOS domain
        @type domain: L{str}
        """
        self.domain = domain

    def generateInitialBlob(self) -> bytes:
        """
        generate greeting blob, fixed data essentially an advertisement
        we only support NTLM

        @rtype: L{bytes}
        """
        mech_types = MechTypeList().subtype(
            explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0)
        )
        mech_types.setComponentByPosition(
            0, univ.ObjectIdentifier("1.3.6.1.4.1.311.2.2.10")
        )

        hints = NegHints().subtype(
            explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 3)
        )
        hints.setComponentByName(
            "hintName",
            char.GeneralString(b"not_defined_in_RFC4178@please_ignore").subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0)
            ),
        )

        n = NegTokenInit2().subtype(
            explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0)
        )
        n.setComponentByName("mechTypes", mech_types)
        n.setComponentByName("negHints", hints)

        nt = NegotiationToken()
        nt.setComponentByName("negTokenInit", n)

        ct = ContextToken()
        ct.setComponentByName("thisMech", univ.ObjectIdentifier("1.3.6.1.5.5.2"))
        ct.setComponentByName("innerContextToken", nt)

        return cast(bytes, encoder.encode(ct))

    def receiveInitialBlob(self, blob: bytes) -> None:
        """
        process first blob from client

        @type blob: L{bytes}
        """
        d, _ = decoder.decode(blob, asn1Spec=ContextToken())
        nt = d.getComponentByName("innerContextToken")
        n = nt.getComponentByName("negTokenInit")
        token = n.getComponentByName("mechToken")
        self.manager = ntlm.NTLMManager(self.domain)
        if token:
            self.manager.receiveToken(token.asOctets())
        else:
            log.warn("initial security blob has no token data.")

    def receiveResp(self, blob: bytes) -> None:
        """
        process subsequent blobs from the client

        @type blob: L{bytes}
        """
        d, _ = decoder.decode(blob, asn1Spec=NegotiationToken())
        nt = d.getComponentByName("negTokenResp")
        token = nt.getComponentByName("responseToken")
        if not token:
            raise _base.SMBError("security blob does not contain responseToken field")
        self.manager.receiveToken(token.asOctets())

    def generateChallengeBlob(self) -> bytes:
        """
        generates a blob response once initial negotiation is complete

        @rtype: L{bytes}
        """
        ntlm_data = self.manager.getChallengeToken()

        response_token = univ.OctetString(ntlm_data).subtype(
            explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2)
        )
        n = NegTokenResp().subtype(
            explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 1)
        )
        n.setComponentByName("responseToken", response_token)
        n.setComponentByName(
            "supportedMech",
            univ.ObjectIdentifier("1.3.6.1.4.1.311.2.2.10").subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1)
            ),
        )
        n.setComponentByName("negResult", RESULT_ACCEPT_INCOMPLETE)
        nt = NegotiationToken()
        nt.setComponentByName("negTokenResp", n)

        return cast(bytes, encoder.encode(nt))

    def generateAuthResponseBlob(self, login_status: bool) -> bytes:
        """
        generate the final blob indicating login status

        @param login_status: C{True} if successful login
        @type login_status: L{bool}
        """
        if login_status:
            result = RESULT_ACCEPT_COMPLETED
        else:
            result = RESULT_REJECT
        n = NegTokenResp().subtype(
            explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 1)
        )
        n.setComponentByName("negResult", result)
        nt = NegotiationToken()
        nt.setComponentByName("negTokenResp", n)

        return cast(bytes, encoder.encode(nt))

    @property
    def credential(self) -> Optional[ntlm.NTLMCredential]:
        return self.manager.credential


#
# GSS-API ASN.1 (RFC2478 section 3.2.1)
#

RESULT_ACCEPT_COMPLETED = 0
RESULT_ACCEPT_INCOMPLETE = 1
RESULT_REJECT = 2


class NegResultEnumerated(univ.Enumerated):
    namedValues = namedval.NamedValues(
        ("accept_completed", 0), ("accept_incomplete", 1), ("reject", 2)
    )
    subtypeSpec = univ.Enumerated.subtypeSpec + constraint.SingleValueConstraint(
        0, 1, 2
    )


class MechTypeList(univ.SequenceOf):
    componentType = univ.ObjectIdentifier()


class ContextFlags(univ.BitString):
    namedValues = namedval.NamedValues(
        ("delegFlag", 0),
        ("mutualFlag", 1),
        ("replayFlag", 2),
        ("sequenceFlag", 3),
        ("anonFlag", 4),
        ("confFlag", 5),
        ("integFlag", 6),
    )


class NegTokenInit(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.OptionalNamedType(
            "mechTypes",
            MechTypeList().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0)
            ),
        ),
        namedtype.OptionalNamedType(
            "reqFlags",
            ContextFlags().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 1)
            ),
        ),
        namedtype.OptionalNamedType(
            "mechToken",
            univ.OctetString().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 2)
            ),
        ),
        namedtype.OptionalNamedType(
            "mechListMIC",
            univ.OctetString().subtype(
                implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 3)
            ),
        ),
    )


class NegHints(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.OptionalNamedType(
            "hintName",
            char.GeneralString().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0)
            ),
        ),
        namedtype.OptionalNamedType(
            "hintAddress",
            univ.OctetString().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 1)
            ),
        ),
    )


class NegTokenInit2(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.OptionalNamedType(
            "mechTypes",
            MechTypeList().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0)
            ),
        ),
        namedtype.OptionalNamedType(
            "reqFlags",
            ContextFlags().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 1)
            ),
        ),
        namedtype.OptionalNamedType(
            "mechToken",
            univ.OctetString().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 2)
            ),
        ),
        namedtype.OptionalNamedType(
            "negHints",
            NegHints().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 3)
            ),
        ),
        namedtype.OptionalNamedType(
            "mechListMIC",
            univ.OctetString().subtype(
                implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 4)
            ),
        ),
    )


class NegTokenResp(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.OptionalNamedType(
            "negResult",
            NegResultEnumerated().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0)
            ),
        ),
        namedtype.OptionalNamedType(
            "supportedMech",
            univ.ObjectIdentifier().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 1)
            ),
        ),
        namedtype.OptionalNamedType(
            "responseToken",
            univ.OctetString().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 2)
            ),
        ),
        namedtype.OptionalNamedType(
            "mechListMIC",
            univ.OctetString().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 3)
            ),
        ),
    )


class NegotiationToken(univ.Choice):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType(
            "negTokenInit",
            NegTokenInit().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0)
            ),
        ),
        namedtype.NamedType(
            "negTokenResp",
            NegTokenResp().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 1)
            ),
        ),
    )


class ContextToken(univ.Sequence):
    tagSet = univ.Sequence.tagSet.tagImplicitly(
        tag.Tag(tag.tagClassApplication, tag.tagFormatConstructed, 0)
    )
    componentType = namedtype.NamedTypes(
        namedtype.NamedType("thisMech", univ.ObjectIdentifier()),
        namedtype.NamedType("innerContextToken", NegotiationToken()),
    )
