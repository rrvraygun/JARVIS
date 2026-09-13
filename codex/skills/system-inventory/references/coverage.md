# Inventory coverage

Collect only what the task needs: OS release, kernel, boot mode, CPU, memory,
graphics, block devices, mounts, filesystem capacity, encryption indicator,
package managers, repository channels, installed kernels, failed services,
listening sockets, firewall status, security modules, containers/VMs, thermal or
battery state, SMART/NVMe health, backup/snapshot facilities, Codex version, and
recent change records. Mark unavailable evidence unknown; do not infer health.

The initial Fedora collector intentionally excludes hostname, username, IP
addresses, machine ID, serial numbers, browser data, document contents,
credential stores, and environment dumps until encrypted user-unlocked storage
exists. Add protected reads only through a separately reviewed collector revision
and user confirmation.
