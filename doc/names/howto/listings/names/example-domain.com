import base64

zone = [
    SOA(
        # For whom we are the authority
        'example-domain.com',

        # This nameserver's name
        mname = "ns1.example-domain.com",

        # Mailbox of individual who handles this
        rname = "root.example-domain.com",

        # Unique serial identifying this SOA data
        serial = 2003010601,

        # Time interval before zone should be refreshed
        refresh = "1H",

        # Interval before failed refresh should be retried
        retry = "1H",

        # Upper limit on time interval before expiry
        expire = "1H",

        # Minimum TTL
        minimum = "1H"
    ),

    A('example-domain.com', '127.0.0.1'),
    NS('example-domain.com', 'ns1.example-domain.com'),

    CNAME('www.example-domain.com', 'example-domain.com'),
    CNAME('ftp.example-domain.com', 'example-domain.com'),

    MX('example-domain.com', 0, 'mail.example-domain.com'),
    A('mail.example-domain.com', '123.0.16.43'),

    DNSKEY('example-domain.com', publicKey=base64.decodestring(
            b'AQPSKmynfzW4kyBv015MUG2DeIQ3'
            b'Cbl+BBZH4b/0PY1kxkmvHjcZc8no'
            b'kfzj31GajIQKY+5CptLr3buXA10h'
            b'WqTkF7H6RfoRqXQeogmMHfpftf6z'
            b'Mv1LyBUgia7za6ZEzOJBOztyvhjL'
            b'742iU/TpPSEDhm2SNKLijfUppn1U'
            b'aNvv4w=='))
]
