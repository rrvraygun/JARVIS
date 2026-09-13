# Repair gates

Filesystem writes, partition changes, boot repair, package database recovery,
identity/permission changes, firewall/remote-access changes, firmware, and data
reconstruction are high risk. Prefer offline or vendor-supported recovery paths.
Do not run filesystem repair on a mounted filesystem unless the tool and exact
mode explicitly support it. Never delete evidence of suspected compromise before
incident preservation and containment decisions.
