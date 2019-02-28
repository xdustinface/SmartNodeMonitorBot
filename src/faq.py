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

import logging, time

from src import messages
from src import util

from fuzzywuzzy import process as fuzzy

log = logging.getLogger("faq")

header = "<u><b>Frequently asked questions<b><u>\n\n"

class FAQ(object):

    def __init__(self, question, answerCB):
        self.question = question
        self.answerCB = answerCB

def qualified(bot):

    with bot.nodeList as nodeList:

        if not nodeList.synced() or not nodeList.enabled():
            return messages.notSynced(bot.messenger)

        confirmations = int(nodeList.enabledWithMinProtocol() / 0.5)
        initialWait = util.secondsToText(nodeList.minimumUptime())
        protocolRequirement = nodeList.protocolRequirement()

        return (
        "Your node has to match the following requirements before it's ready to"
        " receive payouts\n\n"
        "- The node's status has to be <b>ENABLED<b>\n"
        "- The node's collateral transaction needs to have at least <b>{}<b>"
        " confirmations\n"
        "- The node must have a minimum uptime of <b>{}<b>\n"
        "- The node must run at least on the protocol <b>{}<b> number\n\n"
        "Once your node matches <b>all<b> the above requirements it will get a"
        " position in the payout queue.\n\n"
        "You can check all this requirements for your nodes when you send me"
        " <cb>detail<ca> or by running the <cb>lookup<ca> command.\n\n"
        ).format(confirmations, initialWait, protocolRequirement)

def position(bot):

    with bot.nodeList as nodeList:

        if not nodeList.synced() or not nodeList.enabled():
            return messages.notSynced(bot.messenger)


        nodes = nodeList.count()
        enabled = nodeList.enabled()
        qualified = nodeList.qualifiedNormal
        unqualified = nodes - qualified
        minPosition = int(enabled * 0.1)
        top10Seconds = (int((qualified * 55) / 0.5) * (1 + bot.aberration))
        topNode = list(filter(lambda x: x.position == minPosition, nodeList.nodes.values()))

        if len(topNode) and topNode[0].lastPaidTime:
            top10FromList = time.time() - topNode[0].lastPaidTime
            if top10FromList < 1.2 * top10Seconds:
                top10Seconds = top10FromList

        top10Time = util.secondsToText(top10Seconds)

        return (
        "We have currenty <b>{}<b> qualified SmartNodes. All those are in a "
        "virtual payout queue. Every other mined block (2*55seconds) one "
        "of the nodes in the top 10% of that queue gets picked perchance and"
        " receives a payout. After that it moves back to the end of the queue.\n\n"
        "The position of your node represents the position in the queue. Once "
        "your node has a position <b>less<b> than (currently) <b>{}<b>"
        " it is in the <b>random payout zone<b> (top 10%).\n\n"
        "The minimum position depends on the number of enabled nodes and will change"
        " when the number of enabled nodes changes.\n\n"
        "Right now it takes <b>{}<b> to reach the payout zone.\n\n"
        "It's normal and to be expected that your nodes moves also backwards a "
        "bit in the queue from time to time. This happens each time a node that"
        " has received its last payment longer ago as yours becomes eligible"
        " for payouts (it jumpes into the queue and receives a position)."
        " At this moment we have <b>{}<b> SmartNodes. <b>{}<b> of them are"
        " <b>not<b> qualified for payouts. Each time one of the unqualified"
        " nodes becomes eligible due to a full match of the requirements"
        " it is very likely that it will jump ahead of yours.\n\n"
        "You can send me <cb>info<ca> to see the number of qualified nodes, "
        "to check your nodes positions send me <cb>detail<ca>, <cb>nodes<ca>"
        " <cb>top<ca> or use the <cb>lookup<ca> command.\n\n"
        ).format(qualified, minPosition, top10Time, nodes, unqualified)

def collateral(bot):

    with bot.nodeList as nodeList:

        if not nodeList.synced() or not nodeList.enabled():
            return messages.notSynced(bot.messenger)

        confirmations = int(nodeList.enabledWithMinProtocol() / 0.5)
        timeString = util.secondsToText(confirmations * 55)

        return (
        "A too new collateral means that your nodes collateral transaction (the 100k one) does not"
        " have the minimum required number of confirmations in the SmartCash blockchain."
        "This number of confirmations is currently <b>{}<b>.\nYour collateral gets 1 confirmation with each"
        " new mined block.\n\nMeans right now you need to wait {} x 55 seconds => <b>~{}<b> until"
        " your collateral transaction matches the requirement.\n\n"
        "You can check your nodes collateral confirmations"
        " by running the <cb>lookup<ca> command.\n\n"
        ).format(confirmations, confirmations, timeString)

def initial(bot):

    with bot.nodeList as nodeList:

        if not nodeList.synced() or not nodeList.enabled():
            return messages.notSynced(bot.messenger)

        initialWait = util.secondsToText(nodeList.minimumUptime())

        return (
        "When your node shows <b>Initial wait time<b> instead of a position it's"
        " uptime does not match the minimum uptime requirement. At this time the"
        " node must have a minimum uptime of <b>{}<b>."
        " Your uptime will be set to zero when your node was down for more than"
        " <b>2 hours<b> or when you issue a <b>new start<b> of the node with your desktop wallet"
        " by running <c>Start alias<c>.\n\n"
        "You can check your node's uptime when you send me <cb>detail<ca> or by"
        " running the <cb>lookup<ca> command.\n\n"
        ).format(initialWait)

