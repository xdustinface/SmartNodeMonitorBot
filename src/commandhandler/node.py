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

import logging
import time
import json
from src import util
from src import messages

import telegram
import discord

from smartcash.rewardlist import SNReward

HF_1_2_MULTINODE_PAYMENTS = 545005

def getPayeesPerBlock(nHeight):

    if nHeight >= HF_1_2_MULTINODE_PAYMENTS:
        return 10

    return 1

def getPayoutInterval(nHeight):

    if nHeight >= HF_1_2_MULTINODE_PAYMENTS:
        return 2

    return 1

def getBlockReward(nHeight):
    return 5000.0  * ( 143500.0 / nHeight ) * 0.1

logger = logging.getLogger("node")

######
# Command handler for adding nodes for the user who fired the command.
#
# Command: node :ip0;name0 ... :ipN;nameN
#
# Command parameter: :ip0 - Address of the first node to add
#                    :name0 - Name of the first node
#                    :ipN - Address of the last node to add
#                    :nameN - Name of the last node
#
# Only called by the bot instance
######
def nodeAdd(bot, update, args):

    userInfo = util.crossMessengerSplit(update)
    userId = userInfo['user'] if 'user' in userInfo else None
    userName = userInfo['name'] if 'name' in userInfo else None

    response = messages.markdown("<u><b>Add<b><u>\n\n",bot.messenger)

    logger.debug("add - " + " ".join(args))
    logger.debug("add - user: {}".format(userId))

    if len(args) == 0:

        response += messages.markdown(("<b>ERROR<b>: Arguments required: <b>IPAddress_0;name_0 ... IPAddress_n;name_n<b>\n\n"
                     "Example: <cb>add<ca> 43.121.56.87;Node1 56.76.27.100;Node2\n"),bot.messenger)
        valid = False

    else:
        with bot.nodeList as nodeList:

            for arg in args:

                valid = True

                newNode = arg.split(";")

                if len(newNode) != 2:

                    response += messages.invalidParameterError(bot.messenger,arg)
                    valid = False
                else:

                    ip = util.validateIp( newNode[0] )
                    name = util.validateName( newNode[1] )

                    if not ip:

                        response += messages.invalidIpError(bot.messenger, newNode[0])
                        valid = False

                    if not name:

                        response += messages.invalidNameError(bot.messenger, newNode[1])
                        valid = False

                if valid:

                    node = nodeList.getNodeByIp(ip)

                    if node == None:
                        response += messages.nodeNotInListError(bot.messenger,ip)
                    else:

                        if bot.database.addNode( node.collateral, name, userId,userName):

                            response += "Added node {}!\n".format(ip)

                        else:

                            response += messages.nodeExistsError(bot.messenger,ip)

    return response

######
# Command handler for updating nodes for the user who fired the command.
#
# Command: add :ip :newname
#
# Command parameter: :ip - Address of the node to update
#                    :newname - New name for the node
#
# Only called by the bot instance
######
def nodeUpdate(bot, update, args):

    userInfo = util.crossMessengerSplit(update)
    userId = userInfo['user'] if 'user' in userInfo else None
    userName = userInfo['name'] if 'name' in userInfo else None

    response = messages.markdown("<u><b>Update<b><u>\n\n",bot.messenger)

    logger.debug("update - " + " ".join(args))
    logger.debug("update - user: {}".format(userId))

    user = bot.database.getUser(userId)

    if user == None:

        response += messages.notActiveError(bot.messenger)

    elif not len(args):

        response += messages.markdown(("<b>ERROR<b>: Argument(s) required: <b>ip0;newname0 ipN;newnameN<b>\n\n"
                     "Where <b>ip<b> is the IP-Address of the node to update and <b>newname<b> the"
                     " new name of the node.\n\n"
                     "Example: <cb>update<ca> 23.132.143.34;MyNewNodeName\n"),bot.messenger)

    else:

        with bot.nodeList as nodeList:

            for arg in args:

                nodeEdit = arg.split(";")

                valid = True

                if len(nodeEdit) != 2:

                    response += messages.invalidParameterError(bot.messenger,arg)
                    valid = False
                else:

                    ip = util.validateIp( nodeEdit[0] )
                    name = util.validateName( nodeEdit[1] )

                    if not ip:

                        response += messages.invalidIpError(bot.messenger, nodeEdit[0])
                        valid = False

                    if not name:

                        response += messages.invalidNameError(bot.messenger, nodeEdit[1])
                        valid = False

                if valid:

                    logger.info("update - {} {}".format(ip, user['id']))

                    node = nodeList.getNodeByIp(ip)

                    if node == None:
                        response += messages.nodeNotInListError(bot.messenger, ip)
                    else:

                        userNode = bot.database.getNodes(node.collateral,userId)

                        if userNode == None:
                            response += messages.nodeNotExistsError(bot.messenger, ip)
                        else:

                            bot.database.updateNode(node.collateral,user['id'], name)

                            response += "Node successfully updated. {}\n".format(ip)

    return response

