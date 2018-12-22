from __future__ import print_function, unicode_literals
import sys
import re
from collections import namedtuple
from twisted.internet.endpoints import HostnameEndpoint

# These namedtuples are "hint objects". The JSON-serializable dictionaries
# are "hint dicts".

# DirectTCPV1Hint and TorTCPV1Hint mean the following protocol:
# * make a TCP connection (possibly via Tor)
# * send the sender/receiver handshake bytes first
# * expect to see the receiver/sender handshake bytes from the other side
# * the sender writes "go\n", the receiver waits for "go\n"
# * the rest of the connection contains transit data
DirectTCPV1Hint = namedtuple("DirectTCPV1Hint",
                             ["hostname", "port", "priority"])
TorTCPV1Hint = namedtuple("TorTCPV1Hint", ["hostname", "port", "priority"])
# RelayV1Hint contains a tuple of DirectTCPV1Hint and TorTCPV1Hint hints (we
# use a tuple rather than a list so they'll be hashable into a set). For each
# one, make the TCP connection, send the relay handshake, then complete the
# rest of the V1 protocol. Only one hint per relay is useful.
RelayV1Hint = namedtuple("RelayV1Hint", ["hints"])

def describe_hint_obj(hint, relay, tor):
    prefix = "tor->" if tor else "->"
    if relay:
        prefix = prefix + "relay:"
    if isinstance(hint, DirectTCPV1Hint):
        return prefix + "tcp:%s:%d" % (hint.hostname, hint.port)
    elif isinstance(hint, TorTCPV1Hint):
        return prefix + "tor:%s:%d" % (hint.hostname, hint.port)
    else:
        return prefix + str(hint)

def parse_hint_argv(hint, stderr=sys.stderr):
    assert isinstance(hint, type(u""))
    # return tuple or None for an unparseable hint
    priority = 0.0
    mo = re.search(r'^([a-zA-Z0-9]+):(.*)$', hint)
    if not mo:
        print("unparseable hint '%s'" % (hint, ), file=stderr)
        return None
    hint_type = mo.group(1)
    if hint_type != "tcp":
        print("unknown hint type '%s' in '%s'" % (hint_type, hint),
              file=stderr)
        return None
    hint_value = mo.group(2)
    pieces = hint_value.split(":")
    if len(pieces) < 2:
        print("unparseable TCP hint (need more colons) '%s'" % (hint, ),
              file=stderr)
        return None
    mo = re.search(r'^(\d+)$', pieces[1])
    if not mo:
        print("non-numeric port in TCP hint '%s'" % (hint, ), file=stderr)
        return None
    hint_host = pieces[0]
    hint_port = int(pieces[1])
    for more in pieces[2:]:
        if more.startswith("priority="):
            more_pieces = more.split("=")
            try:
                priority = float(more_pieces[1])
            except ValueError:
                print("non-float priority= in TCP hint '%s'" % (hint, ),
                      file=stderr)
                return None
    return DirectTCPV1Hint(hint_host, hint_port, priority)

def endpoint_from_hint_obj(hint, tor, reactor):
    if tor:
        if isinstance(hint, (DirectTCPV1Hint, TorTCPV1Hint)):
            # this Tor object will throw ValueError for non-public IPv4
            # addresses and any IPv6 address
            try:
                return tor.stream_via(hint.hostname, hint.port)
            except ValueError:
                return None
        return None
    if isinstance(hint, DirectTCPV1Hint):
        return HostnameEndpoint(reactor, hint.hostname, hint.port)
    return None
