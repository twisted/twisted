# Needs to be short enough so that with prefix and suffix, fits into 16 bytes
IDENTIFIER="twtest"

# A device without protocol information
sudo ip tuntap add dev tap-$IDENTIFIER mode tap user $(id -u -n) group $(id -g -n)
sudo ip link set up dev tap-$IDENTIFIER
sudo ip addr add 10.0.0.1/24 dev tap-$IDENTIFIER
sudo ip neigh add 10.0.0.2 lladdr de:ad:be:ef:ca:fe dev tap-$IDENTIFIER

# A device with protocol information
sudo ip tuntap add dev tap-$IDENTIFIER-pi mode tap user $(id -u -n) group $(id -g -n) pi
sudo ip link set up dev tap-$IDENTIFIER-pi
sudo ip addr add 10.1.0.1/24 dev tap-$IDENTIFIER-pi
sudo ip neigh add 10.1.0.2 lladdr de:ad:ca:fe:be:ef dev tap-$IDENTIFIER-pi

# A device without protocol information
sudo ip tuntap add dev tun-$IDENTIFIER mode tun user $(id -u -n) group $(id -g -n)
sudo ip link set up dev tun-$IDENTIFIER

# A device with protocol information
sudo ip tuntap add dev tun-$IDENTIFIER-pi mode tun user $(id -u -n) group $(id -g -n) pi
sudo ip link set up dev tun-$IDENTIFIER-pi
