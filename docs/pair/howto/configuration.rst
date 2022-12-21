
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Twisted Pair: Device Configuration
==================================






Twisted Pair's Test Suite
-------------------------


    

Certain system configuration is required before the full Twisted Pair test suite can be run.
Without this setup the test suite will lack the permission necessary to access tap and tun devices.
Some tests will still run but the integration tests which verify Twisted Pair can successfully read from and write to real devices will be skipped.


    



The following shell script creates two tun devices and two tap devices and grants permission to use them to whatever user the shell script is run as.
Run it to configure your system so that you can perform a complete run of the Twisted Pair test suite.


    





.. code-block:: console

    # Needs to be short enough so that with prefix and suffix, fits into 16 bytes
    IDENTIFIER="twtest"
    
    # A tap device without protocol information
    sudo ip tuntap add dev tap-${IDENTIFIER} mode tap user $(id -u -n) group $(id -g -n)
    sudo ip link set up dev tap-${IDENTIFIER}
    sudo ip addr add 172.16.0.1/24 dev tap-${IDENTIFIER}
    sudo ip neigh add 172.16.0.2 lladdr de:ad:be:ef:ca:fe dev tap-${IDENTIFIER}
    
    # A tap device with protocol information
    sudo ip tuntap add dev tap-${IDENTIFIER}-pi mode tap user $(id -u -n) group $(id -g -n) pi
    sudo ip link set up dev tap-${IDENTIFIER}-pi
    sudo ip addr add 172.16.1.1/24 dev tap-${IDENTIFIER}-pi
    sudo ip neigh add 172.16.1.2 lladdr de:ad:ca:fe:be:ef dev tap-${IDENTIFIER}-pi
    
    # A tun device without protocol information
    sudo ip tuntap add dev tun-${IDENTIFIER} mode tun user $(id -u -n) group $(id -g -n)
    sudo ip link set up dev tun-${IDENTIFIER}
    
    # A tun device with protocol information
    sudo ip tuntap add dev tun-${IDENTIFIER}-pi mode tun user $(id -u -n) group $(id -g -n) pi
    sudo ip link set up dev tun-${IDENTIFIER}-pi




    



There are two things to keep in mind about this configuration.
First, it uses addresses from the 172.16.0.0/12 private use range.
If your network is configured to use these already then running the script may cause problems for your network.
These addresses are hard-coded into the Twisted Pair test suite so this problem is not easily avoided.
Second, the changes are not persistent across reboots.
If you want this network configuration to be available even after a reboot you will need to integrate the above into your system's init scripts somehow
(the details of this for different systems is beyond the scope of this document).


    



Certain platforms may also require a modification to their firewall rules in order to allow the traffic the test suite wants to transmit.
Adding firewall rules which allowing traffic destined for the addresses used by the test suite should address this problem.
If you encounter timeouts when running the Twisted Pair test suite then this may apply to you.
For example, to configure an iptables firewall to allow this traffic:


    



::

    
    iptables -I INPUT --dest 172.16.1.1 -j ACCEPT
    iptables -I INPUT --dest 172.16.2.1 -j ACCEPT



  
