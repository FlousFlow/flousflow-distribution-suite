import ipaddress
import json
import logging
import re
import socket
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlencode, urlparse, unquote

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Only these hosts may be contacted or followed during short-link resolution.
# This is the SSRF allowlist: we never fetch arbitrary user-supplied URLs.
_ALLOWED_HOSTS = frozenset({
    'google.com',
    'www.google.com',
    'maps.google.com',
    'maps.app.goo.gl',
    'goo.gl',
})

# Google Maps short-link hosts that require server-side redirect resolution.
_SHORT_LINK_HOSTS = frozenset({'maps.app.goo.gl', 'goo.gl'})

_MAX_REDIRECTS = 5
_REQUEST_TIMEOUT = 5

_COORD_RE = re.compile(
    r'^([-+]?\d{1,3}(?:\.\d+)?)\s*[, ]\s*([-+]?\d{1,3}(?:\.\d+)?)$'
)
_PATH_COORD_RE = re.compile(
    r'@([-+]?\d{1,3}(?:\.\d+)?)[,+]?([-+]?\d{1,3}(?:\.\d+)?)'
)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    location_url = fields.Char(
        string='Location Link',
        help='Google Maps / WhatsApp shared location link.',
    )
    location_accuracy = fields.Float(
        string='Accuracy (m)',
        digits=(10, 2),
        help='Estimated accuracy of the captured position, in meters.',
    )
    location_source = fields.Selection(
        selection=[
            ('gps', 'Current Device'),
            ('google_maps_link', 'Shared Maps Link'),
            ('manual', 'Manual'),
        ],
        string='Location Source',
    )
    location_updated_at = fields.Datetime(
        string='Last Location Update',
        readonly=True,
    )
    location_updated_by = fields.Many2one(
        'res.users',
        string='Updated By',
        readonly=True,
    )
    location_can_edit = fields.Boolean(
        string='Can Edit Location',
        compute='_compute_location_can_edit',
    )
    location_panel = fields.Boolean(
        string='Location Controls',
        compute='_compute_location_panel',
    )

    # ------------------------------------------------------------------
    # Computed helpers
    # ------------------------------------------------------------------
    @api.depends_context('uid')
    def _compute_location_can_edit(self):
        can_edit = (
            self.env.is_admin()
            or self.env.user.has_group('flousflow_partner_location.group_location_manager')
        )
        for partner in self:
            partner.location_can_edit = can_edit

    @api.depends('partner_latitude', 'partner_longitude')
    def _compute_location_panel(self):
        for partner in self:
            partner.location_panel = True

    # ------------------------------------------------------------------
    # CRUD — keep location audit fields up to date
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'partner_latitude' in vals or 'partner_longitude' in vals:
                vals['location_updated_at'] = fields.Datetime.now()
                vals['location_updated_by'] = self.env.user.id
        return super().create(vals_list)

    def write(self, vals):
        if 'partner_latitude' in vals or 'partner_longitude' in vals:
            vals['location_updated_at'] = fields.Datetime.now()
            vals['location_updated_by'] = self.env.user.id
        return super().write(vals)

    # ------------------------------------------------------------------
    # Coordinate parsing / validation
    # ------------------------------------------------------------------
    @api.model
    def _validate_coordinates(self, latitude, longitude):
        try:
            lat = float(latitude)
            lng = float(longitude)
        except (TypeError, ValueError):
            raise UserError(_('Invalid latitude or longitude.'))
        if not (-90.0 <= lat <= 90.0):
            raise UserError(_('Latitude must be between -90 and 90.'))
        if not (-180.0 <= lng <= 180.0):
            raise UserError(_('Longitude must be between -180 and 180.'))
        if lat == 0.0 and lng == 0.0:
            raise UserError(_('No valid coordinates were found in this link.'))
        return lat, lng

    @api.model
    def _parse_location_url(self, url):
        if not url:
            raise UserError(_('Please enter a Google Maps location link.'))
        url = unquote(url.strip())

        parsed = urlparse(url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        candidates = []

        for key in ('q', 'query', 'll'):
            for value in query.get(key, []):
                value = value.strip()
                if value.lower().startswith('loc:'):
                    value = value[4:].strip()
                if value:
                    candidates.append(value)

        path_match = _PATH_COORD_RE.search(parsed.path)
        if path_match:
            candidates.append('%s,%s' % (path_match.group(1), path_match.group(2)))

        for candidate in candidates:
            match = _COORD_RE.match(candidate.replace('+', ',').strip())
            if match:
                return self._validate_coordinates(match.group(1), match.group(2))

        raise UserError(_(
            'No valid coordinates were found in this link. '
            'Please open the link and copy the full Google Maps URL.'
        ))

    # ------------------------------------------------------------------
    # SSRF-safe short link resolution
    # ------------------------------------------------------------------
    @api.model
    def _is_safe_host(self, host):
        host = (host or '').lower().strip()
        if not host:
            return False
        # Reject literal IP addresses (v4/v6).
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            pass
        if host in _ALLOWED_HOSTS:
            return True
        if host.endswith('.google.com'):
            return True
        return False

    @api.model
    def _resolve_short_url(self, url):
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            raise UserError(
                _('This location link is not from a supported Google Maps domain.'))
        if not self._is_safe_host(parsed.hostname):
            raise UserError(
                _('This location link is not from a supported Google Maps domain.'))

        class _RedirectHandler(urllib.request.HTTPRedirectHandler):
            def __init__(self, model):
                super().__init__()
                self.model = model
                self.count = 0

            def redirect_request(self, req, fp, code, msg, headers, newurl):
                self.count += 1
                if self.count > _MAX_REDIRECTS:
                    raise UserError(_('This location link has too many redirects.'))
                target = urlparse(newurl)
                target_host = (target.hostname or '').lower()
                if (target.scheme not in ('http', 'https')
                        or not self.model._is_safe_host(target_host)):
                    raise UserError(
                        _('This location link is not from a supported Google Maps domain.'))
                return super().redirect_request(req, fp, code, msg, headers, newurl)

        opener = urllib.request.build_opener(_RedirectHandler(self))
        request = urllib.request.Request(url, headers={'User-Agent': 'Odoo/19'})
        try:
            with opener.open(request, timeout=_REQUEST_TIMEOUT) as response:
                final_url = response.geturl()
        except (urllib.error.URLError, socket.timeout, TimeoutError,
                ConnectionError, OSError) as exc:
            _logger.info('Could not resolve short location URL: %s', exc)
            raise UserError(_(
                'Unable to extract coordinates from this link. '
                'Please open the link and copy the full Google Maps URL.'))
        return final_url

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------
    @api.model
    def extract_coordinates(self, url):
        """Return {'latitude', 'longitude'} parsed from a Google Maps link.

        Public (no leading underscore) so it can be called via RPC from the
        frontend widget.
        """
        if not url:
            raise UserError(_('Please enter a Google Maps location link.'))
        url = url.strip()
        if '://' not in url:
            url = 'https://' + url

        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            raise UserError(
                _('This location link is not from a supported Google Maps domain.'))
        host = (parsed.hostname or '').lower()
        if not self._is_safe_host(host):
            raise UserError(
                _('This location link is not from a supported Google Maps domain.'))

        target_url = url
        if host in _SHORT_LINK_HOSTS:
            target_url = self._resolve_short_url(url)

        lat, lng = self._parse_location_url(target_url)
        return {'latitude': lat, 'longitude': lng}

    @api.model
    def _build_maps_url(self, latitude, longitude, directions=False):
        lat, lng = self._validate_coordinates(latitude, longitude)
        if directions:
            return 'https://www.google.com/maps/dir/?api=1&destination=%s,%s' % (lat, lng)
        return 'https://www.google.com/maps/search/?api=1&query=%s,%s' % (lat, lng)

    def action_extract_location(self):
        self.ensure_one()
        url = self.location_url
        result = self.extract_coordinates(url)
        self.write({
            'partner_latitude': result['latitude'],
            'partner_longitude': result['longitude'],
            'location_url': url,
            'location_source': 'google_maps_link',
        })
        return result

    def action_clear_location(self):
        self.write({
            'partner_latitude': False,
            'partner_longitude': False,
            'location_accuracy': False,
            'location_url': False,
            'location_source': False,
        })

    # ------------------------------------------------------------------
    # Reverse geocoding (fill the partner address card from coordinates)
    # Opt-in only: runs when the user clicks "Fill Address from Location".
    # ------------------------------------------------------------------
    @api.model
    def _reverse_geocode(self, latitude, longitude):
        """Query OpenStreetMap Nominatim for the address of the coordinates."""
        lat, lng = self._validate_coordinates(latitude, longitude)
        query = urlencode({
            'format': 'jsonv2',
            'lat': lat,
            'lon': lng,
            'zoom': 18,
            'addressdetails': 1,
        })
        url = 'https://nominatim.openstreetmap.org/reverse?%s' % query
        request = urllib.request.Request(url, headers={
            'User-Agent': 'flousflow_partner_location/19.0 (https://flousflow.com)',
            'Accept': 'application/json',
        })
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status != 200:
                    raise UserError(_('Unable to determine the address from this location.'))
                data = json.loads(response.read().decode('utf-8'))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            _logger.info('Reverse geocoding failed: %s', exc)
            raise UserError(_('Unable to determine the address from this location.'))
        return data.get('address') or {}

    @api.model
    def get_address_from_location(self, latitude, longitude):
        """Map coordinates to partner address fields (reverse geocoding).

        Public so the frontend can call it via RPC and fill the form state.
        Returns street / street2 / city / zip / country_id / state_id.
        """
        address = self._reverse_geocode(latitude, longitude)
        house_number = (address.get('house_number') or '').strip()
        road = (address.get('road') or '').strip()
        street = ' '.join(part for part in (house_number, road) if part)
        street2 = (address.get('suburb') or address.get('neighbourhood') or '').strip()
        city = (address.get('city')
                or address.get('town')
                or address.get('village')
                or address.get('municipality') or '').strip()

        country = self.env['res.country'].search(
            [('code', '=ilike', (address.get('country_code') or '').strip())], limit=1)
        state = self.env['res.country.state']
        state_name = (address.get('state') or '').strip()
        if country and state_name:
            state = self.env['res.country.state'].search([
                ('country_id', '=', country.id),
                ('name', '=ilike', state_name),
            ], limit=1)

        return {
            'street': street,
            'street2': street2,
            'city': city,
            'zip': (address.get('postcode') or '').strip(),
            'country_id': [country.id, country.name] if country else False,
            'state_id': [state.id, state.name] if state else False,
        }
