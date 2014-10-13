# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import urllib

from django.test import TestCase
from django.core.urlresolvers import reverse


from ralph.cmdb.tests.utils import (
    DeviceEnvironmentFactory,
    ServiceCatalogFactory,
)
from ralph_assets.tests.util import create_model
from ralph_assets.tests.utils import sam
from ralph_assets.tests.utils.assets import (
    AssetFactory,
    BOAssetFactory,
    DCAssetFactory,
    AssetManufacturerFactory,
)
from ralph_assets.models_assets import (
    Asset,
    AssetType,
    AssetStatus,
)
from ralph.ui.tests.global_utils import login_as_su
from ralph_assets.tests.utils import supports


class TestSearchForm(TestCase):
    """Scenario:
    1. Tests all fields
    2. Insert incorrect data
    """
    def setUp(self):
        self.client = login_as_su()
        self.first_asset = AssetFactory(
            invoice_no='Invoice No1',
            order_no='Order No2',
            invoice_date=datetime.date(2001, 1, 1),
            support_type='Support d2d',
            provider='Provider1',
            sn='1234-1234-1234-1234',
            barcode='bc1',
        )

        self.second_asset = AssetFactory(
            invoice_no='Invoice No2',
            order_no='Order No1',
            invoice_date=datetime.date(2001, 1, 1),
            support_type='Support d2d',
            provider='Provider2',
            sn='1235-1235-1235-1235',
            barcode='bc2',
        )

        asset_model = create_model(name='Model2')
        asset_status = AssetStatus.used.id
        self.third_asset = AssetFactory(
            model=asset_model,
            invoice_no='Invoice No1',
            order_no='Order No1',
            invoice_date=datetime.date(2001, 1, 1),
            support_type='Support d2d',
            provider='Provider1',
            sn='1236-1236-1236-1236',
            barcode='bc3',
            status=asset_status,
        )

    def test_model_field(self):
        url = '/assets/dc/search?model=%s' % self.first_asset.model.name
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 2)

        # Test if search form find correct data
        self.assertItemsEqual(
            [asset.model.name for asset in rows_from_table],
            [self.first_asset.model.name, self.second_asset.model.name]
        )
        self.assertItemsEqual(
            [asset.sn for asset in rows_from_table],
            ['1234-1234-1234-1234', '1235-1235-1235-1235']
        )

        # What do Ralph when we don't insert model name? (return all asset)
        content = self.client.get('/assets/dc/search?model=')
        self.assertEqual(content.status_code, 200)
        empty_model_rows = content.context_data['bob_page'].object_list
        self.assertEqual(len(empty_model_rows), 3)

        # or we insert wrong model name (outside range)?
        content = self.client.get('/assets/dc/search?model=Ralph0')
        self.assertEqual(content.status_code, 200)
        outside_range_rows = content.context_data['bob_page'].object_list
        self.assertEqual(len(outside_range_rows), 0)

    def test_invoice_no_field(self):
        self.assertEqual(self.third_asset.invoice_no, 'Invoice No1')

        url = '/assets/dc/search?invoice_no=%s' % self.third_asset.invoice_no
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 2)

        # Test if search form find correct data
        self.assertItemsEqual(
            [asset.invoice_no for asset in rows_from_table],
            ['Invoice No1', 'Invoice No1']
        )
        self.assertItemsEqual(
            [asset.sn for asset in rows_from_table],
            ['1234-1234-1234-1234', '1236-1236-1236-1236']
        )

    def test_order_no_field(self):
        self.assertEqual(self.third_asset.order_no, 'Order No1')
        url = '/assets/dc/search?order_no=%s' % self.third_asset.order_no
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 2)

        # Test if search form find correct data
        self.assertItemsEqual(
            [asset.order_no for asset in rows_from_table],
            ['Order No1', 'Order No1']
        )
        self.assertItemsEqual(
            [asset.sn for asset in rows_from_table],
            ['1235-1235-1235-1235', '1236-1236-1236-1236']
        )

    def test_provider_field(self):
        self.assertEqual(self.second_asset.provider, 'Provider2')
        url = '/assets/dc/search?provider=%s' % self.second_asset.provider
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 1)

        # Test if search form find correct data
        self.assertEqual(rows_from_table[0].provider, 'Provider2')
        self.assertEqual(rows_from_table[0].sn, '1235-1235-1235-1235')

    def test_status_field(self):
        self.assertEqual(
            AssetStatus.name_from_id(self.third_asset.status), 'used'
        )
        url = '/assets/dc/search?status=%s' % AssetStatus.used.id
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 1)

        # Test if search form find correct data
        self.assertItemsEqual(
            [AssetStatus.name_from_id(
                asset.status,
            ) for asset in rows_from_table],
            ['used']
        )
        self.assertEqual(rows_from_table[0].sn, '1236-1236-1236-1236')

    def test_sn_field(self):
        self.assertEqual(self.first_asset.sn, '1234-1234-1234-1234')
        url = '/assets/dc/search?sn=%s' % self.first_asset.sn
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 1)

        # Test if search form find correct data
        self.assertEqual(rows_from_table[0].sn, '1234-1234-1234-1234')

    def test_type_filed(self):
        device = '/assets/dc/search?part_info=device'
        part = '/assets/dc/search?part_info=part'

        # Here we tests if in page see only devices.
        device_content = self.client.get(device)
        self.assertEqual(device_content.status_code, 200)
        dev_data = device_content.context_data['bob_page'].object_list

        for dev in dev_data:
            self.assertEqual(dev.part_info, None)

        # Here we tests if in page see only a parts..
        part_content = self.client.get(part)
        self.assertEqual(part_content.status_code, 200)
        part_data = part_content.context_data['bob_page'].object_list

        for part in part_data:
            self.assertNotEqual(part.part_info, None)


