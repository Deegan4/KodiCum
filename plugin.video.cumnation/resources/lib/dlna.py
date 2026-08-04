# -*- coding: utf-8 -*-
"""Discovery of DLNA/UPnP MediaRenderer devices on the local network.

Smart TVs, AV receivers and streaming sticks advertise themselves as UPnP
MediaRenderers. Finding one is a two-step exchange:

1. **SSDP.** A multicast ``M-SEARCH`` datagram goes to 239.255.255.250:1900;
   every device matching the search target answers with a unicast,
   HTTP-shaped response whose ``LOCATION`` header points at its description.
2. **Device description.** That URL serves an XML document with the friendly
   name, manufacturer/model and the device's service list. A device is only a
   usable renderer if it exposes an ``AVTransport`` service, so that is what
   we filter on -- it keeps printers, routers and NAS servers out of the list.

Only :func:`ssdp_search` and :func:`fetch_description` touch the network; the
parsing and assembly are pure functions so they can be unit tested off-device.
Description fetching uses ``urllib`` rather than ``requests``: these are tiny
LAN documents and it keeps discovery free of the add-on's HTTP dependency.

Caveat worth knowing when a device is "missing": the search goes out over the
host's default multicast interface. On a multi-homed machine (an active VPN,
several NICs, a Docker bridge) devices on the other subnets never see the
query. Devices asleep or with "network standby" disabled stay silent too.
"""
import socket
import time

try:
    from urllib.parse import urljoin, urlparse
    from urllib.request import Request, urlopen
    from urllib.error import URLError
except ImportError:  # pragma: no cover - Python 2 fallback
    from urlparse import urljoin, urlparse
    from urllib2 import Request, urlopen, URLError

from xml.etree import ElementTree

from . import kodiutils
from . import storage
from .models import Renderer

SSDP_ADDR = '239.255.255.250'
SSDP_PORT = 1900
SSDP_BUFFER = 4096
MULTICAST_TTL = 2

#: Renderers answer the device-level target; a few only answer the
#: service-level one, so we ask for both and de-duplicate afterwards.
SEARCH_TARGETS = (
    'urn:schemas-upnp-org:device:MediaRenderer:1',
    'urn:schemas-upnp-org:service:AVTransport:1',
)

AVTRANSPORT = 'urn:schemas-upnp-org:service:AVTransport'
STORE = 'dlna_devices.json'

DESCRIPTION_TIMEOUT = 5


# -- settings -------------------------------------------------------------
def enabled():
    return kodiutils.get_setting_bool('dlna_enabled', True)


def timeout():
    """Seconds to listen for SSDP answers."""
    return max(1, kodiutils.get_setting_int('dlna_timeout', 3))


def cache_ttl():
    """Seconds a scan result stays fresh. 0 rescans every time."""
    return max(0, kodiutils.get_setting_int('dlna_cache_ttl', 5)) * 60


# -- SSDP -----------------------------------------------------------------
def _msearch(target, mx):
    """Build an M-SEARCH datagram for one search target."""
    return '\r\n'.join([
        'M-SEARCH * HTTP/1.1',
        'HOST: {0}:{1}'.format(SSDP_ADDR, SSDP_PORT),
        'MAN: "ssdp:discover"',
        'MX: {0}'.format(mx),
        'ST: {0}'.format(target),
        '',
        '',
    ]).encode('utf-8')


def parse_ssdp_response(raw):
    """Parse an SSDP response into a dict of lower-cased headers.

    The status line is discarded and duplicate headers keep the first value,
    matching how the UPnP spec expects a client to read them.
    """
    headers = {}
    for line in raw.splitlines()[1:]:
        if not line.strip():
            continue
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        key = key.strip().lower()
        if key and key not in headers:
            headers[key] = value.strip()
    return headers


def ssdp_search(wait=None, targets=SEARCH_TARGETS, repeats=2):
    """Multicast an M-SEARCH and collect the answers.

    Returns a list of header dicts, each with a ``location`` key and an
    ``address`` key holding the responding device's IP. UDP is lossy, so the
    query is sent ``repeats`` times; duplicate answers are expected and are
    filtered later by LOCATION and UDN.
    """
    wait = timeout() if wait is None else wait
    responses = []
    seen_locations = set()

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except OSError as exc:                      # pragma: no cover - no sockets
        kodiutils.log_error('SSDP socket unavailable: {0}'.format(exc))
        return responses

    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL,
                        MULTICAST_TTL)
        sock.bind(('', 0))

        mx = max(1, int(wait))
        for _ in range(max(1, repeats)):
            for target in targets:
                try:
                    sock.sendto(_msearch(target, mx), (SSDP_ADDR, SSDP_PORT))
                except OSError as exc:
                    kodiutils.log_error('SSDP send failed: {0}'.format(exc))

        deadline = time.time() + wait
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            sock.settimeout(remaining)
            try:
                data, addr = sock.recvfrom(SSDP_BUFFER)
            except socket.timeout:
                break
            except OSError as exc:
                kodiutils.log_error('SSDP receive failed: {0}'.format(exc))
                break
            headers = parse_ssdp_response(data.decode('utf-8', 'replace'))
            location = headers.get('location')
            if not location or location in seen_locations:
                continue
            seen_locations.add(location)
            headers['address'] = addr[0]
            responses.append(headers)
    finally:
        sock.close()

    kodiutils.log('SSDP: {0} candidate device(s)'.format(len(responses)))
    return responses


