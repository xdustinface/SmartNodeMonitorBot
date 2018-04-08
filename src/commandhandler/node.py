#!/usr/bin/env python3

import logging
import time
from src import util
from src import messages

import telegram
import discord

from smartcash.rewardlist import SNReward

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

                node = bot.nodeList.getNodeByIp(ip)

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

                node = bot.nodeList.getNodeByIp(ip)

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

                    logger.info("remove - valid {}".format(ip))

                    node = bot.nodeList.getNodeByIp(ip)

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
    minimumUptime = bot.nodeList.minimumUptime()

    if user == None or userNodes == None or len(userNodes) == 0:

       response +=  messages.nodesRequired(bot.messenger)

    else:

        for userNode in userNodes:

            smartnode = bot.nodeList.getNodes([userNode['collateral']])[0]

            response += messages.markdown(("<b>" + userNode['name'] + " - " + smartnode.ip + "<b>")  ,bot.messenger)
            response += "\n  `Status` " + smartnode.status
            response += "\n  `Position` " + messages.markdown(smartnode.positionString(minimumUptime),bot.messenger)
            response += "\n  `Payee` " + smartnode.payee
            response += "\n  `Active since` " + util.secondsToText(smartnode.activeSeconds)
            response += "\n  `Last seen` " + util.secondsToText( int(time.time()) - smartnode.lastSeen)
            response += "\n  `Last payout (Block)` " + smartnode.payoutBlockString()
            response += "\n  `Last payout (Time)` " + smartnode.payoutTimeString()
            response += "\n  `Protocol` {}".format(smartnode.protocol)
            #response += "\n  `Rank` {}".format(smartnode.rank)
            response += "\n  " + messages.link(bot.messenger, 'https://explorer3.smartcash.cc/address/{}'.format(smartnode.payee),'Open the explorer!')
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

        collaterals = list(map(lambda x: x['collateral'],userNodes))
        nodes = bot.nodeList.getNodes(collaterals)
        minimumUptime = bot.nodeList.minimumUptime()

        for smartnode in sorted(nodes, key=lambda x: x.position):

            userNode = bot.database.getNodes(smartnode.collateral, user['id'])

            payoutText = util.secondsToText(smartnode.lastPaidTime)
            response += messages.markdown("<b>" + userNode['name'] + "<b> - `" + smartnode.status + "`",bot.messenger)
            response += "\nPosition " + messages.markdown(smartnode.positionString(minimumUptime),bot.messenger)
            response += "\nLast seen " + util.secondsToText( int(time.time()) - smartnode.lastSeen)
            response += "\nLast payout " + smartnode.payoutTimeString()
            response += "\n" + messages.link(bot.messenger, 'https://explorer3.smartcash.cc/address/{}'.format(smartnode.payee),'Open the explorer!')
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

    response = messages.markdown("<u><b>History<b><u>\n\n",bot.messenger)

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

        collaterals = list(map(lambda x: x['collateral'],userNodes))
        nodes = bot.nodeList.getNodes(collaterals)

        totalInvest = len(nodes) * 10000
        totalProfit = 0

        for smartnode in nodes:

            userNode = bot.database.getNodes(smartnode.collateral, user['id'])
            rewards = bot.rewardList.getRewardsForPayee(smartnode.payee)
            profit = sum(map(lambda x: x.amount,rewards))
            totalProfit += profit
            response += messages.markdown("<b>" + userNode['name'] + "<b>",bot.messenger)
            response += "\nPayouts {}".format(len(rewards))
            response += "\nProfit {} SMART".format(profit)
            response += "\nROI (SMART) {}%".format(round((profit/10000.0)*100.0,1))
            response += "\n\n"

        response += messages.markdown("<b>Total profit<b> {}<b>".format(round(totalProfit,1)),bot.messenger)
        response += messages.markdown("<b>Total ROI (SMART): {}<b>".format(round((totalProfit / totalInvest)*100,1),bot.messenger)

    return response


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
        error = False

        for result in results:
            for node in userNodes:
                if str(result.node.collateral) == node['collateral']:

                    if not util.isInt(result.data) and "error" in result.data:
                        response += "{} - Error: {}\n".format(node['name'], result.data["error"])
                        logger.warning("Balance response error: {}".format(result.data))
                        error = True
                    else:

                        try:
                            total += round(result.data,1)
                            response += "{} - {} SMART\n".format(node['name'], result.data)
                        except:
                            error = True
                            logger.warning("Balance response invalid: {}".format(result.data))
                            response += "{} - Error: Could not fetch this balance.\n".format(node['name'])

        response += messages.markdown("\nTotal: <b>{} SMART<b>".format(round(total,1)),bot.messenger)

        # Only show the profit if there was no error since it would make not much sense otherwise.
        if not error:
            response += messages.markdown("\nProfit: <b>{} SMART<b>".format(round(total - len(userNodes) * 10000,1)),bot.messenger)

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

    if bot.nodeList.synced() and bot.nodeList.lastBlock:

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

                    result = bot.nodeList.lookup(ip)

                    if result:
                        lookups.append(messages.lookupResult(bot.messenger,result))
                    else:
                        errors.append(messages.nodeNotInListError(bot.messenger,ip))

            for e in errors:
                response += e

            for l in lookups:
                response += l
    else:
        response += "<b>Sorry, the bot is currently not synced with the network. Try it again in few minutes...<b>"

    return response


def handleNodeUpdate(bot, update, node):

    # If there is a new block available form the nodelist
    if update['lastPaid']:

        # Update the source of the reward in the rewardlist to be able to track the
        # number of missing blocks in the nodelist
        # If the reward was not available yet it gets added
        reward = SNReward(block=node.lastPaidBlock,
                          txtime=node.lastPaidTime,
                          payee=node.payee,
                          source=1,
                          meta=2)

        bot.rewardList.updateSource(reward)


    # Create notification response messages!

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

                responses[dbUser['id']].append(response)


    return responses

def handleReward(bot, reward, synced):

        responses = {}
        nodes = bot.nodeList.getNodesByPayee(reward.payee)

        if not nodes or not len(nodes):
            # Payee not found for whatever reason?!
            logger.error("Could not find payee in list. Reward: {}".format(str(reward)))

            # Mark it in the database!
            reward.meta = 1
            updated = bot.rewardList.updateMeta(reward)
            logger.info("Updated meta {}".format(updated))

        elif synced:
        # Dont notify until the list is up to date.

            # When there are multiple nodes with that payee warn the user
            count = len(nodes)

            logger.info("rewardCB {} - nodes: {}".format(str(reward),count))

            for n in nodes:

                for userNode in bot.database.getNodes(n.collateral):

                    dbUser = bot.database.getUser(userNode['user_id'])

                    if dbUser and dbUser['reward_n']:

                        if not dbUser['id'] in responses:
                            responses[dbUser['id']] = []

                        response = messages.rewardNotification(bot.messenger, userNode['name'], reward.block, reward.amount)

                        if count > 1:
                            response += messages.multiplePayeeWarning(bot.messenger, reward.payee, count)

                        responses[dbUser['id']].append(response)

        return responses
