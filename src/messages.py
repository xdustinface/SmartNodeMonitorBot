#!/usr/bin/env python3

def splitMessage(text, split, maximum):

    # When the message is longer then the max allowed size
    # split it at double linebreaks to make sure its well readable
    # when the message comes in parts.
    if len(text) > maximum:

        parts = []

        searchIndex = 0

        while True:

            if len(text[searchIndex:]) <= maximum:
                parts.append(text[searchIndex:])
                break

            splitIndex = text.rfind(split,searchIndex,maximum + searchIndex)

            if searchIndex == 0 and splitIndex == -1:
                # If there is no split string, split it just at the
                # length limit.
                parts = [text[i:i + limit] for i in range(0, len(text), maximum)]
                break
            elif searchIndex != 0 and splitIndex == -1:
                # If there was a split string in the message but the
                # next part of the message hasnt one split the rest of the message
                # at the length limit if its still exceeds it.
                parts.extend([text[i:i + maximum] for i in range(searchIndex, len(text), maximum)])
            elif splitIndex != -1:
                # Found a sweet spot to to split
                parts.append(text[searchIndex:splitIndex])
                searchIndex = splitIndex
            else:
                logger.warning("Split whatever..")
                # ...

        return parts

    else:
        return [text]

def removeMarkdown(text):
    clean = text.replace('_','')
    clean = clean.replace('*','')
    clean = clean.replace('`','')
    return clean

def markdown(text,messenger):

    msg = text.replace('<c>','`')

    if messenger == 'telegram':
        msg = msg.replace('<b>','*')
        msg = msg.replace('<u>','')
        msg = msg.replace('<cb>','/')
        msg = msg.replace('<ca>','')
        msg = msg.replace('<c>','`')
    elif messenger == 'discord':
        msg = msg.replace('<u>','__')
        msg = msg.replace('<b>','**')
        msg = msg.replace('<cb>','`')
        msg = msg.replace('<ca>','`')

    return msg

def link(messenger, link, text = ''):

    msg = link

    if messenger == 'telegram':
        msg = "[{}]({})".format(text,link)
    elif messenger == 'discord':
        msg = "<{}>".format(link)

    return msg


def help(messenger):

    helpMsg =  ("You can use this bot to monitor your SmartNodes and subscribe event notifications. "
                "Once you added your nodes with <cb>add<ca> and enabled the desired notifications"
                " with the commands below you will receive a message from the bot on each "
                "occured event!\n\n"
                "<b>Common commands<b>\n\n"
                "<cb>help<ca> - Print this help\n"
                "<cb>info<ca> - Print the current status of the SmartNode network\n\n"
                "<cb>lookup<ca> <b>ip0 .. ipN<b> - Check the payout requirements of one or multiple nodes\n\n"
                "<b>User commands<b>\n\n"
                "<cb>status<ca> <b>:enabled<b> - Set :enabled to 0 to disable or to 1 to receive a notification when one of your node's status changed.\n"
                "<cb>reward<ca> <b>:enabled<b> - Set :enabled to 0 to disable or to 1 to receive a notification each time one of your nodes received a reward.\n"
                "<cb>timeout<ca> <b>:enabled<b> - Set :enabled to 0 to disable or to 1 to receive a notification when the seen timestamp of your node is > 30min.\n"
                "<cb>network<ca> <b>:enabled<b> - Set :enabled to 0 to disable or to 1 to enable network notifications\n\n"
                "<cb>me<ca> - List your user info and notification states\n"
                "<cb>username<ca> <b>:newname<b> - Change your username to :newname\n\n"
                "<b>Node commands<b>\n\n"
                "<cb>add<ca> <b>ip0;name0 ip1;name1 ... ipN;nameN<b> - Add one or multiple nodes. Use a list of ip;name pairs as arguments.\n"
                "  <b>Example<b>: add 23.123.213.11;Node1 22.122.212.12;Node2\n"
                "<cb>update<ca> <b>:ip :newname<b> - Change the name of a node with its IP-Address\n"
                "<cb>remove<ca> <b>:ip<b> - Remove one of your nodes with its IP-Address\n"
                "<cb>balance<ca> - List the SMART balances of your SmartNodes\n"
                "<cb>detail<ca> - List all details of your SmartNodes\n"
                "<cb>nodes<ca> - List only the status and last payments of your nodes\n\n")

    if messenger == 'discord':
        helpMsg = helpMsg.replace("<cb>username<ca> <b>:newname<b> - Change your username to :newname\n\n",'\n\n')

    helpMsg = markdown(helpMsg, messenger)

    return helpMsg