def rewards(bot):

    with bot.nodeList as nodeList:

        if not nodeList.synced() or not nodeList.enabled():
            return messages.notSynced(bot.messenger)

        enabled = nodeList.enabled()
        minPosition = int(enabled * 0.1)
        qualified = nodeList.qualifiedNormal
        lastBlock = nodeList.lastBlock

        # Fallback if for whatever reason the top node could not filtered which
        # should actually not happen.
        top10Seconds = (int((qualified * 55) / 0.5) * (1 + bot.aberration))

        topNode = list(filter(lambda x: x.position == minPosition, nodeList.nodes.values()))

        if len(topNode) and topNode[0].lastPaidTime:
            top10FromList = time.time() - topNode[0].lastPaidTime
            if top10FromList < 1.2 * top10Seconds:
                top10Seconds = top10FromList

        payoutSeconds = top10Seconds + (10 * 60 * 60)
        payoutDays = payoutSeconds / 86400.0
        interval = util.secondsToText(int(payoutSeconds))
        currentReward = round(5000.0 * 143500.0 / lastBlock * 0.1,1) / 0.5
        perMonth = round((30.5 / payoutDays) * currentReward,1)

        return (
        "The SmartNode rewards are calculated by the following formula\n\n"
        "```reward = 5000 x 143500 / blockHeight * 0.1```\n\n"
        "At this moment our blockchain is at the height <b>{}<b> that means"
        "\n\n```5000 x 143500 / {} * 0.1 => {} SMART per block```\n\n"
        "Each block with an <b>even<b> blockheight one of the the nodes receive this reward for 2 blocks. With the current "
        "estimated payout interval of <b>{}<b> you can expect roughly"
        " <b>{:,} SMART<b> per month per SmartNode. This can vary a bit upwards and downwards though.\n\n"
        "Due to the constant increase of the <c>blockHeight<c> of the SmartCash blockchain"
        " the rewards will decrease a little bit every 55 seconds."
        " Also the increase of the number of qualified nodes will increase the payout interval."
        " As result your monthly payout will slightly decrease over the time.\n\n"
        "You can look at the chart in the link below to see the reward decrease "
        "for the first 4 years after the SmartNode launch.\n\n"
        ).format(lastBlock, lastBlock, currentReward, interval, perMonth)\
        + messages.link(bot.messenger, "https://goo.gl/Va817H", "Click here to open the chart")

def status(bot):

    return (
    "First you should check your node's status by running "
    "<c>smartcash-cli smartnode status<c> on your node's VPS.\n\n"
    "The status of your node can hint towards the problem of why your "
    "node isn't running. Here are the known states and their likely causes:\n\n"
    "<b>Node just started, not yet activated<b>\n\n"
    "Simply means your blocks aren't up-to-date yet with the current "
    "blockcount. Run <c>smartcash-cli getinfo<c> on the VPS to see your current "
    "blockHeight at <c>blocks<c>, and compare it to the current blockHeight that "
    "you can see when you send me <cb>info<ca>\n\n"
    "<b>Broadcast IP doesn't match external IP<b>\n\n"
    "Most likely culprit is a duplicate IP/genkey/txhash in the "
    "config file. Verify that all node entries in the <c>smartnode.conf<c> file "
    " have a unique IP/genkey/txhash+id. If your VPS has multiple IP's, adding "
    "externalip=yourNodeIP in the <c>smartcash.conf<c> of a daemon will direct it"
    " towards the IP you specified.\n\n"
    "<b>Not capable smartnode: invalid protocol version<b>\n\n"
    "Your node is not up-to-date on the latest version. Compare the version you"
    " see when you run <c>smartcash-cli getinfo<c> at <c>version<c> to the latest version at ") +\
    messages.link(bot.messenger, "https://smartcash.cc/wallets/", "SmartCash wallets") +\
    (" for more info on the current version.\n\n"
    "<b>Not capable smartnode: smartnode not in smartnodelist<b>\n\n"
    "The node hasn't yet connected to the network. This can have "
    "several reasons; your desktop-wallet is outdated, your node is "
    "outdated or you didn't yet issue a <c>Start alias<c> command while the "
    "desktop-wallet was synced.")

faqs = {
    'qualified' : FAQ("What are the requirements for my node to be qualified for payouts?",
             qualified ),
    'position' : FAQ( "What is the <b>position<b> of my node and how do i check it? Why does my node move up in its position?",
              position ),
    'collateral' : FAQ("What does <b>collateral too new<b> mean?",
              collateral ),
    'initial' : FAQ("What does <b>Initial wait time<b> mean?",
             initial ),
     'rewards' : FAQ("What payouts can i expect from my nodes?",
              rewards ),
    'status' : FAQ(("What should be done when a SmartNode is <b>not<b> successfully started?"),
             status )
}

def topicList():

    message = ""

    for topic, q in faqs.items():
        message += "<c>{}<c> - {}\n".format(topic, q.question)

    return message

def unknown(ask):

    message = "Sorry, i dont know anything about <b>{}<b>\n\n".format(ask)
    message += "Try one of the following topics\n\n"

    return message + topicList()

def help():

    message = topicList()

    message += "\nTo get information about any of the available topics send me <cb>faq<ca> topic\n\n"
    message += "If you have anything else that should be covered here - send a message to @dustinface\n\n"

    return message

def parse(bot, args):

    message = help()

    if len(args):

        ask = " ".join(args)

        choices = fuzzy.extract(ask,faqs.keys(),limit=2)

        if choices[0][1] == choices[1][1] or choices[0][1] < 60:
            log.warning('Invalid fuzzy result {} - {}\n'.format(ask, choices))
            message = unknown(ask)
        else:

            topic = choices[0][0]

            message = "<b>" + faqs[topic].question + "<b>\n\n" + faqs[topic].answerCB(bot)

    return messages.markdown(header + message,bot.messenger)