# -- device description ---------------------------------------------------
def fetch_description(location, request_timeout=DESCRIPTION_TIMEOUT):
    """GET a device description document. Returns the XML text, or None."""
    try:
        request = Request(location, headers={
            'User-Agent': 'Kodi/{0}'.format(kodiutils.ADDON_ID),
        })
        handle = urlopen(request, timeout=request_timeout)
        try:
            return handle.read().decode('utf-8', 'replace')
        finally:
            handle.close()
    except (URLError, OSError, ValueError) as exc:
        kodiutils.log('Description fetch failed for {0}: {1}'.format(
            location, exc))
        return None


def local_name(tag):
    """Strip the XML namespace from a tag name."""
    return tag.rsplit('}', 1)[-1]


def _child(element, name):
    for child in element:
        if local_name(child.tag) == name:
            return child
    return None


def _text(element, name, default=None):
    child = _child(element, name)
    if child is None or child.text is None:
        return default
    return child.text.strip() or default


def _avtransport_service(device, base):
    """Return ``(control_url, service_type)`` for a device's AVTransport.

    The exact service type is kept, not just assumed to be version 1: it goes
    into the ``SOAPACTION`` header when controlling the device, and a renderer
    advertising ``AVTransport:2`` will reject actions addressed to ``:1``.
    """
    services = _child(device, 'serviceList')
    if services is None:
        return None, None
    for service in services:
        if local_name(service.tag) != 'service':
            continue
        service_type = _text(service, 'serviceType') or ''
        if not service_type.startswith(AVTRANSPORT):
            continue
        control = _text(service, 'controlURL')
        if control:
            return urljoin(base, control), service_type
    return None, None


def _best_icon(device, base):
    """Return the largest declared icon URL, or None."""
    icons = _child(device, 'iconList')
    if icons is None:
        return None
    best, best_width = None, -1
    for icon in icons:
        if local_name(icon.tag) != 'icon':
            continue
        url = _text(icon, 'url')
        if not url:
            continue
        try:
            width = int(_text(icon, 'width', '0'))
        except (TypeError, ValueError):
            width = 0
        if width > best_width:
            best, best_width = urljoin(base, url), width
    return best


def parse_device_description(xml_text, location, address=None):
    """Build a :class:`Renderer` from a device description document.

    Returns None when the document is unparseable or describes something that
    is not a media renderer. A renderer is identified by exposing an
    ``AVTransport`` service -- that is the service Kodi (or anything else)
    would push a stream through, so a device without it cannot be played to.
    Embedded devices are searched too: some TVs nest the MediaRenderer inside
    a vendor root device.
    """
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        kodiutils.log('Bad device description from {0}: {1}'.format(
            location, exc))
        return None

    base = _text(root, 'URLBase') or location

    for device in root.iter():
        if local_name(device.tag) != 'device':
            continue
        control_url, service_type = _avtransport_service(device, base)
        if not control_url:
            continue
        host = address or urlparse(location).hostname
        return Renderer(
            udn=_text(device, 'UDN') or location,
            name=_text(device, 'friendlyName') or host or '',
            location=location,
            address=host,
            manufacturer=_text(device, 'manufacturer'),
            model=_text(device, 'modelName'),
            model_number=_text(device, 'modelNumber'),
            device_type=_text(device, 'deviceType'),
            control_url=control_url,
            service_type=service_type,
            icon=_best_icon(device, base),
        )
    return None


# -- assembly -------------------------------------------------------------
def renderers_from_responses(responses, fetch=fetch_description):
    """Turn SSDP responses into a de-duplicated, sorted list of Renderers.

    ``fetch`` is injectable so this can be exercised without a network.
    Devices that answer SSDP but whose description is unreachable or is not a
    renderer are dropped -- a name with nothing playable behind it would be a
    dead entry in the UI.
    """
    found = {}
    for headers in responses:
        location = headers.get('location')
        if not location:
            continue
        xml_text = fetch(location)
        if not xml_text:
            continue
        renderer = parse_device_description(xml_text, location,
                                            headers.get('address'))
        if renderer is None:
            continue
        found.setdefault(renderer.udn, renderer)
    return sorted(found.values(), key=lambda r: r.label.lower())


def discover(wait=None):
    """Run a full scan and remember the result. Returns a list of Renderers."""
    renderers = renderers_from_responses(ssdp_search(wait))
    kodiutils.log('DLNA: {0} renderer(s) found'.format(len(renderers)))
    _remember(renderers)
    return renderers


# -- scan cache -----------------------------------------------------------
def _remember(renderers):
    if cache_ttl() <= 0:
        return
    storage.save(STORE, {
        'ts': time.time(),
        'devices': [r.to_dict() for r in renderers],
    })


def cached(now=None):
    """Return the last scan if it is still fresh, else None.

    None means "no usable result" -- the caller should scan, and can warn the
    user first since a scan blocks for a few seconds.
    """
    ttl = cache_ttl()
    if ttl <= 0:
        return None
    entry = storage.load(STORE, default={})
    if not entry:
        return None
    now = time.time() if now is None else now
    if now - entry.get('ts', 0) > ttl:
        return None
    return [Renderer.from_dict(d) for d in entry.get('devices', [])]


def forget():
    """Drop the remembered scan so the next lookup rescans."""
    storage.save(STORE, {})
