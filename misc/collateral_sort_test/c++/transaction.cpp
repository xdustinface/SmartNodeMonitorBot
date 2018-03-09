// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-2015 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include "transaction.h"

#include "hash.h"
#include "tinyformat.h"
#include "utilstrencodings.h"


std::string COutPoint::ToString() const
{
    return strprintf("%s-%u", hash.ToString(), n);
}

std::string COutPoint::ToStringShort() const
{
    return strprintf("COutPoint(%s, %u)", hash.ToString().substr(0,64), n);
}
