"""Client-IP resolution behind a hosting proxy.

In production the app sits behind Railway's edge, so every request
arrives from the proxy. The classroom network check is only as good as
the address it is handed, which makes this the most security-sensitive
piece of plumbing in the deployment.
"""

import pytest

from services.network_service import client_ip, ip_matches


class FakeRequest:
    def __init__(self, remote_addr, forwarded=None):
        self.remote_addr = remote_addr
        self.headers = {}
        if forwarded is not None:
            self.headers["X-Forwarded-For"] = forwarded


# --- With no declared proxy, the header is ignored ----------------------

def test_forwarded_header_ignored_when_no_proxy_declared():
    """The default. A client-writable header must not decide anything."""
    request = FakeRequest("10.0.0.9", forwarded="203.0.113.44")
    assert client_ip(request, trusted_proxy_count=0) == "10.0.0.9"


def test_connection_address_used_when_no_header():
    request = FakeRequest("198.51.100.7")
    assert client_ip(request, trusted_proxy_count=0) == "198.51.100.7"


# --- With one declared proxy, the last hop is the client ----------------

def test_one_proxy_reads_the_last_hop():
    """Railway appends the real client, so the last entry is the student."""
    request = FakeRequest("10.0.0.9", forwarded="203.0.113.44")
    assert client_ip(request, trusted_proxy_count=1) == "203.0.113.44"


def test_client_supplied_prefix_cannot_win():
    """A student prepending a fake address gets ignored.

    With one trusted proxy only the last entry is read, and the proxy
    appends the true address itself -- so the forged entries sit
    harmlessly to the left.
    """
    request = FakeRequest(
        "10.0.0.9", forwarded="1.2.3.4, 5.6.7.8, 203.0.113.44"
    )
    assert client_ip(request, trusted_proxy_count=1) == "203.0.113.44"


def test_two_proxies_step_back_two_hops():
    request = FakeRequest("10.0.0.9", forwarded="203.0.113.44, 172.16.0.1")
    assert client_ip(request, trusted_proxy_count=2) == "203.0.113.44"


def test_falls_back_when_header_is_shorter_than_declared():
    """Claiming more proxies than exist must not read a forged entry."""
    request = FakeRequest("10.0.0.9", forwarded="203.0.113.44")
    assert client_ip(request, trusted_proxy_count=3) == "10.0.0.9"


def test_whitespace_and_empties_are_tolerated():
    request = FakeRequest("10.0.0.9", forwarded="  , 203.0.113.44 ,  ")
    assert client_ip(request, trusted_proxy_count=1) == "203.0.113.44"


def test_missing_remote_addr_gives_empty_string():
    assert client_ip(FakeRequest(None), trusted_proxy_count=0) == ""


# --- Matching the resolved address against a classroom ------------------

@pytest.mark.parametrize(
    "ip,networks,expected",
    [
        ("203.0.113.44", ["203.0.113.44"], True),
        ("203.0.113.44", ["203.0.113.0/24"], True),
        ("203.0.113.44", ["198.51.100.0/24"], False),
        ("192.168.1.20", ["192.168.0.0/16"], True),
        ("8.8.8.8", ["192.168.0.0/16", "10.0.0.0/8"], False),
        # A malformed entry must never widen access.
        ("203.0.113.44", ["not-an-ip", "203.0.113.44"], True),
        ("203.0.113.44", ["not-an-ip"], False),
        # Nothing configured means nothing matches.
        ("203.0.113.44", [], False),
        ("", ["203.0.113.44"], False),
    ],
)
def test_ip_matching(ip, networks, expected):
    assert ip_matches(ip, networks) is expected


def test_the_production_shape_end_to_end():
    """A student on college Wi-Fi, seen through Railway's proxy."""
    college_egress = "203.0.113.44"
    classroom_networks = ["203.0.113.0/24"]

    request = FakeRequest("10.0.0.9", forwarded=college_egress)
    resolved = client_ip(request, trusted_proxy_count=1)

    assert ip_matches(resolved, classroom_networks)

    # The same student at home fails, which is the whole point.
    at_home = FakeRequest("10.0.0.9", forwarded="198.51.100.9")
    assert not ip_matches(
        client_ip(at_home, trusted_proxy_count=1), classroom_networks
    )
