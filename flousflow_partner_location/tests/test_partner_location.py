from unittest import mock

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestPartnerLocationParser(TransactionCase):

    def test_parse_q(self):
        url = 'https://www.google.com/maps?q=30.0444,31.2357'
        lat, lng = self.env['res.partner']._parse_location_url(url)
        self.assertAlmostEqual(lat, 30.0444, places=5)
        self.assertAlmostEqual(lng, 31.2357, places=5)

    def test_parse_query(self):
        url = 'https://www.google.com/maps/search/?api=1&query=30.0444,31.2357'
        lat, lng = self.env['res.partner']._parse_location_url(url)
        self.assertAlmostEqual(lat, 30.0444, places=5)
        self.assertAlmostEqual(lng, 31.2357, places=5)

    def test_parse_ll(self):
        url = 'https://maps.google.com/?ll=29.95,31.25'
        lat, lng = self.env['res.partner']._parse_location_url(url)
        self.assertAlmostEqual(lat, 29.95, places=5)
        self.assertAlmostEqual(lng, 31.25, places=5)

    def test_parse_at_path(self):
        url = 'https://www.google.com/maps/place/Cairo/@30.0444,31.2357,17z'
        lat, lng = self.env['res.partner']._parse_location_url(url)
        self.assertAlmostEqual(lat, 30.0444, places=5)
        self.assertAlmostEqual(lng, 31.2357, places=5)

    def test_parse_plus_separator(self):
        url = 'https://www.google.com/maps?q=30.0444+31.2357'
        lat, lng = self.env['res.partner']._parse_location_url(url)
        self.assertAlmostEqual(lat, 30.0444, places=5)
        self.assertAlmostEqual(lng, 31.2357, places=5)

    def test_parse_loc_prefix(self):
        url = 'https://maps.google.com/maps?q=loc:30.0444,31.2357'
        lat, lng = self.env['res.partner']._parse_location_url(url)
        self.assertAlmostEqual(lat, 30.0444, places=5)
        self.assertAlmostEqual(lng, 31.2357, places=5)

    def test_parse_negative(self):
        url = 'https://www.google.com/maps?q=-33.8688,151.2093'
        lat, lng = self.env['res.partner']._parse_location_url(url)
        self.assertAlmostEqual(lat, -33.8688, places=5)
        self.assertAlmostEqual(lng, 151.2093, places=5)

    def test_invalid_no_coords(self):
        url = 'https://www.google.com/maps/place/Cairo'
        with self.assertRaises(UserError):
            self.env['res.partner']._parse_location_url(url)

    def test_validate_lat_out_of_range(self):
        with self.assertRaises(UserError):
            self.env['res.partner']._validate_coordinates(95.0, 31.0)

    def test_validate_lng_out_of_range(self):
        with self.assertRaises(UserError):
            self.env['res.partner']._validate_coordinates(30.0, 190.0)

    def test_validate_zero_zero_rejected(self):
        with self.assertRaises(UserError):
            self.env['res.partner']._validate_coordinates(0.0, 0.0)

    def test_validate_non_numeric(self):
        with self.assertRaises(UserError):
            self.env['res.partner']._validate_coordinates('abc', 31.0)