######
# Command handler for removing nodes for the user who fired the command.
#
# Command: remove :ip
#
# Command parameter: :ip - Address of the node to remove
#
# Only called by the bot instance
######
def nodeRemove(bot, update, args):

    userInfo = util.crossMessengerSplit(update)
    userId = userInfo['user'] if 'user' in userInfo else None
    userName = userInfo['name'] if 'name' in userInfo else None

    response = messages.markdown("<u><b>Remove<b><u>\n\n",bot.messenger)

    logger.debug("remove - " + " ".join(args))
    logger.debug("remove - user: {}".format(userId))

    user = bot.database.getUser(userId)

    if user == None:

        response += messages.notActiveError(bot.messenger)

    elif len(args) < 1:

        response += messages.markdown(("<b>ERROR<b>: Argument(s) required: <b>:ip0 :ipN<b>\n\n"
                     "Example remove one: <cb>remove<ca> 21.23.34.44\n"
                     "Example remove more: <cb>remove<ca> 21.23.34.44 21.23.34.43\n"
                     "Example remove all: <cb>remove<ca> all\n"),bot.messenger)

    else:

        # Check if the user wants to remove all nodes.
        if len(args) == 1 and args[0] == 'all':

            bot.database.deleteNodesForUser(userId)
            response += messages.markdown("Successfully removed <b>all<b> your nodes!\n",bot.messenger)

        else:

            # Else go through the parameters
            for arg in args:

                ip = util.validateIp( arg )

                if not ip:

                    response += messages.invalidIpError(bot.messenger, arg)
                    valid = False

                else:

                    with bot.nodeList as nodeList:

                        logger.info("remove - valid {}".format(ip))

                        node = nodeList.getNodeByIp(ip)

                        if node == None:
                            response += messages.nodeNotInListError(bot.messenger, ip)
                        else:

                            userNode = bot.database.getNodes(node.collateral,userId)

                            if userNode == None:
                                response += messages.nodeNotExistsError(bot.messenger, ip)
                            else:
                                bot.database.deleteNode(node.collateral,user['id'])
                                response += messages.markdown("Node successfully removed. <b>{}<b>\n".format(ip),bot.messenger)

    return response

######
# Command handler for printing a detailed list for all nodes
# of the user
#
# Command: detail
#
# Only called by the bot instance
######
def detail(bot, update):

    response = messages.markdown("<u><b>Detail<b><u>\n\n",bot.messenger)

    userInfo = util.crossMessengerSplit(update)
    userId = userInfo['user'] if 'user' in userInfo else None
    userName = userInfo['name'] if 'name' in userInfo else update.message.from_user.name

    logger.debug("detail - user: {}".format(userId))

    nodesFound = False


    user = bot.database.getUser(userId)
    userNodes = bot.database.getAllNodes(userId)

    if user == None or userNodes == None or len(userNodes) == 0:

       response +=  messages.nodesRequired(bot.messenger)

    else:

        with bot.nodeList as nodeList:

            minimumUptime = nodeList.minimumUptime()
            top10 = nodeList.enabledWithMinProtocol() * 0.1

            for userNode in userNodes:

                smartnode = nodeList.getNodes([userNode['collateral']])[0]

                response += messages.markdown(("<b>" + userNode['name'] + " - " + smartnode.ip + "<b>")  ,bot.messenger)
                response += "\n  `Status` " + smartnode.status
                response += "\n  `Position` " + messages.markdown(smartnode.positionString(minimumUptime, top10),bot.messenger)
                response += "\n  `Payee` " + smartnode.payee
                response += "\n  `Active since` " + util.secondsToText(smartnode.activeSeconds)
                response += "\n  `Last seen` " + util.secondsToText( int(time.time()) - smartnode.lastSeen)
                response += "\n  `Last payout (Block)` " + smartnode.payoutBlockString()
                response += "\n  `Last payout (Time)` " + smartnode.payoutTimeString()
                response += "\n  `Protocol` {}".format(smartnode.protocol)
                #response += "\n  `Rank` {}".format(smartnode.rank)
                response += "\n  " + messages.link(bot.messenger, 'https://explorer.smartcash.cc/address/{}'.format(smartnode.payee),'Open the explorer!')
                response += "\n\n"

    return response


