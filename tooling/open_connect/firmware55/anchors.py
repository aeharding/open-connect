"""Exact OEM input anchors shared by the selected startup builder."""

INDEX_SHA = "b0e116b941f29078ced19b864a1b888cf76d8bc3e4974af081efca4693e5c420"
PLUGIN_SHA = "2c2c0494817b13a38c36a8276a39899b4096efc217e82568fe3842f8b34bb025"


def replace_once(data, old, new):
    if data.count(old) != 1:
        raise ValueError("expected one exact composition anchor")
    return data.replace(old, new)
