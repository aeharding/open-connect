#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# v74 WCP startup: preserve Mazda's filter policy with one atomic commit.
# The OEM script still owns developer/UCP modes and any optimization refusal.
set -u
PATH=/sbin:/usr/sbin:/bin:/usr/bin
export PATH
if test "$#" -ne 0 || test -f /data/integration/developer_mode_on_flag; then
    exec /jci/scripts/start_network.sh "$@"
fi

module_loaded() {
    local wanted=$1 name rest
    while read -r name rest; do
        if test "$name" = "$wanted"; then return 0; fi
    done < /proc/modules
    return 1
}

firewall_start() {
    local path name
    # Keep dependency order; avoid slow implicit loading for hashlimit/REJECT.
    for path in net/netfilter/x_tables net/ipv4/netfilter/ip_tables \
        net/ipv4/netfilter/iptable_filter net/netfilter/nf_conntrack \
        net/netfilter/xt_state net/ipv4/netfilter/nf_defrag_ipv4 \
        net/ipv4/netfilter/nf_conntrack_ipv4 net/netfilter/xt_tcpudp \
        net/netfilter/xt_limit net/netfilter/xt_hashlimit net/ipv4/netfilter/ipt_REJECT; do
        name=${path##*/}
        module_loaded "$name" || insmod "/lib/modules/3.0.35/kernel/$path.ko" || return 1
    done
    /usr/sbin/iptables-restore <<'RULES'
*filter
:INPUT DROP [0:0]
:FORWARD DROP [0:0]
:OUTPUT ACCEPT [0:0]
:wcp_packets - [0:0]
-A wcp_packets -p tcp -i wlan0 -m state --state ESTABLISHED,RELATED -m hashlimit --hashlimit 1667/sec --hashlimit-mode dstip --hashlimit-burst 1000 --hashlimit-name 25Mbps -j ACCEPT
-A wcp_packets -p tcp -i wlan0 -m state --state ESTABLISHED,RELATED -j REJECT --reject-with icmp-port-unreachable
-A wcp_packets -p udp -i wlan0 --dport 5353 -j ACCEPT
-A wcp_packets -p tcp -i wlan0 --dport 5000 -j ACCEPT
-A wcp_packets -p tcp -i wlan0 --dport 7000 -j ACCEPT
-A wcp_packets -p tcp -i wlan0 --dport 32768:61000 -j ACCEPT
-A wcp_packets -p udp -i wlan0 --dport 32768:61000 -j ACCEPT
-A INPUT -i lo -j ACCEPT
-A OUTPUT -o lo -j ACCEPT
-A INPUT -m state --state INVALID -j DROP
-A OUTPUT -m state --state INVALID -j DROP
-A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
-A INPUT -p tcp -i wlan0 --dport 36000 -m state --state NEW,ESTABLISHED -j DROP
-A INPUT -p tcp --dport 36000 -m state --state NEW,ESTABLISHED -j ACCEPT
-A INPUT -p udp -i wlan0 --sport 68 --dport 67 -j ACCEPT
-A INPUT -p tcp -i wlan0 --sport 68 --dport 67 -j ACCEPT
-A INPUT -p udp -i wlan0 --dport 53 -m state --state NEW -j ACCEPT
-A INPUT -p tcp -i wlan0 --dport 53 -m state --state NEW -j ACCEPT
-A INPUT -p icmp --icmp-type echo-request -j DROP
COMMIT
RULES
}

# SM treats even a failed exited process as STARTED. Preserve the OEM startup
# path on refusal rather than leaving its dependents with a partial replacement.
if ! firewall_start; then
    printf 'Open Connect: using OEM network startup\n' >&2
    exec /jci/scripts/start_network.sh "$@"
fi
printf 'Open Connect: atomic WCP firewall committed\n'

if test -f /data/integration/eth0_on_flag; then
    insmod /lib/modules/3.0.35/kernel/drivers/net/phy/smsc.ko
    insmod /lib/modules/3.0.35/kernel/drivers/net/fec.ko
    ifplugd -M -I -i eth0
fi
insmod /lib/modules/3.0.35/kernel/drivers/net/usb/usbnet.ko
insmod /lib/modules/3.0.35/kernel/drivers/net/usb/asix.ko
/jci/scripts/start_eth1_dhcp.sh &
/usr/sbin/sshd
touch /var/run/start_network_ready