######
# Command handler for printing a shortened list sorted by positions for all nodes
# of the user
#
# Command: nodes
#
# Only called by the bot instance
######
def nodes(bot, update):

    response = messages.markdown("<u><b>Nodes<b><u>\n\n",bot.messenger)

    userInfo = util.crossMessengerSplit(update)
    userId = userInfo['user'] if 'user' in userInfo else None
    userName = userInfo['name'] if 'name' in userInfo else None

    logger.debug("nodes - user: {}".format(userId))

    nodesFound = False

    user = bot.database.getUser(userId)
    userNodes = bot.database.getAllNodes(userId)

    if user == None or userNodes == None or len(userNodes) == 0:

       response +=  messages.nodesRequired(bot.messenger)

    else:

        with bot.nodeList as nodeList:

            collaterals = list(map(lambda x: x['collateral'],userNodes))
            nodes = nodeList.getNodes(collaterals)
            minimumUptime = nodeList.minimumUptime()
            top10 = nodeList.enabledWithMinProtocol() * 0.1

            for smartnode in sorted(nodes, key=lambda x: x.position if x.position > 0 else 100000):

                userNode = bot.database.getNodes(smartnode.collateral, user['id'])

                payoutText = util.secondsToText(smartnode.lastPaidTime)
                response += messages.markdown("<b>" + userNode['name'] + "<b> - `" + smartnode.status + "`",bot.messenger)
                response += "\nPosition " + messages.markdown(smartnode.positionString(minimumUptime, top10),bot.messenger)
                response += "\nLast seen " + util.secondsToText( int(time.time()) - smartnode.lastSeen)
                response += "\nLast payout " + smartnode.payoutTimeString()
                response += "\n" + messages.link(bot.messenger, 'https://explorer.smartcash.cc/address/{}'.format(smartnode.payee),'Open the explorer!')
                response += "\n\n"

    return response

######
# Command handler for printing a history of payouts for each node
# of the user
#
# Command: history
#
# Only called by the bot instance
######
def history(bot, update):

    response = "<u><b>History<b><u>\n\n"

    userInfo = util.crossMessengerSplit(update)
    userId = userInfo['user'] if 'user' in userInfo else None
    userName = userInfo['name'] if 'name' in userInfo else None

    logger.debug("history - user: {}".format(userId))

    nodesFound = False

    user = bot.database.getUser(userId)
    userNodes = bot.database.getAllNodes(userId)

    if user == None or userNodes == None or len(userNodes) == 0:

       response +=  messages.nodesRequired(bot.messenger)

    else:

        with bot.nodeList as nodeList:

            collaterals = list(map(lambda x: x['collateral'],userNodes))
            nodes = nodeList.getNodes(collaterals)

            time30Days = time.time() - (2592000) # now - 30d * 24h * 60m * 60s
            totalInvest = len(nodes) * 10000
            totalProfit = 0
            totalAvgInterval = 0
            totalFirst = 0
            countMultiplePayouts = 0
            totalProfit30Days = 0

            for smartnode in nodes:

                userNode = bot.database.getNodes(smartnode.collateral, user['id'])
                rewards = bot.rewardList.getRewardsForPayee(smartnode.payee)

                profit = sum(map(lambda x: x.amount,rewards))
                profit30Days = sum(map(lambda x: x.amount if x.txtime > time30Days else 0,rewards))
                totalProfit30Days += profit30Days

                totalProfit += round(profit,1)
                avgInterval = 0
                smartPerDay = 0

                first = 0
                last = 0

                if len(rewards) == 1:

                    first = rewards[0].txtime

                if len(rewards) > 1:
                    countMultiplePayouts += 1

                    payoutTimes = list(map(lambda x: x.txtime,rewards))

                    first = min(payoutTimes)
                    last = max(payoutTimes)

                if not totalFirst or first and totalFirst > first:
                    totalFirst = first

                if last:

                    avgInterval = (last - first) / len(rewards)
                    totalAvgInterval += avgInterval

                    smartPerDay = round( profit / ( (time.time() - first) / 86400 ),1)

                response += "<u><b>Node - " + userNode['name'] + "<b><u>\n\n"
                response += "<b>Payouts<b> {}\n".format(len(rewards))
                response += "<b>Profit<b> {:,} SMART\n".format(round(profit,1))
                response += "<b>Profit (30 days)<b> {:,} SMART\n".format(round(profit30Days,1))

                if avgInterval:
                    response += "\n<b>Payout interval<b> " + util.secondsToText(avgInterval)

                if smartPerDay:
                    response += "\n<b>SMART/day<b> {:,} SMART".format(smartPerDay)

                response += "\n<b>ROI (SMART)<b> {}%".format(round((profit/10000.0)*100.0,1))

                response += "\n\n"

            response += "<u><b>Total stats<b><u>\n\n"

            if totalFirst:
                response += "<b>First payout<b> {} ago\n\n".format(util.secondsToText( time.time() - totalFirst ) )

            response += "<b>Profit (30 days)<b> {:,} SMART\n".format(round(totalProfit30Days,1))
            response += "<b>SMART/day (30 days)<b> {:,} SMART\n\n".format(round(totalProfit30Days/30,1))

            if totalAvgInterval:
                totalAvgInterval = totalAvgInterval/countMultiplePayouts
                response += "<b>Total payout interval<b> {}\n".format(util.secondsToText(totalAvgInterval))

            response += "<b>Total SMART/day<b> {:,} SMART\n\n".format(round(totalProfit/( ( time.time() - totalFirst ) / 86400),1))
            response += "<b>Total profit<b> {:,} SMART\n".format(round(totalProfit,1))
            response += "<b>Total ROI (SMART)<b> {}%\n\n".format(round((totalProfit / totalInvest)*100,1))

    return messages.markdown(response, bot.messenger)


