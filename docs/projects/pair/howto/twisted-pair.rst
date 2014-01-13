
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Twisted Pair: Low-level Networking
==================================





Twisted can do low-level networking, too.




Here's an example that tries to show the relationships of different
classes and how data could flow for receiving packets.





::

    
    FileWrapper
       |
       v
    PcapProtocol  TuntapPort
       |            |
       +------------+
       v
    EthernetProtocol
       |
       +------------+-----------+---...
       v            v           v
    IPProtocol    ARPProtocol  IPv6Protocol
       |
       +-------------+----------------+---...
       v             v                v
    RawUDPProtocol  RawICMPProtocol  RawTCPProtocol
       |
       v
    DatagramProtocol




Of course, for writing, the picture would look pretty much
identical, except all arrows would be reversed.





Overview of classes
-------------------



TODO





Transports
~~~~~~~~~~



TODO





- TuntapPort: TODO






Protocols
~~~~~~~~~



TODO





- EthernetProtocol: TODO
- IPProtocol: TODO
- RawUDPProtocol: TODO






Interfaces
~~~~~~~~~~



TODO





- IRawDatagramProtocol: TODO
- IRawPacketProtocol: TODO




