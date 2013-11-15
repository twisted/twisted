twisted.names.client.Resolver now accepts three new factory arguments (
datagramProtocolFactory, streamProtocolFactory and axfrControllerFactory) which
allows customization of the protocols it uses to handle DNS requests and zone
transfers.
