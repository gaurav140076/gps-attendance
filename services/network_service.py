"""Classroom network verification.

The strongest cheap signal a web application has is where the request
came from. A student at home on mobile data fails this no matter how
perfect their coordinates are, because they cannot forge the source
address of a connection they need the replies to.
"""

import ipaddress


def client_ip(request, trusted_proxy_count=0):
    """The address to judge the request by.

    X-Forwarded-For is only consulted when the deployment declares how
    many proxies sit in front of the app. Trusting it unconditionally
    would let any student claim to be on the classroom network by setting
    a header.
    """
    if trusted_proxy_count > 0:
        forwarded = request.headers.get("X-Forwarded-For", "")
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) >= trusted_proxy_count:
            return parts[-trusted_proxy_count]
    return request.remote_addr or ""


def ip_matches(ip_str, networks):
    """Whether an address falls in any of the allowed IPs or CIDRs."""
    if not ip_str or not networks:
        return False

    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    for entry in networks:
        entry = entry.strip()
        if not entry:
            continue
        try:
            if "/" in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            else:
                if addr == ipaddress.ip_address(entry):
                    return True
        except ValueError:
            # A malformed entry must never widen access.
            continue
    return False


def check(ip_str, location, enforce=True):
    """Verify a request came from the classroom.

    Returns an error code or None.

    A location with no networks configured fails closed when the check is
    enforced. Treating "not configured" as "allow" would silently disable
    the layer on exactly the locations an admin forgot to set up.
    """
    if not enforce:
        return None

    networks = location.network_list()
    if not networks:
        return "NETWORK_NOT_CONFIGURED"

    if ip_matches(ip_str, networks):
        return None
    return "WRONG_NETWORK"
