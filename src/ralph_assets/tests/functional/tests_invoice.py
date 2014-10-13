# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import urllib

from django.test import TestCase
from django.core.urlresolvers import reverse
from django.test.utils import override_settings
from mock import patch

from ralph.ui.tests.global_utils import login_as_su
from ralph_assets.models import Asset, Licence
from ralph_assets.tests.utils import ReportOdtSourceFactory
from ralph_assets.tests.utils.assets import (
    BOAssetFactory,
)
from ralph_assets.tests.utils.sam import LicenceFactory


ASSETS_REPORTS_FOR_TESTS = {
    'ENABLE': True,
    'INVOICE_REPORT': {'SLUG': 'invoice-report'},
    'TEMP_STORAGE_PATH': '/tmp/',
}
INKPY_FOR_TESTS = {
    'script_path': '/path/to/script.py',
    'tmp_dir': '/tmp/inkpy'
}


def mocked_generate_pdf(source_path, output_path, data, lang_code):
    """Mock generate_pdf method from inky"""


class TestInvoiceReport(TestCase):
    def setUp(self):
        self.client = login_as_su()

    def assert_message_contains(self, response, text):
        """
        Asserts that there is exactly one message containing the given text.
        """
        messages = response.context['messages']
        matches = [m for m in messages if text in m.message]
        if not matches:
            messages_str = ", ".join('"%s"' % m for m in messages)
            self.fail(
                'No message contained text "%s", messages were: %s' %
                (text, messages_str),
            )

    def _create_assets(self, custom_values={}):
        [BOAssetFactory(**custom_values) for _ in xrange(4)]

    def _create_licences(self, custom_values={}):
        [LicenceFactory(**custom_values) for _ in xrange(4)]

    def _create_report_odt_source(self):
        ReportOdtSourceFactory(**{'slug': 'invoice-report'})

    def _get_invoice_asset_base_url(self):
        return reverse('assets_invoice_report', args=('back_office',))

    def _get_invoice_licence_base_url(self):
        return reverse('sam_invoice_report')

    def _get_invoice_url_from_asset(self, assets):
        assets_ids = assets.values_list('id', flat=True)
        return '{}?{}'.format(
            self._get_invoice_asset_base_url(),
            urllib.urlencode([('select', aid) for aid in assets_ids]),
        )

    def _get_invoice_url_from_licence(self, assets):
        licence_ids = assets.values_list('id', flat=True)
        return '{}?{}'.format(
            self._get_invoice_licence_base_url(),
            urllib.urlencode([('select', lid) for lid in licence_ids]),
        )

    def test_asset_invoice_disable_in_settings(self):
        self._create_assets()
        url = self._get_invoice_url_from_asset(Asset.objects.all()[0:2])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assert_message_contains(response, 'Assets reports is disabled')

    @override_settings(ASSETS_REPORTS=ASSETS_REPORTS_FOR_TESTS)
    def test_asset_invoice_enable_in_settings(self):
        self._create_assets({'invoice_no': None})
        url = self._get_invoice_url_from_asset(Asset.objects.all()[0:2])
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        messages = [
            'Odt template does not exist!',
            'Selected items has different:',
            "Invoice number, invoice date or provider can't be empty",
        ]
        for message in messages:
            self.assert_message_contains(response, message)

    @override_settings(ASSETS_REPORTS=ASSETS_REPORTS_FOR_TESTS)
    def test_asset_invoice_from_query(self):
        self._create_assets({'invoice_no': 12})
        url = '{}?from_query=1&invoice_no=12'.format(
            self._get_invoice_asset_base_url(),
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)

    @override_settings(ASSETS_REPORTS=ASSETS_REPORTS_FOR_TESTS)
    @override_settings(INKPY=INKPY_FOR_TESTS)
    @patch('ralph_assets.views.invoice_report.generate_pdf')
    def test_asset_invoice_with_report_odt_source_fail(self, generate_pdf):
        generate_pdf.side_effect = mocked_generate_pdf

        self._create_assets({
            'invoice_no': 12,
            'invoice_date': datetime.date.today(),
            'provider': 'test',
        })
        self._create_report_odt_source()
        url = self._get_invoice_url_from_asset(Asset.objects.all()[0:2])
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assert_message_contains(
            response,
            'The error occurred, was not possible to read generated file.',
        )

    @override_settings(ASSETS_REPORTS=ASSETS_REPORTS_FOR_TESTS)
    def test_licence_invoice_from_query(self):
        self._create_licences({'invoice_no': 666})
        url = '{}?from_query=1&invoice_no=666'.format(
            self._get_invoice_licence_base_url(),
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)

    @override_settings(ASSETS_REPORTS=ASSETS_REPORTS_FOR_TESTS)
    @override_settings(INKPY=INKPY_FOR_TESTS)
    @patch('ralph_assets.views.invoice_report.generate_pdf')
    def test_licence_invoice_with_report_odt_source_fail(self, generate_pdf):
        generate_pdf.side_effect = mocked_generate_pdf

        self._create_licences({
            'invoice_no': 666,
            'invoice_date': datetime.date.today(),
            'provider': 'test',
        })
        self._create_report_odt_source()
        url = self._get_invoice_url_from_licence(Licence.objects.all()[0:2])
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assert_message_contains(
            response,
            'The error occurred, was not possible to read generated file.',
        )
