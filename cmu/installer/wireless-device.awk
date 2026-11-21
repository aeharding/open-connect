# SPDX-License-Identifier: AGPL-3.0-or-later
# Filter Mazda's already-rendered RAM configuration. Preserve its other values.
/bWifiSupport/ {
    wifi++
    if ($0 !~ /^<config><name>bWifiSupport<\/name><value>(FALSE|TRUE)<\/value><\/config>\r?$/) exit 1
    sub(/<value>FALSE<\/value>/, "<value>TRUE</value>")
}
/bOOBSupport/ {
    oob++
    if ($0 !~ /^<config><name>bOOBSupport<\/name><value>(FALSE|TRUE)<\/value><\/config>\r?$/) exit 1
    sub(/<value>FALSE<\/value>/, "<value>TRUE</value>")
}
{ print }
END { if (wifi != 1 || oob != 1) exit 1 }
