// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-2015 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include "transaction.h"
#include <iostream>
#include <vector>

using namespace std;

struct CompareLastPaidBlock
{
    bool operator()(const std::pair<int, COutPoint*>& t1,
                    const std::pair<int, COutPoint*>& t2) const
    {
        return (t1.first != t2.first) ? (t1.first < t2.first) : (*t1.second < *t2.second);
    }
};

int main(){

    cout << "Start memcmp test" << endl;

    std::vector<std::pair<int, COutPoint*> > vec;

    vec.push_back(std::make_pair(1, new COutPoint(uint256S("7c4389865729c03e9228a2bade8ae96d305d1b8b16b65207f227fd17c890d52e"),0)));
    vec.push_back(std::make_pair(2, new COutPoint(uint256S("1f44671c77aee69cacbb166bd879eaf921c1c04f04ef91c1580e173d7f829ebe"),1)));
    vec.push_back(std::make_pair(3, new COutPoint(uint256S("fbaef56dd2306b15ed8f69dae0e0ddc815551c2d6f3477d4dba7260ecce865c0"),1)));
    vec.push_back(std::make_pair(4, new COutPoint(uint256S("7c4389865729c03e9228a2bade8ae96d305d1b8b16b65207f227fd17c890d52e"),1)));
    vec.push_back(std::make_pair(1, new COutPoint(uint256S("7c4389865729c03e9228a2bade8ae96d305d1b8b16b65207f227fd17c890d52e"),2)));
    vec.push_back(std::make_pair(1, new COutPoint(uint256S("7c4389865729c03e9228a2bade8aa96d305d1b8b16b65207f227fd17c890d52e"),3)));

    cout << "Unsorted" << endl;
    for( auto entry : vec ){
        cout << "[" << entry.first << "] " << entry.second->ToString() << endl;
    }

    sort(vec.begin(), vec.end(), CompareLastPaidBlock());

    cout << "Sorted" << endl;
    for( auto entry : vec ){
        cout << "[" << entry.first << "] " << entry.second->ToString() << endl;
    }

    return 0;
}