class TestSearchInvoiceDateFields(TestCase):
    def setUp(self):
        self.client = login_as_su()
        self.first_asset = AssetFactory(
            invoice_date=datetime.date(2001, 1, 1),
            sn='1234-1234-1234-1234',
        )

        self.second_asset = AssetFactory(
            invoice_date=datetime.date(2002, 1, 1),
            sn='1235-1235-1235-1235',
        )

        self.third_asset = AssetFactory(
            invoice_date=datetime.date(2003, 1, 1),
            sn='1236-1236-1236-1236',
        )

    def test_start_date_is_equal_end_date(self):
        url = '/assets/dc/search?invoice_date_from=%s&invoice_date_to=%s' % (
            '2001-01-01', '2001-01-01')
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 1)
        self.assertEqual(rows_from_table[0].sn, '1234-1234-1234-1234')

    def test_start_date_is_less_then_end_date(self):
        url = '/assets/dc/search?invoice_date_from=%s&invoice_date_to=%s' % (
            '2011-01-01', '2002-01-01')
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 0)

    def test_find_more_assets_lte_gte(self):
        url = '/assets/dc/search?invoice_date_from=%s&invoice_date_to=%s' % (
            '2001-01-01', '2002-01-01')
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 2)

        self.assertItemsEqual(
            [asset.sn for asset in rows_from_table],
            ['1234-1234-1234-1234', '1235-1235-1235-1235']
        )

    def test_start_date_is_empty(self):
        url = '/assets/dc/search?invoice_date_from=%s&invoice_date_to=%s' % (
            '', '2001-01-01')
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 1)
        self.assertEqual(rows_from_table[0].sn, '1234-1234-1234-1234')

    def test_end_date_is_empty(self):
        url = '/assets/dc/search?invoice_date_from=%s&invoice_date_to=%s' % (
            '1999-01-01', '')
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 3)


