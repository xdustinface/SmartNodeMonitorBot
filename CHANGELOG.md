# v1.0

- Initial version
- Telegram support
- Discord support

# v1.1
- Position integration
- Upgrade mode calculations
- Node lookup command
- Improved info command
- Update/Remove multiple nodes with one command call
- Backend update
  - Removed the need of the node-id column in the database
  - Use the collateral as primary key
- The command `nodes` prints the nodes now sorted by position.
- Timeout notification improvements.

# 2.0
- Using the python-smartcash module for rpc stuff now instead of the ugly cli subprocess calls
- Maintain a node reward database where missing/false rewards are tracked
- Makes use of the new reward database to improve the reward notifications. **All** rewards should be notified from now on!
- New node `history` command which shows past payouts for all nodes
- Restrict the lookup command to DM
- Show remaining wait time for nodes in the initial wait phase
- New node `top` command to show only nodes in the top X percent
