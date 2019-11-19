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

import os, stat, sys
import re
import subprocess
import json
import time
from requests_futures.sessions import FuturesSession

import logging
import threading
import re
import uuid

logger = logging.getLogger("smartexplorer")

lockForever = sys.float_info.max

class Request(object):

    def __init__(self,node, request, cb):
        self.attempts = 0
        self.node = node
        self.explorer = request['explorer']
        self.future = request['future']
        self.future.add_done_callback(self.futureCB)
        self.result = None
        self.cb = cb
        self.data = None
        self.status = -1
        self.error = None

    def futureCB(self, future):

        try:
            self.result = self.future.result()
            self.status = self.result.status_code
        except:
            self.error = "Could not fetch result"

        try:
            self.data = self.result.json()
        except:
            self.error = "Could not parse json {}".format(self.result)

        self.cb(self.future)

class SmartExplorer(object):

    def __init__(self, balancesCB):
        self.balancesCB = balancesCB

    def balances(self, addresses):
        logger.warning("SmartExplorer balances")

class LocalExplorer(SmartExplorer):

    def __init__(self,balancesCB):
        super().__init__(balancesCB)

    def balances(self,addresses):
        logger.warning("LocalExplorer maybe later...")

class WebExplorer(SmartExplorer):

    def __init__(self,balancesCB):
        super().__init__(balancesCB)

        self.lastUrl = 0
        self.urls = {'https://core-sapi.smartcash.cc': None}

        self.urlLockSeconds = 3600
        self.session = FuturesSession(max_workers=20)
        self.checks = {}
        self.results = {}
        self.requestSem = threading.Lock()

    def backgroundCB(self, future):

        self.requestSem.acquire()

        logger.info("Checks {}".format(len(self.checks)))

        done = None

        for check, requests in self.checks.items():
            logger.info("CHECK {}, requests {}".format(check,len(requests)))
            for request in requests:

                if request.future == future:

                    if request.error != None:
                        logger.error("[{}] Request error {}".format(request.status, request.error))
                        self.balancesCB(check, None)
                        self.urls[request.explorer] = time.time()
                        done = check
                        break

                    if request.status != 200:
                        logger.warning("[{}] Request error {}".format(request.status, request.data))
                        self.urls[request.explorer] = time.time()

                    break

            if done:
                 break

            if not sum(map(lambda x: x.status == -1 , requests)):
                done = check
                self.balancesCB(check, requests)

        if done:
            self.checks.pop(done)

        logger.info("URL states {}".format(self.urls))

        self.requestSem.release()

    def nextUrl(self):

        def urlReady(x):
            return x == None or \
                  (time.time() - x) >= self.urlLockSeconds

        while True:

            if not sum(map(lambda x: urlReady(x) ,self.urls.values())):
                # If there is no unlocked url left
                raise ValueError("No explorer url ready.")

            nextIndex = (self.lastUrl + 1 ) % len(self.urls)
            self.lastUrl = nextIndex

            if urlReady(list(self.urls.values())[nextIndex]):
                return list(self.urls.keys())[self.lastUrl]


    def balance(self, address):

        explorer = self.nextUrl()
        requestUrl = "{}/v1/address/balance/{}".format(explorer,address)
        logger.info("Add {}".format(requestUrl))
        future = self.session.get(requestUrl)
        return {'explorer' : explorer, 'future' : future}

    def balances(self, nodes):

        self.requestSem.acquire()

        check = uuid.uuid4()

        logger.info("Create balance check: {}".format(check))

        try:
            self.checks[check] = list(map(lambda x: Request(x, self.balance(x.payee), self.backgroundCB), nodes ))
        except ValueError as e:
            logger.warning("balances {}".format(e))
            self.requestSem.release()
            return None
        else:
            logger.info("Added balance check {}".format(check))

        self.requestSem.release()

        return check
