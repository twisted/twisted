from twisted.conch.ssh._cryptography_backports import intFromBytes, intToBytes


def test_int_to_bytes():
    assert intToBytes(528) == b'\x02\x10'


def test_int_to_bytes_length():
    assert intToBytes(528, 3) == b'\x00\x02\x10'


def test_int_from_bytes():
    assert intFromBytes(b'\x02\x10', 'big') == 528


def test_int_from_bytes_bytearray():
    assert intFromBytes(bytearray(b'\x02\x10'), 'big') == 528
