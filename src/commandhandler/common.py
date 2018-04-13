#!/usr/bin/env python3

import logging
from src import messages
from src import util
import requests
import json
import time

import telegram
import discord

logger = logging.getLogger("common")

######
# Return the welcome message and add the user if its not already added
#
#
# Gets only called by any command handler
######
def checkUser(bot, message):
    logger.info("checkUser")

    result = {'response':None, 'added':False}

    userInfo = util.crossMessengerSplit(message)
    userId = userInfo['user'] if 'user' in userInfo else None
    userName = userInfo['name'] if 'name' in userInfo else "Unknown"

    if not bot.database.getUser(userId) and bot.database.addUser(userId, userName):
        logger.info("checkUser - new user {}".format(userName))

        result['added'] = True

        if bot.messenger == 'discord':
            result['response'] += messages.welcome(bot.messenger)

    return result


######
# Telegram command handler for printing the help text
#
# Command: /help
#
# Gets only called by the telegram bot api
######
def info(bot, update):

    logger.info("network")

    response = messages.markdown("<u><b>SmartNode Network<b><u>\n\n",bot.messenger)

    with bot.nodeList as nodeList:

        if nodeList.synced() and nodeList.lastBlock:

            lastBlock = nodeList.lastBlock
            created = nodeList.count()
            enabled = nodeList.enabled()
            qualifiedNormal = nodeList.qualifiedNormal
            qualifiedUpgrade = nodeList.qualifiedUpgrade
            upgradeModeDuration = nodeList.remainingUpgradeModeDuration
            protocolRequirement = nodeList.protocolRequirement()
            protocol90024 = nodeList.count(90024)
            protocol90025 = nodeList.count(90025)
            initialWait = nodeList.minimumUptime()
            aberration = bot.aberration

            if upgradeModeDuration:
                upgradeModeDuration = util.secondsToText(upgradeModeDuration)

            response += messages.networkState(bot.messenger,
                                              lastBlock,
                                              created,
                                              enabled,
                                              qualifiedNormal,
                                              qualifiedUpgrade,
                                              upgradeModeDuration,
                                              protocolRequirement,
                                              protocol90024,
                                              protocol90025,
                                              util.secondsToText(initialWait),
                                              aberration)

        else:
            response += "*Sorry, the bot is currently not synced with the network. Try it again in few minutes...*"

    return response

def networkUpdate(bot, ids, added):

    count = len(ids)

    logger.info("networkUpdate {}, {}".format(count,added))

    response = messages.markdown("<u><b>Network update<b><u>\n\n",bot.messenger)

    if added:
        response += "{} new node{} detected\n\n".format(count,"s" if count > 1 else "")
    else:
        response += "{} node{} left us!\n\n".format(abs(count),"s" if count < 1 else "")

    with bot.nodeList as nodeList:

        response += messages.markdown("We have <b>{}<b> created nodes now!\n\n".format(nodeList.count()),bot.messenger)
        response += messages.markdown("<b>{}<b> of them are enabled.".format(nodeList.enabled()), bot.messenger)

    return response

######
# Telegram command handler for printing the help text
#
# Command: /help
#
# Gets only called by the telegram bot api
######
def stats(bot):

    logger.info("stats")

    response = messages.markdown("<u><b>Statistics<b><u>\n\n",bot.messenger)

    response += "User: {}\n".format(len(bot.database.getUsers()))
    response += "Nodes: {}\n".format(len(bot.database.getAllNodes()))

    return response

def payouts(bot, args):

    logger.info("payouts")

    response = messages.markdown("<u><b>Payout statistics<b><u>\n\n",bot.messenger)

    if not bot.rewardList.running:
        response += "Not initialized yet. Wait a bit..."
        return response

    hours = 12

    if len(args):
        try:
            hours = float(args[0])
        except:
            pass

    start = time.time() - (hours * 3600)

    firstReward = bot.rewardList.getNextReward(start)
    lastReward = bot.rewardList.getLastReward()

    if not firstReward:
        response += "Could not fetch the rewards in the given time range!\n"
        response += "The last available is at block {} from {} ago.".format(lastReward.block, util.secondsToText(time.time() - lastReward.txtime))
        return response

    total = bot.rewardList.getRewardCount(start = start)
    vChain = bot.rewardList.getRewardCount(start = start, source=0, meta=0)
    iChain = bot.rewardList.getRewardCount(start = start, meta=1)
    nList = bot.rewardList.getRewardCount(start = start, source=1)
    err = bot.rewardList.getRewardCount(start = start, meta=-1)

    response += "Blocks: {}\n".format(lastReward.block - firstReward.block)
    response += "RT: {}\n".format(util.secondsToText(lastReward.txtime - firstReward.txtime))
    response += "P: {}\n".format(total)
    response += "V: {}\n".format(vChain)
    response += "I: {}\n".format(iChain)
    response += "NL: {}\n".format(nList)
    response += "ERR: {}\n".format(err)
    response += "E: {}%".format(round( (1 - (nList/total))*100, 1))

    return response




######
# Telegram command handler for printing unknown command text
#
# Command: All invalid commands
#
# Gets only called by the telegram bot api
######
def unknown(bot):

    logger.info("help")

    return messages.markdown("I'm not sure what you mean? Try <cb>help<ca>",bot.messenger)

######
# Telegram command handler for logging errors from the bot api
#
# Command: No command, will get called on errors.
#
# Gets only called by the telegram bot api
######
def error(bot, update, error):
    logger.error('Update "%s" caused error "%s"' % (update, error))
    logger.error(error)