class TestSearchProviderDateFields(TestCase):
    def setUp(self):
        self.client = login_as_su()
        self.base_url = '/assets/dc/search'

        self.first_asset = AssetFactory(
            provider_order_date=datetime.date(2001, 1, 1),
            sn='1234-1234-1234-1234',
        )

        self.second_asset = AssetFactory(
            provider_order_date=datetime.date(2002, 1, 1),
            sn='1235-1235-1235-1235',
        )

        self.third_asset = AssetFactory(
            provider_order_date=datetime.date(2003, 1, 1),
            sn='1236-1236-1236-1236',
        )

    def test_start_date_is_equal_end_date(self):
        url = '?provider_order_date_from=%s&provider_order_date_to=%s' % (
            '2001-01-01', '2001-01-01')
        content = self.client.get(self.base_url + url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 1)
        self.assertEqual(rows_from_table[0].sn, '1234-1234-1234-1234')

    def test_start_date_is_less_then_end_date(self):
        url = '?provider_order_date_from=%s&provider_order_date_to=%s' % (
            '2011-01-01', '2002-01-01')
        content = self.client.get(self.base_url + url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 0)

    def test_find_more_assets_lte_gte(self):
        url = '?provider_order_date_from=%s&provider_order_date_to=%s' % (
            '2001-01-01', '2002-01-01')
        content = self.client.get(self.base_url + url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 2)

        self.assertItemsEqual(
            [asset.sn for asset in rows_from_table],
            ['1234-1234-1234-1234', '1235-1235-1235-1235']
        )

    def test_start_date_is_empty(self):
        url = '?provider_order_date_from=%s&provider_order_date_to=%s' % (
            '', '2001-01-01')
        content = self.client.get(self.base_url + url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 1)
        self.assertEqual(rows_from_table[0].sn, '1234-1234-1234-1234')

    def test_end_date_is_empty(self):
        url = '?provider_order_date_from=%s&provider_order_date_to=%s' % (
            '1999-01-01', '')
        content = self.client.get(self.base_url + url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 3)


class TestSearchDeliveryDateFields(TestCase):
    def setUp(self):
        self.client = login_as_su()

        self.first_asset = AssetFactory(
            delivery_date=datetime.date(2001, 1, 1),
            sn='1234-1234-1234-1234',
        )

        self.second_asset = AssetFactory(
            delivery_date=datetime.date(2002, 1, 1),
            sn='1235-1235-1235-1235',
        )

        self.third_asset = AssetFactory(
            delivery_date=datetime.date(2003, 1, 1),
            sn='1236-1236-1236-1236',
        )

    def test_start_date_is_equal_end_date(self):
        url = '/assets/dc/search?delivery_date_from=%s&delivery_date_to=%s' % (
            '2001-01-01', '2001-01-01')
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 1)
        self.assertEqual(rows_from_table[0].sn, '1234-1234-1234-1234')

    def test_start_date_is_less_then_end_date(self):
        url = '/assets/dc/search?delivery_date_from=%s&delivery_date_to=%s' % (
            '2011-01-01', '2002-01-01')
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 0)

    def test_find_more_assets_lte_gte(self):
        url = '/assets/dc/search?delivery_date_from=%s&delivery_date_to=%s' % (
            '2001-01-01', '2002-01-01')
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 2)

        self.assertItemsEqual(
            [asset.sn for asset in rows_from_table],
            ['1234-1234-1234-1234', '1235-1235-1235-1235']
        )

    def test_start_date_is_empty(self):
        url = '/assets/dc/search?delivery_date_from=%s&delivery_date_to=%s' % (
            '', '2001-01-01')
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 1)
        self.assertEqual(rows_from_table[0].sn, '1234-1234-1234-1234')

    def test_end_date_is_empty(self):
        url = '/assets/dc/search?delivery_date_from=%s&delivery_date_to=%s' % (
            '1999-01-01', '')
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 3)


class TestSearchRequestDateFields(TestCase):
    def setUp(self):
        self.client = login_as_su()

        self.first_asset = AssetFactory(
            request_date=datetime.date(2001, 1, 1),
            sn='1234-1234-1234-1234',
        )

        self.second_asset = AssetFactory(
            request_date=datetime.date(2002, 1, 1),
            sn='1235-1235-1235-1235',
        )

        self.third_asset = AssetFactory(
            request_date=datetime.date(2003, 1, 1),
            sn='1236-1236-1236-1236',
        )

    def test_start_date_is_equal_end_date(self):
        url = '/assets/dc/search?request_date_from=%s&request_date_to=%s' % (
            '2001-01-01', '2001-01-01')
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 1)
        self.assertEqual(rows_from_table[0].sn, '1234-1234-1234-1234')

    def test_start_date_is_less_then_end_date(self):
        url = '/assets/dc/search?request_date_from=%s&request_date_to=%s' % (
            '2011-01-01', '2002-01-01')
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 0)

    def test_find_more_assets_lte_gte(self):
        url = '/assets/dc/search?request_date_from=%s&request_date_to=%s' % (
            '2001-01-01', '2002-01-01')
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 2)

        self.assertItemsEqual(
            [asset.sn for asset in rows_from_table],
            ['1234-1234-1234-1234', '1235-1235-1235-1235']
        )

    def test_start_date_is_empty(self):
        url = '/assets/dc/search?request_date_from=%s&request_date_to=%s' % (
            '', '2001-01-01')
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 1)
        self.assertEqual(rows_from_table[0].sn, '1234-1234-1234-1234')

    def test_end_date_is_empty(self):
        url = '/assets/dc/search?request_date_from=%s&request_date_to=%s' % (
            '1999-01-01', '')
        content = self.client.get(url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 3)