############################################################
#                      Common messages                     #
############################################################

def networkState(messenger, last, created, enabled, qualifiedNormal,
                 qualifiedUpgrade, upgradeModeDuration, protocolRequirement,
                 protocol90024, protocol90025, initialWaitString):

    message = ("<b>Current block<b> {}\n\n"
                "<b>Nodes created<b> {}\n"
                "<b>Nodes enabled<b> {}\n").format(last,
                                                      created,
                                                      enabled)

    minPosition = enabled * 0.1
    minEligible = int(enabled / 3)

    if qualifiedUpgrade != -1:
        message += "<b>Nodes qualified<b> {}\n".format(qualifiedUpgrade)
        message += "<b>Nodes qualified (UpgradeMode)<b> {}\n\n".format(qualifiedNormal)
    else:
        message += "<b>Nodes qualified<b> {}\n\n".format(qualifiedNormal)

    message += ("<b>Protocol requirement<b> {}\n\n"
                "<b>Nodes with 90024<b> {}\n"
                "<b>Nodes with 90025<b> {}\n\n").format(protocolRequirement,
                                                        protocol90024,
                                                        protocol90025)

    message += "<u><b>Initial payout/Minimum uptime<b><u>\n\n"

    message += ("The current <b>minimum<b> uptime after a restart to be eligible for"
                   " SmartNode rewards is <b>{}<b>\n\n").format(initialWaitString)
    message += ("Once your node has reached the minimum uptime requirement it may"
                " join the payout queue if the other requirements are met.\n\n")

    ####
    # Check if the network is in upgrade mode.
    #
    #https://github.com/SmartCash/smartcash/blob/1.1.1/src/smartnode/smartnodeman.cpp#L655
    ####
    if qualifiedUpgrade != -1:
        message += ("<b>The network is currenty in upgrade mode<b>. Recently started nodes"
        " do also do have the chance to get paid - <b>The minimum uptime above does not matter<b> - if their collateral transaction has"
        " at least {} confirmations. Your nodes's position needs to be less than {}"
        " to be in the random payout zone. If you are there you have the <b>chance<b> get paid"
        " from now on but in the <b>worst<b> case it still might take some days.\n\n").format(enabled, int(minPosition))

        message += ("The upgrade mode will be active until <b>{}<b> nodes has become eligible. Right now we have <b>{}<b> of them.\n\n").format(minEligible, qualifiedUpgrade)

        if upgradeModeDuration:
            message += "<b>Remaining upgrade mode duration<b> ~{}\n\n".format(upgradeModeDuration)

    message += "<u><b>Further payouts<b><u>\n\n"
    message += ("Once you received your first payout your node's position"
               " currenty needs to be less than <b>{}<b>"
               " to be in the random payout zone. If you are there you have the <b>chance<b> get paid"
               " from now on but in the <b>worst<b> case it still might take some days.\n\n").format(int(minPosition))

    # Use qualifiedNormal instead of (qualifiedNormal * 0.9) to give the worst case
    message += "<b>Reaching the payout zone<b> should currently take roughly <b>{}<b> days\n\n".format(int(qualifiedNormal / 1570))

    message += "<u><b>Warning<b><u>\n\n"
    message += "The positions of your nodes and the calculations above should be quite accurate but <b>please keep in mind that they may be inaccurate in special cases until the wallet version 1.2.0 is released<b> which should fix the current issues".format(int(qualifiedNormal / 1570))

    return markdown(message,messenger)

def lookupResult(messenger, result):

    def resultEmoji(value):
        return "✅" if value else "🛑"

    message = "<u><b>Result {}<b><u>\n\n".format(result['ip'])

    message += "  {} <b>Position<b> - ".format(resultEmoji(result['position']))
    message += result['position_string'] + "\n\n"

    message += "  {} <b>Status<b> - ".format(resultEmoji(result['status']))
    message += result['status_string'] + "\n\n"

    message += "  {} <b>Collateral confirmations<b> - ".format(resultEmoji(result['collateral']))
    message += result['collateral_string'] + "\n\n"

    if result['upgrade_mode']:
        message += "  {} <b>Uptime (upgrade mode)<b> - ".format(resultEmoji(True))
        message += result['uptime_string'] + "\n\n"
    else:
        message += "  {} <b>Uptime<b> - ".format(resultEmoji(result['uptime']))
        message += result['uptime_string'] + "\n\n"

    message += "  {} <b>Protocol<b> - ".format(resultEmoji(result['protocol']))
    message += result['protocol_string'] + "\n\n"

    return markdown(message,messenger)