######
# Command handler for printing a shortened list sorted by positions for all nodes
# of the user
#
# Command: nodes
#
# Only called by the bot instance
######
def top(bot, update, args):

    response = "<u><b>Top nodes<b><u>\n\n"

    userInfo = util.crossMessengerSplit(update)
    userId = userInfo['user'] if 'user' in userInfo else None
    userName = userInfo['name'] if 'name' in userInfo else None

    logger.debug("nodes - user: {}".format(userId))

    nodesFound = False

    user = bot.database.getUser(userId)
    userNodes = bot.database.getAllNodes(userId)

    if user == None or userNodes == None or len(userNodes) == 0:

       response +=  messages.nodesRequired(bot.messenger)

    else:

        invalidFilterValueMsg = "<b>ERROR<b>: Invalid filter value: <b>{}<b>! Valid range: 10 - 100\n\n"
        topPercent = 10

        if len(args) >= 1:

            if util.isInt(args[0]) and\
               int(args[0]) >= 10 and int(args[0]) <= 100:
                topPercent = int(args[0])
            else:
                response += invalidFilterValueMsg.format(messages.removeMarkdown(args[0]))

        response += "<b>Filter<b> {}%\n\n".format(topPercent)

        with bot.nodeList as nodeList:

            topX = nodeList.enabledWithMinProtocol() * (topPercent/100)
            collaterals = list(map(lambda x: x['collateral'],userNodes))
            nodes = nodeList.getNodes(collaterals)
            topNodes = list(filter(lambda x: x.position <= topX and x.position > 0, nodes))
            minimumUptime = nodeList.minimumUptime()

            if len(topNodes):
                for smartnode in sorted(topNodes, key=lambda x: x.position if x.position > 0 else 100000):

                    userNode = bot.database.getNodes(smartnode.collateral, user['id'])

                    response += "<b>" + userNode['name'] + "<b>"
                    response += "\nPosition " + messages.markdown(smartnode.positionString(minimumUptime),bot.messenger)
                    response += "\n" + messages.link(bot.messenger, 'https://explorer.smartcash.cc/address/{}'.format(smartnode.payee),'Open the explorer!')
                    response += "\n\n"
            else:
                response += "<b>You have currently no nodes in the top {}% of the queue.<b>\n\n".format(topPercent)

    return messages.markdown(response, bot.messenger)

######
# Command handler for printing the balances for all nodes
# of the user
#
# Command: balance
#
# Only called by the bot instance
######
def balances(bot, userId, results):

    response = messages.markdown("<u><b>Balances<b><u>\n\n",bot.messenger)

    if results != None:

        userNodes = bot.database.getAllNodes(userId)

        total = 0

        for result in results:
            for node in userNodes:
                if str(result.node.collateral) == node['collateral']:

                    if not isinstance(result.data, list) or not len(result.data) or not "balance" in result.data[0]:
                        response += "{} - Error: {}\n".format(node['name'], "Could not fetch balance.")
                        logger.warning("Balance response error: {}".format(result.data))

                    else:

                        try:
                            balance = float(result.data[0]["balance"])
                            total += round(balance,1)
                            response += "{} - {:,} SMART\n".format(node['name'], balance)
                        except:
                            logger.warning("Balance response invalid: {}".format(result.data))
                            response += "{} - Error: Could not fetch this balance.\n".format(node['name'])

        response += messages.markdown("\nTotal: <b>{:,} SMART<b>".format(round(total,1)),bot.messenger)

    else:
        response += "Sorry, could not check your balances! Looks like all explorers are down. Try it again later.\n\n"

    return response