class TestSearchProductionUseDateFields(TestCase):
    def setUp(self):
        self.client = login_as_su()
        self.base_url = '/assets/dc/search'

        self.first_asset = AssetFactory(
            production_use_date=datetime.date(2001, 1, 1),
            sn='1234-1234-1234-1234',
        )

        self.second_asset = AssetFactory(
            production_use_date=datetime.date(2002, 1, 1),
            sn='1235-1235-1235-1235',
        )

        self.third_asset = AssetFactory(
            production_use_date=datetime.date(2003, 1, 1),
            sn='1236-1236-1236-1236',
        )

    def test_start_date_is_equal_end_date(self):
        url = '?production_use_date_from=%s&production_use_date_to=%s' % (
            '2001-01-01', '2001-01-01')
        content = self.client.get(self.base_url + url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 1)
        self.assertEqual(rows_from_table[0].sn, '1234-1234-1234-1234')

    def test_start_date_is_less_then_end_date(self):
        url = '?production_use_date_from=%s&production_use_date_to=%s' % (
            '2011-01-01', '2002-01-01')
        content = self.client.get(self.base_url + url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 0)

    def test_find_more_assets_lte_gte(self):
        url = '?production_use_date_from=%s&production_use_date_to=%s' % (
            '2001-01-01', '2002-01-01')
        content = self.client.get(self.base_url + url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 2)

        self.assertItemsEqual(
            [asset.sn for asset in rows_from_table],
            ['1234-1234-1234-1234', '1235-1235-1235-1235']
        )

    def test_start_date_is_empty(self):
        url = '?production_use_date_from=%s&production_use_date_to=%s' % (
            '', '2001-01-01')
        content = self.client.get(self.base_url + url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 1)
        self.assertEqual(rows_from_table[0].sn, '1234-1234-1234-1234')

    def test_end_date_is_empty(self):
        url = '?production_use_date_from=%s&production_use_date_to=%s' % (
            '1999-01-01', '')
        content = self.client.get(self.base_url + url)
        self.assertEqual(content.status_code, 200)

        rows_from_table = content.context_data['bob_page'].object_list
        self.assertEqual(len(rows_from_table), 3)


