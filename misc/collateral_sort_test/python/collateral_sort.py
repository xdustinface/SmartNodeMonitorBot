import os, stat
import re
import subprocess
import json
import time
import csv
import logging
import threading
import re

transactionRawCheck = re.compile("COutPoint\([\d\a-f]{64},.[\d]{1,}\)")
transactionStringCheck = re.compile("[\d\a-f]{64}-[\d]{1,}")

def memcmp ( str1, str2, count):

    while count > 0:
        count -= 1

        print( str(str1[count]) + " " + str(str2[count]))

        if str1[count] != str2[count]:
            return -1 if str1[count] < str2[count] else 1

    return 0

class Transaction(object):

    def __init__(self, txhash, txindex):
        self.hash = txhash
        self.index = txindex

    def __str__(self):
        return '{0.hash}-{0.index}'.format(self)

    def __eq__(self, other):
        return self.hash == other.hash and\
                self.index == other.index

    def __lt__(self, other):
        # friend bool operator<(const CTxIn& a, const CTxIn& b)
        # {
        #     return a.prevout<b.prevout;
        # }
        # friend bool operator<(const COutPoint& a, const COutPoint& b)
        # {
        #     int cmp = a.hash.Compare(b.hash);
        #     return cmp < 0 || (cmp == 0 && a.n < b.n);
        # }
        # https://github.com/SmartCash/smartcash/blob/1.1.1/src/uint256.h#L45
        # https://github.com/SmartCash/smartcash/blob/1.1.1/src/primitives/transaction.h#L38
        # https://github.com/SmartCash/smartcash/blob/1.1.1/src/primitives/transaction.h#L126
        compare = memcmp(bytes.fromhex(self.hash), bytes.fromhex(other.hash),len(bytes.fromhex(self.hash)))
        print(compare)
        return compare < 0 or ( compare == 0 and self.index < other.index )
        #return self.hash < other.hash or ( self.hash == other.hash and self.index < other.index )


    def __hash__(self):
        return hash((self.hash,self.index))

    @classmethod
    def fromRaw(cls, s):

        if transactionRawCheck.match(s):
            parts = s[10:-1].split(', ')
            return cls(parts[0], int(parts[1]))

    @classmethod
    def fromString(cls, s):

        if transactionStringCheck.match(s):
            parts = s.split('-')
            return cls(parts[0], int(parts[1]))

class LastPaid(object):

    def __init__(self, lastPaidBlock, transaction):
        self.transaction = transaction
        self.lastPaidBlock = lastPaidBlock

    def __str__(self):
        return '[{0.lastPaidBlock}] {0.transaction}'.format(self)

    def __lt__(self, other):

        if self.lastPaidBlock != other.lastPaidBlock:
            return self.lastPaidBlock < other.lastPaidBlock

        return self.transaction < other.transaction

tx1 = Transaction.fromString("7c4389865729c03e9228a2bade8ae96d305d1b8b16b65207f227fd17c890d52e-0")
tx2 = Transaction.fromString("1f44671c77aee69cacbb166bd879eaf921c1c04f04ef91c1580e173d7f829ebe-1")
tx3 = Transaction.fromString("fbaef56dd2306b15ed8f69dae0e0ddc815551c2d6f3477d4dba7260ecce865c0-1")
tx4 = Transaction.fromString("7c4389865729c03e9228a2bade8ae96d305d1b8b16b65207f227fd17c890d52e-1")

lastPaidVec = []
lastPaidVec.append(LastPaid(1, tx1))
lastPaidVec.append(LastPaid(1, tx2))
lastPaidVec.append(LastPaid(1, tx3))
lastPaidVec.append(LastPaid(1, tx4))

print("\nUnsorted\n")

for l in lastPaidVec:
    print(str(l))

print("\nSorted\n")

lastPaidVec.sort()

for l in lastPaidVec:
    print(str(l))