class TestPartnerLocationSafety(TransactionCase):

    def test_safe_hosts(self):
        partner = self.env['res.partner']
        for host in ('google.com', 'www.google.com', 'maps.google.com',
                     'maps.app.goo.gl', 'goo.gl', 'sub.google.com'):
            self.assertTrue(partner._is_safe_host(host), host)

    def test_unsafe_hosts(self):
        partner = self.env['res.partner']
        for host in ('localhost', '127.0.0.1', '10.0.0.1', 'evil.com',
                     'google.com.evil.com', 'googles.com', 'google.co.uk'):
            self.assertFalse(partner._is_safe_host(host), host)

    def test_file_scheme_rejected(self):
        with self.assertRaises(UserError):
            self.env['res.partner'].extract_coordinates('file:///etc/passwd')

    def test_unsupported_domain_rejected(self):
        with self.assertRaises(UserError):
            self.env['res.partner'].extract_coordinates('https://evil.com/maps?q=30,31')

    def test_short_url_resolution(self):
        partner = self.env['res.partner']
        url = 'https://maps.app.goo.gl/abc123'

        class FakeResponse:
            def geturl(self):
                return 'https://www.google.com/maps/place/X/@30.0444,31.2357,17z'

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        fake_opener = mock.Mock()
        fake_opener.open.return_value = FakeResponse()
        with mock.patch('urllib.request.build_opener', return_value=fake_opener):
            result = partner.extract_coordinates(url)
        self.assertAlmostEqual(result['latitude'], 30.0444, places=5)
        self.assertAlmostEqual(result['longitude'], 31.2357, places=5)


class TestPartnerLocationWrite(TransactionCase):

    def test_write_updates_tracking(self):
        partner = self.env['res.partner'].create({'name': 'Test Location Co'})
        partner.write({'partner_latitude': 30.0, 'partner_longitude': 31.0})
        self.assertTrue(partner.location_updated_at)
        self.assertEqual(partner.location_updated_by, self.env.user)

    def test_extract_writes_coordinates(self):
        partner = self.env['res.partner'].create({
            'name': 'Test Extract',
            'location_url': 'https://www.google.com/maps?q=30.0444,31.2357',
        })
        partner.action_extract_location()
        self.assertAlmostEqual(partner.partner_latitude, 30.0444, places=5)
        self.assertAlmostEqual(partner.partner_longitude, 31.2357, places=5)
        self.assertEqual(partner.location_source, 'google_maps_link')

    def test_clear_location(self):
        partner = self.env['res.partner'].create({
            'name': 'Test Clear',
            'partner_latitude': 30.0,
            'partner_longitude': 31.0,
        })
        partner.action_clear_location()
        self.assertFalse(partner.partner_latitude)
        self.assertFalse(partner.partner_longitude)

    def test_get_address_from_location_mapping(self):
        partner = self.env['res.partner']
        fake_address = {
            'house_number': '12',
            'road': 'Main Street',
            'suburb': 'Nasr City',
            'city': 'Cairo',
            'postcode': '11762',
            'state': 'Cairo Governorate',
            'country_code': 'eg',
        }
        with mock.patch.object(type(partner), '_reverse_geocode', return_value=fake_address):
            result = partner.get_address_from_location(30.0, 31.0)
        self.assertEqual(result['street'], '12 Main Street')
        self.assertEqual(result['street2'], 'Nasr City')
        self.assertEqual(result['city'], 'Cairo')
        self.assertEqual(result['zip'], '11762')
        self.assertTrue(result['country_id'])

    def test_reverse_geocode_invalid_coords(self):
        with self.assertRaises(UserError):
            self.env['res.partner']._reverse_geocode(95.0, 31.0)

    def test_build_maps_urls(self):
        partner = self.env['res.partner']
        search_url = partner._build_maps_url(30.0444, 31.2357)
        self.assertIn('query=30.0444,31.2357', search_url)
        dir_url = partner._build_maps_url(30.0444, 31.2357, directions=True)
        self.assertIn('destination=30.0444,31.2357', dir_url)

    def test_location_can_edit_group(self):
        partner = self.env['res.partner'].create({'name': 'Test Perm'})
        # Tests run as the technical superuser -> can edit.
        self.assertTrue(partner.location_can_edit)
        # The regular admin user has base.group_system -> can edit.
        admin = self.env.ref('base.user_admin')
        self.assertTrue(partner.with_user(admin).location_can_edit)
        # The manager group exists and implies internal-user membership.
        manager_group = self.env.ref('flousflow_partner_location.group_location_manager')
        self.assertTrue(manager_group)
        self.assertIn(
            self.env.ref('base.group_user').id,
            manager_group.all_implied_ids.ids,
        )