class TestSearchEngine(TestCase):
    """General tests for search engine."""
    def setUp(self):
        self.client = login_as_su()
        self.testing_urls = {
            'dc': reverse('asset_search', args=('dc',)),
            'bo': reverse('asset_search', args=('back_office',)),
        }
        self.assets_dc = [AssetFactory() for _ in range(5)]
        self.assets_bo = [BOAssetFactory() for _ in range(5)]
        for name in ['iPad 5 16 GB', 'ProLiant BL2x2d', 'WS-CBS312']:
            AssetFactory(model__name=name)
            BOAssetFactory(model__name=name)

        for manufacturer in ['Apple', 'Sony', 'Nikon', 'Sony Ericsson']:
            manu = AssetManufacturerFactory(name=manufacturer)
            AssetFactory(model__manufacturer=manu)
            BOAssetFactory(model__manufacturer=manu)
            sam.LicenceFactory(manufacturer=manu)

        for unique in ['123456', '456123']:
            AssetFactory(barcode=unique, sn=unique, niw=unique)
        for unique in ['654321', '321654']:
            BOAssetFactory(barcode=unique, sn=unique, niw=unique)

        self.msg_error = 'Error in {}, request has return {} but expected {}.'

    def _search_results(self, url, field_name=None, value=None):
        if field_name and value:
            field_query = '='.join([field_name, value])
        else:
            field_query = ''
        url = '{}?{}'.format(url, field_query)
        response = self.client.get(url)
        return response.context['bob_page'].paginator.object_list

    def _check_results_length(self, url, field_name, value, expected):
        results = self._search_results(url, field_name, urllib.quote(value))
        self.assertEqual(
            len(results), expected,
            self.msg_error.format(url, len(results), expected),
        )

    def _field_exact(self, field_name):
        self._check_results_length(
            self.testing_urls['dc'], field_name, '"123456"', 1
        )
        self._check_results_length(
            self.testing_urls['dc'], field_name, '"12345"', 0
        )

        self._check_results_length(
            self.testing_urls['bo'], field_name, '"654321"', 1
        )
        self._check_results_length(
            self.testing_urls['bo'], field_name, '"654320"', 0
        )

    def _field_multi(self, field_name):
        self._check_results_length(
            self.testing_urls['dc'], field_name, '123456;456123', 2
        )
        self._check_results_length(
            self.testing_urls['bo'], field_name, '654321;321654', 2
        )

    def _field_icontains(self, field_name):
        self._check_results_length(
            self.testing_urls['dc'], field_name, '456', 2
        )
        self._check_results_length(
            self.testing_urls['dc'], field_name, '2345', 1
        )
        self._check_results_length(
            self.testing_urls['dc'], field_name, '9875', 0
        )
        self._check_results_length(
            self.testing_urls['bo'], field_name, '321', 2
        )

    def _check_search_result_count(self, data_to_check):
        for url, field_name, value, expected in data_to_check:
            self._check_results_length(url, field_name, value, expected)

    def test_model_exact(self):
        field_name = 'model'
        for _, url in self.testing_urls.items():
            self._check_results_length(url, field_name, '"iPad 5 16 GB"', 1)
            self._check_results_length(url, field_name, '"iPad 5 "', 0)

    def test_model_icontains(self):
        field_name = 'model'
        for _, url in self.testing_urls.items():
            self._check_results_length(url, field_name, 'model', 11)
            self._check_results_length(url, field_name, 'gb', 1)
            self._check_results_length(url, field_name, 'P', 2)
            self._check_results_length(url, field_name, '404', 0)

    def test_manufacturer_exact(self):
        urls = self.testing_urls.copy()
        urls['license'] = reverse('licence_list')
        field_name = 'manufacturer'
        for url in urls.values():
            self._check_results_length(url, field_name, '"Sony"', 1)
            self._check_results_length(url, field_name, '"Apple"', 1)
            self._check_results_length(url, field_name, '"Sony Ericsson"', 1)
            self._check_results_length(url, field_name, '"Manu 404"', 0)

    def test_manufacturer_icontains(self):
        urls = self.testing_urls.copy()
        urls['license'] = reverse('licence_list')
        field_name = 'manufacturer'
        for url in urls.values():
            self._check_results_length(url, field_name, 'Sony', 2)
            self._check_results_length(url, field_name, 'pp', 1)
            self._check_results_length(url, field_name, 'o', 3)

    def test_barcode(self):
        field_name = 'barcode'
        self._field_exact(field_name)
        self._field_multi(field_name)
        self._field_icontains(field_name)

    def test_sn(self):
        field_name = 'sn'
        self._field_exact(field_name)
        self._field_multi(field_name)
        self._field_icontains(field_name)

    def test_niw(self):
        field_name = 'niw'
        self._field_exact(field_name)
        self._field_multi(field_name)
        self._field_icontains(field_name)

    def test_hostname(self):
        for hostname in ("POLPC10000", "POLPC10001"):
            DCAssetFactory(hostname=hostname)
        for hostname in ("POLPC20000", "POLPC20001"):
            BOAssetFactory(hostname=hostname)

        field_name = 'hostname'
        self._check_search_result_count([
            # exact check
            (self.testing_urls['dc'], field_name, '"POLPC10001"', 1),
            (self.testing_urls['dc'], field_name, '"POLPC1000"', 0),
            (self.testing_urls['bo'], field_name, '"POLPC20001"', 1),
            (self.testing_urls['bo'], field_name, '"POLPC2000"', 0),
            # multi check
            (self.testing_urls['dc'], field_name, 'POLPC10000;POLPC10001', 2),
            (self.testing_urls['bo'], field_name, 'POLPC20000;POLPC20001', 2),
            # icontains check
            (self.testing_urls['dc'], field_name, 'POLPC1', 2),
            (self.testing_urls['dc'], field_name, '10001', 1),
            (self.testing_urls['dc'], field_name, 'none', 0),
            (self.testing_urls['bo'], field_name, 'POLPC2', 2),
            (self.testing_urls['bo'], field_name, '20001', 1),
            (self.testing_urls['bo'], field_name, 'none', 0),
        ])

    def test_service(self):
        DCAssetFactory(service=ServiceCatalogFactory(name='dc-service.com'))
        DCAssetFactory(service=ServiceCatalogFactory(name='dc-service2.com'))
        BOAssetFactory(service=ServiceCatalogFactory(name='bo-service.com'))
        BOAssetFactory(service=ServiceCatalogFactory(name='bo-service2.com'))

        field_name = 'service'
        self._check_search_result_count([
            # exact check
            (self.testing_urls['dc'], field_name, '"dc-service.com"', 1),
            (self.testing_urls['dc'], field_name, 'fake-dc', 0),
            (self.testing_urls['bo'], field_name, '"bo-service.com"', 1),
            (self.testing_urls['bo'], field_name, 'fake-bo', 0),
            # icontains check
            (self.testing_urls['dc'], field_name, 'dc', 2),
            (self.testing_urls['dc'], field_name, 'dc-service2', 1),
            (self.testing_urls['dc'], field_name, 'none', 0),
            (self.testing_urls['bo'], field_name, 'bo', 2),
            (self.testing_urls['bo'], field_name, 'bo-service2', 1),
            (self.testing_urls['bo'], field_name, 'none', 0),
        ])

    def test_device_environment(self):
        DCAssetFactory(
            device_environment=DeviceEnvironmentFactory(name='dc-dev-env'),
        )
        DCAssetFactory(
            device_environment=DeviceEnvironmentFactory(name='dc-dev-env2'),
        )
        BOAssetFactory(
            device_environment=DeviceEnvironmentFactory(name='bo-dev-env'),
        )
        BOAssetFactory(
            device_environment=DeviceEnvironmentFactory(name='bo-dev-env2'),
        )

        field_name = 'device_environment'
        self._check_search_result_count([
            # exact check
            (self.testing_urls['dc'], field_name, '"dc-dev-env"', 1),
            (self.testing_urls['dc'], field_name, 'fake-dc', 0),
            (self.testing_urls['bo'], field_name, '"bo-dev-env"', 1),
            (self.testing_urls['bo'], field_name, 'fake-bo', 0),
            # icontains check
            (self.testing_urls['dc'], field_name, 'dc', 2),
            (self.testing_urls['dc'], field_name, 'dc-dev-env2', 1),
            (self.testing_urls['dc'], field_name, 'none', 0),
            (self.testing_urls['bo'], field_name, 'bo', 2),
            (self.testing_urls['bo'], field_name, 'bo-dev-env2', 1),
            (self.testing_urls['bo'], field_name, 'none', 0),
        ])

    def test_support_requirement(self):
        """
        - add asset a1 with required_support=True
        - add asset a2 with required_support=False
        - send request without param *required_support*
            - assert found: all-assets
        - send request with required_support=yes
            - assert found: 1
        - send request with required_support=no
            - assert found: (all-assets - 1)
        """
        DCAssetFactory(**{'required_support': True})
        DCAssetFactory(**{'required_support': False})

        assets_count = Asset.objects.filter(
            type=AssetType.data_center.id
        ).count()
        self._check_results_length(
            self.testing_urls['dc'], 'required_support', '', assets_count,
        )
        self._check_results_length(
            self.testing_urls['dc'], 'required_support', 'yes', 1,
        )
        self._check_results_length(
            self.testing_urls['dc'],
            'required_support',
            'no',
            assets_count - 1,
        )

    def test_support_assignment(self):
        """
        - add asset a1 without supports
        - add asset a2 with support s1
        - send request without param *support_assigned*
            - assert found: all-assets
        - send request with support_assigned=any
            - assert found: 1
        - send request with support_assigned=false
            - assert found: (all-assets - 1)
        """
        DCAssetFactory()
        DCAssetFactory(**dict(
            supports=(supports.DCSupportFactory(),),
        ))

        assets_count = Asset.objects.filter(
            type=AssetType.data_center.id
        ).count()
        self._check_results_length(
            self.testing_urls['dc'], 'support_assigned', '', assets_count,
        )
        self._check_results_length(
            self.testing_urls['dc'], 'support_assigned', 'any', 1,
        )
        self._check_results_length(
            self.testing_urls['dc'],
            'support_assigned',
            'none',
            assets_count - 1,
        )
