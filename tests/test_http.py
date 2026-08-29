from unittest.mock import Mock, patch

import pytest
import requests

from checkin_tools.http import SafeHttpClient, UnsafeRedirectError


def response(status=200, location=None):
    item = Mock(spec=requests.Response)
    item.status_code = status
    item.headers = {} if location is None else {"Location": location}
    item.is_redirect = status in (301, 302, 303, 307, 308)
    item.is_permanent_redirect = status in (301, 308)
    item.raise_for_status.return_value = None
    return item


def test_request_uses_timeout_tls_url_and_no_auto_redirect():
    session = Mock(spec=requests.Session)
    session.request.return_value = response()
    client = SafeHttpClient("https://example.com", timeout=7, retries=0)
    assert client.get(session, "/page").status_code == 200
    session.request.assert_called_once_with(
        "GET", "https://example.com/page", timeout=7, allow_redirects=False
    )


def test_allows_same_host_redirect():
    session = Mock(spec=requests.Session)
    session.request.side_effect = [response(302, "/next"), response()]
    client = SafeHttpClient("https://example.com", retries=0)
    client.get(session, "/start")
    assert session.request.call_count == 2


@pytest.mark.parametrize("location", ["https://evil.example/page", "http://example.com/page"])
def test_rejects_cross_host_or_insecure_redirect(location):
    session = Mock(spec=requests.Session)
    session.request.return_value = response(302, location)
    with pytest.raises(UnsafeRedirectError):
        SafeHttpClient("https://example.com", retries=0).get(session, "/start")


def test_retries_connection_errors_and_5xx():
    session = Mock(spec=requests.Session)
    session.request.side_effect = [requests.Timeout("late"), response(503), response()]
    with patch("checkin_tools.http.time.sleep"):
        result = SafeHttpClient("https://example.com", retries=2).get(session, "/")
    assert result.status_code == 200
    assert session.request.call_count == 3


def test_does_not_retry_authentication_error():
    session = Mock(spec=requests.Session)
    denied = response(401)
    denied.raise_for_status.side_effect = requests.HTTPError("denied")
    session.request.return_value = denied
    with pytest.raises(requests.HTTPError):
        SafeHttpClient("https://example.com", retries=2).get(session, "/")
    assert session.request.call_count == 1

