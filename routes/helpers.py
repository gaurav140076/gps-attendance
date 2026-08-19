"""Request-level helpers shared by the blueprints."""

from flask import current_app, request

from services import device_service, network_service


def source_ip():
    """The address the request actually came from."""
    return network_service.client_ip(
        request, current_app.config["TRUSTED_PROXY_COUNT"]
    )


def device_hash_from_cookie():
    """The device identity presented by this browser, if any.

    Read from the signed cookie -- never from the request body, which the
    client controls.
    """
    return device_service.read_cookie(
        request,
        current_app.config["SECRET_KEY"],
        current_app.config["DEVICE_COOKIE_NAME"],
    )


def attach_device_cookie(response, device_hash):
    """Issue or refresh the device cookie on a response."""
    cfg = current_app.config
    response.set_cookie(
        cfg["DEVICE_COOKIE_NAME"],
        device_service.sign(cfg["SECRET_KEY"], device_hash),
        max_age=cfg["DEVICE_COOKIE_MAX_AGE"],
        httponly=True,
        samesite="Lax",
        secure=cfg["SESSION_COOKIE_SECURE"],
    )
    return response


def ensure_device_cookie(response):
    """Give this browser a device identity if it does not have one.

    Minting the value here rather than at registration means the identity
    is stable from first visit, so registration binds the device the
    student is actually holding.
    """
    if device_hash_from_cookie():
        return response, None
    fresh = device_service.new_device_hash()
    return attach_device_cookie(response, fresh), fresh


def wants_json():
    return request.path.startswith("/api/") or request.is_json


def payload():
    """Request body as a dict, whether it arrived as JSON or a form."""
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict()
