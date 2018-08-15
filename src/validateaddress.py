##
# Part of `SmartNodeMonitorBot`
#
# Copyright 2018 dustinface
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
##

import binascii
from Cryptodome.Hash import keccak

digits58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

def keccak256(x):
    x = bytes(x)
    keccak_hash = keccak.new(digest_bits=256)
    keccak_hash.update(x)
    return bytes(keccak_hash.digest())

def HashKeccak(x):
    x = bytes(x)
    out = bytes(keccak256(x))
    return out

def decode_base58(smartAddress, length):
    """Decode a base58 encoded address
    This form of base58 decoding is smartcashd specific. Be careful outside of
    smartcashd context.
    """
    n = 0
    for char in smartAddress:
        try:
            n = n * 58 + digits58.index(char)
        except:
            msg = u"Character not part of SmartCashs's base58: '%s'"
            raise ValueError(msg % (char,))

    return n.to_bytes(length, 'big')

def encode_base58(bytestring):
    """Encode a bytestring to a base58 encoded string
    """
    # Count zero's
    zeros = 0
    for i in range(len(bytestring)):
        if bytestring[i] == 0:
            zeros += 1
        else:
            break

    n = int.from_bytes(bytestring, 'big')

    result = ''
    (n, rest) = divmod(n, 58)
    while n or rest:
        result += digits58[rest]
        (n, rest) = divmod(n, 58)
    return zeros * '1' + result[::-1]  # reverse string

def validate(smartAddress):
    """Check the integrity of a smartcash address
    Returns False if the address is invalid.
    """

    addressLen = len(smartAddress)

    if addressLen < 27 or addressLen > 35:
        return None

    try:
        decoded = decode_base58(smartAddress, 25)
    except ValueError:
        return None

    # Compare checksum
    checksum = HashKeccak(decoded[:-4])[:4]
    if decoded[-4:] != checksum:
        return None

    if smartAddress != encode_base58(decoded):
        return None

    return smartAddress