######
# Command handler for printing the balances for all nodes
# of the user
#
# Command: balance
#
# Only called by the bot instance
######
def lookup(bot, userId, args):

    response = messages.markdown("<u><b>Node lookup<b><u>\n\n",bot.messenger)

    with bot.nodeList as nodeList:

        if nodeList.synced() and nodeList.lastBlock:

            if not len(args):
                response += messages.lookupArgumentRequiredError(bot.messenger)
            else:

                errors = []
                lookups = []

                for arg in args:

                    ip = util.validateIp( arg )

                    if not ip:
                        errors.append(messages.invalidIpError(bot.messenger,arg))
                    else:

                        result = nodeList.lookup(ip)

                        if result:
                            lookups.append(messages.lookupResult(bot.messenger,result))
                        else:
                            errors.append(messages.nodeNotInListError(bot.messenger,ip))

                for e in errors:
                    response += e

                for l in lookups:
                    response += l
        else:
            response += messages.notSynced(bot.messenger)

    return response


def handleNodeUpdate(bot, update, node):

    ## Disabled for the meantime.
    # # If there is a new block available form the nodelist
    # if update['lastPaid']:

        # # Update the source of the reward in the rewardlist to be able to track the
        # # number of missing blocks in the nodelist
        # # If the reward was not available yet it gets added
        # reward = SNReward(block=node.lastPaidBlock,
        #                   txtime=node.lastPaidTime,
        #                   payee=node.payee,
        #                   source=1,
        #                   meta=2)
        #
        # dbReward = bot.rewardList.getReward(node.lastPaidBlock)
        #
        # if not dbReward:
        #
        #     reward = SNReward(block=node.lastPaidBlock,
        #                       payee = node.payee,
        #                       txtime=node.lastPaidTime,
        #                       source=1)
        #
        #     bot.rewardList.addReward(reward)
        # else:
        #     bot.rewardList.updateSource(reward)

    # Create notification response messages

    responses = {}

    for userNode in bot.database.getNodes(node.collateral):

        dbUser = bot.database.getUser(userNode['user_id'])

        if dbUser:

            if not dbUser['id'] in responses:
                responses[dbUser['id']] = []

            nodeName = userNode['name']

            if update['status'] and dbUser['status_n']:

                response = messages.statusNotification(bot.messenger,nodeName, node.status)
                responses[dbUser['id']].append(response)

            if update['timeout'] and dbUser['timeout_n']:

                if node.timeout != -1:
                    timeString = util.secondsToText( int(time.time()) - node.lastSeen)
                    response = messages.panicNotification(bot.messenger, nodeName, timeString)
                else:
                    response = messages.relaxNotification(bot.messenger, nodeName)

                #responses[dbUser['id']].append(response)


    return responses

def handleReward(bot, reward, distance):

    logger.debug("handleReward - block distance: {}".format(distance))

    responses = {}
    nodes = None
    payees = []

    try:
        payees = json.loads(reward.payee)
    except:
        payees.append(reward.payee)

    for payee in payees:

        with bot.nodeList as nodeList:
            nodes = nodeList.getNodesByPayee(payee)

        if not nodes or not len(nodes):
            # Payee not found for whatever reason?!
            logger.error("Could not find payee in list. Reward: {}".format(str(payee)))

            # Mark it in the database!
            reward.meta = 1
            updated = bot.rewardList.updateMeta(reward)
            logger.info("Updated meta {}".format(updated))

        elif distance < 200:
        # Dont notify until the list is 200 blocks behind the chain

            # When there are multiple nodes with that payee warn the user
            count = len(nodes)

            logger.info("rewardCB {} - nodes: {}".format(str(payee),count))

            for n in nodes:

                for userNode in bot.database.getNodes(n.collateral):

                    dbUser = bot.database.getUser(userNode['user_id'])

                    if dbUser and dbUser['reward_n']:

                        if not dbUser['id'] in responses:
                            responses[dbUser['id']] = []

                        response = messages.rewardNotification(bot.messenger, userNode['name'], reward.block, reward.amount)

                        if count > 1:
                            response += messages.multiplePayeeWarning(bot.messenger, payee, count)

                        responses[dbUser['id']].append(response)

    return responses
