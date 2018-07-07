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
from src import messages
import requests
import json
from src import util

logger = logging.getLogger("user")

######
# Telegram command handler for reading out the notification states of the user who
# fired the command.
#
# Command: /me
#
#
# Gets only called by the telegram bot api
######
def me(bot, update):

    response = messages.markdown("<u><b>User info<b><u>\n\n", bot.messenger)

    userInfo = util.crossMessengerSplit(update)
    userId = userInfo['user'] if 'user' in userInfo else None

    #Get the user entry from the user which fired the command
    user = bot.database.getUser(userId)

    if user == None:
        response += messages.nodesRequired(bot.messenger)
    else:
        response += "You are {}\n\n".format(messages.removeMarkdown(user['name']))
        response += "Status Notifications " + messages.notificationState(bot.messenger, user['status_n'])
        response += "\nReward Notifications " + messages.notificationState(bot.messenger, user['reward_n'])
        #response += "\nTimeout Notifications " + messages.notificationState(bot.messenger, user['timeout_n'])
        response += "\nNetwork Notifications " + messages.notificationState(bot.messenger, user['network_n'])

    return response

######
# Telegram command handler for changing the user name of the user
# who fired the command.
#
# Command: /username :newname
#
# Parameter: :newname - New username
#
# Gets only called by the telegram bot api
######
def username(bot, update, args ):

    response = messages.markdown("<u><b>Change username<b><u>\n\n",bot.messenger)

    userInfo = util.crossMessengerSplit(update)
    userId = userInfo['user'] if 'user' in userInfo else None

    #Get the user entry from the user which fired the command
    user = bot.database.getUser(userId)

    if user == None:

        response += messages.nodesRequired(bot.messenger)

    elif len(args) != 1:

        response += messages.userNameRequiredError(bot.messenger)

    elif not util.validateName(args[0]):

        response += messages.invalidNameError.format(args[0])

    else:

        old = user['name']

        bot.database.updateUsername(args[0], user['id'])

        response += "Username updated from {} to {}".format(messages.removeMarkdown(old), messages.removeMarkdown(args[0]))

    return response

######
# Telegram command handler for the state of satus notifications for the user
#
# Command: /status :enabled
#
# Command parameter: :status - New notification state
#
# Gets only called by the telegram bot api
######
def status(bot, update, args):
    return changeState(bot,update, args, bot.database.updateStatusNotification, "Status")

#####
# Telegram command handler for the state of satus notifications for the user
#
# Command: /status :enabled
#
# Command parameter: :status - New notification state
#
# Gets only called by the telegram bot api
######
def reward(bot, update, args):
    return changeState(bot,update, args, bot.database.updateRewardNotification, "Reward")


#####
# Telegram command handler for the state of satus notifications for the user
#
# Command: /status :enabled
#
# Command parameter: :status - New notification state
#
# Gets only called by the telegram bot api
######
def timeout(bot, update, args):
    return changeState(bot,update, args, bot.database.updateTimeoutNotification, "Timeout")

#####
# Telegram command handler for the state of satus notifications for the user
#
# Command: /status :enabled
#
# Command parameter: :status - New notification state
#
# Gets only called by the telegram bot api
######
def network(bot, update, args):
    return changeState(bot,update, args, bot.database.updateNetworkNotification, "Network")

def changeState(bot, update, args, action, description):

    response = messages.markdown("<b>{} notifications<b>\n\n".format(description),bot.messenger)

    userInfo = util.crossMessengerSplit(update)
    userId = userInfo['user'] if 'user' in userInfo else None

    #Get the user entry from the user which fired the command
    user = bot.database.getUser(userId)

    if user == None:

        response+= messages.nodesRequired(bot.messenger)

    elif len(args) != 1:

        response += messages.notificationArgumentRequiredError(bot.messenger)

    elif not util.isInt(args[0]) or int(args[0]) < 0 or int(args[0]) > 1:

        response += messages.notificationArgumentInvalidError(bot.messenger)

    else:

        action(user['id'], args[0])

        response += messages.notificationResponse(bot.messenger, description.lower(), int(args[0]))

    return response