############################################################
#                      User messages                       #
############################################################

def notificationState(messenger, state):
    if state:
        return markdown("<b>Enabled<b>",messenger)
    else:
        return markdown("<b>Disabled<b>",messenger)

def notificationResponse(messenger, description, state):
    if state:
        return markdown("Succesfully <b>enabled<b> {} notifications.".format(description),messenger)
    else:
        return markdown("Succesfully <b>disabled<b> {} notifications.".format(description),messenger)

def statusNotification(messenger, nodeName, status):
    return markdown(("<u><b>Status update<b><u>\n\n"
                          "Your node <b>{}<b> changed its "
                          "status to <b>{}<b>").format(nodeName,status),messenger)

def panicNotification(messenger, nodeName, timeString):
    response = ("<u><b>Panic!<b><u>\n\n"
                "Your node <b>{}<b> has been last seen before\n").format(nodeName)
    response += timeString

    return markdown(response, messenger)

def relaxNotification(messenger, nodeName):
    response = ("<u><b>Relax!<b><u>\n\n"
                "Your node <b>{}<b> is back!\n").format(nodeName)
    return markdown(response,messenger)

def rewardNotification(messenger, nodeName, block, reward ):

    response = ("<u><b>Reward!<b><u>\n\n"
                "Your node <b>{}<b> received a "
                "reward at block {}\n\n"
                "Payout <b>~{} SMART<b>").format(nodeName, block, int(reward))

    return markdown(response, messenger)

def nodeRemovedNotification(messenger, nodeName):
    return markdown(("<u><b>Warning!<b><u>\n\n"
                      "Your node <b>{}<b> has been removed "
                      "from the global nodelist.").format(nodeName), messenger)

############################################################
#                     Error messages                       #
############################################################

def notActiveError(messenger):
    return markdown(("<b>ERROR<b>: You have currently no added nodes. "
                         "Add a node first with <cb>add<ca>."),messenger)

def rateLimitError(messenger, seconds):
    return markdown("<b>Sorry, you hit the rate limit. Take a deep breath...\n\n{} to go!<b>".format(seconds),messenger)

def userNameRequiredError(messenger):
    return markdown("<b>ERROR<b>: Exactly 1 argument required: new_user_name",messenger)

def invalidParameterError(messenger,arg):
    clean = removeMarkdown(arg)
    return markdown("<b>ERROR<b>: Invalid parameter: {}\n".format(clean),messenger)

def invalidSmartAddressError(messenger,address):
    return markdown("<b>ERROR<b>: Invalid SMART-Address: {}\n".format(address),messenger)

def invalidIpError(messenger,ip):
    clean = removeMarkdown(ip)
    return markdown("<b>ERROR<b>: Invalid IP-Address: {}\n".format(clean),messenger)

def invalidNameError(messenger, name):
    clean = removeMarkdown(name)
    return markdown("<b>ERROR<b>: Invalid name (Length: 1-20, Only A-Z, a-z, 0-9, .#-): {}\n".format(clean),messenger)

def nodeExistsError(messenger, node):
    clean = removeMarkdown(node)
    return markdown("<b>ERROR<b>: Node already exists {}\n".format(clean),messenger)

def nodeNotExistsError(messenger, node):
    clean = removeMarkdown(node)
    return markdown("<b>ERROR<b>: Node does not exist in your list! {}\n".format(clean),messenger)

def nodeNotInListError(messenger, node):
    clean = removeMarkdown(node)
    return markdown("<b>ERROR<b>: Address doest not exists in the global nodelist. {}\n".format(node),messenger)

def notificationArgumentRequiredError(messenger):
    return markdown("<b>ERROR<b>: Exactly 1 argument required: 0 (Disable), 1 (Enable)\n",messenger)

def notificationArgumentInvalidError(messenger):
    return markdown("<b>ERROR<b>: Invalid argument value: 0 (Disable), 1 (Enable)\n",messenger)

def notAvailableInGroups(messenger):
    return markdown("<b>Sorry, this command is not available in groups.<b>",messenger)

def nodesRequired(messenger):
    return markdown(("You need to add nodes first. "
             "Type <cb>help<ca> to show the list of commands."),messenger)

def lookupArgumentRequiredError(messenger):
    return markdown(("<b>ERROR<b>: Aguments required. You can lookup one or multiple IP's: ip0 ip1 ... ipN\n"
                    "<b>Example<b>: <cb>lookup 222.222.222.222<ca>"),messenger)

def lookupError(messenger, ip):
    return markdown("<b>ERROR<b>: Could not check ip {}\n".format(ip),messenger)
