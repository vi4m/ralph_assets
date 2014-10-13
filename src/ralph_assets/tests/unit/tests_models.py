# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
from django.test import TestCase

from ralph.business.models import Venture
from ralph.discovery.models_device import Device, DeviceType

from ralph_assets.api_pricing import get_assets, get_asset_parts
from ralph_assets.models_assets import PartInfo
from ralph_assets.tests.utils.assets import (
    AssetSubCategoryFactory,
    AssetModelFactory,
    AssetFactory,
)
from ralph_assets.tests.utils.assets import ServiceFactory
from ralph_assets.tests.utils.sam import LicenceFactory


class TestModelAsset(TestCase):
    def setUp(self):
        self.asset = AssetFactory(
            invoice_date=datetime.date(2012, 11, 28),
            support_period=1,
            deprecation_rate=100,
        )
        self.asset.device_info.ralph_device_id = 666
        self.asset.device_info.save()
        self.asset2 = AssetFactory(
            invoice_date=datetime.date(2012, 11, 28),
            support_period=120,
            deprecation_rate=50,
        )
        self.asset2.device_info.ralph_device_id = 667
        self.asset2.device_info.save()
        self.asset3 = AssetFactory(
            invoice_date=datetime.date(2012, 11, 28),
            support_period=120,
            deprecation_rate=50,
            force_deprecation=True,
        )
        self.asset_depr_date = AssetFactory(
            sn='1111-1111-1111-1114',
            invoice_date=datetime.date(2012, 11, 28),
            support_period=120,
            deprecation_rate=50,
            deprecation_end_date=datetime.date(2014, 12, 15),
        )
        self.dev1 = Device.create(
            [('1', 'sda', 0)],
            model_name='xxx',
            model_type=DeviceType.rack_server,
            allow_stub=1,
        )
        self.dev1.id = 666
        self.dev1.save()
        dev2 = Device.create(
            [('1', 'dawdwad', 0)],
            model_name='Unknown',
            model_type=DeviceType.unknown,
            allow_stub=1,
        )
        dev2.id = 667
        dev2.save()

    def test_is_discovered(self):
        self.assertEqual(self.asset.is_discovered, True)
        self.assertEqual(self.asset2.is_discovered, False)
        self.assertEqual(self.asset3.is_discovered, False)

    def test_is_deperecation(self):
        date = datetime.date(2014, 03, 29)
        self.assertEqual(self.asset.get_deprecation_months(), 12)
        self.assertEqual(self.asset2.get_deprecation_months(), 24)
        self.assertEqual(self.asset.is_deprecated(date), True)
        self.assertEqual(self.asset2.is_deprecated(date), False)
        self.assertEqual(self.asset3.is_deprecated(date), True)
        self.assertEqual(
            self.asset_depr_date.is_deprecated(datetime.date(2014, 12, 10)),
            False,
        )
        self.assertEqual(
            self.asset_depr_date.is_deprecated(datetime.date(2014, 12, 20)),
            True,
        )

    def test_venture(self):
        venture = Venture.objects.create(name='v1')
        self.dev1.venture = venture
        self.dev1.save()

        asset_without_device = AssetFactory(device_info=None)

        self.assertEqual(self.asset.venture, venture)
        self.assertEqual(self.asset2.venture, None)
        self.assertEqual(asset_without_device.venture, None)


class TestModelLicences(TestCase):
    def setUp(self):
        self.licence = LicenceFactory()

    def test_remarks(self):
        """Remarks field is in model?"""
        self.licence.remarks = 'a' * 512
        self.licence.save()

        self.assertEqual(self.licence.remarks, 'a' * 512)

    def test_service_name(self):
        old_service = self.licence.service_name
        self.licence.service_name = ServiceFactory()
        self.licence.save()

        self.assertNotEqual(old_service, self.licence.service_name)


class TestApiAssets(TestCase):
    def setUp(self):
        self.category = AssetSubCategoryFactory(is_blade=True)
        self.model = AssetModelFactory(category=self.category)
        self.asset = AssetFactory(
            invoice_date=datetime.date(2012, 11, 28),
            support_period=1,
            slots=12.0,
            price=100,
            deprecation_rate=100,
            model=self.model,
        )
        part_info = PartInfo(device=self.asset)
        part_info.save()
        self.asset2 = AssetFactory(
            invoice_date=datetime.date(2012, 11, 28),
            support_period=1,
            slots=12.0,
            price=100,
            part_info=part_info,
            deprecation_rate=50,
            model=self.model,
        )
        self.stock_venture = Venture.objects.get(name='Stock')

    def tests_api_asset(self):
        date = datetime.date(2014, 03, 29)
        for item in get_assets(date):
            self.assertEqual(item['asset_id'], self.asset.id)
            self.assertEqual(
                item['ralph_id'], self.asset.device_info.ralph_device_id,
            )
            self.assertEqual(item['slots'], self.asset.slots)
            self.assertEqual(item['price'], self.asset.price)
            self.assertEqual(
                item['is_deprecated'],
                self.asset.is_deprecated(date)
            )
            self.assertEqual(item['sn'], self.asset.sn)
            self.assertEqual(item['barcode'], self.asset.barcode)
            self.assertEqual(item['venture_id'], self.stock_venture.id)
            self.assertEqual(item['is_blade'], self.category.is_blade)
            self.assertEqual(item['cores_count'], self.asset.cores_count)

    def tests_api_asset_part(self):
        for item in get_asset_parts():
            self.assertEqual(item['price'], 100)
            # self.assertEqual(item['is_deprecated'], False)
            model = self.model
            self.assertEqual(item['model'], model.name)
            self.assertEqual(item['asset_id'], self.asset2.id)
            self.assertEqual(item['sn'], self.asset.sn)
            self.assertEqual(item['barcode'], self.asset.barcode)


class TestModelHistory(TestCase):

    def test_asset(self):
        asset = AssetFactory(pk=123)
        history = asset.get_history()
        self.assertEqual(0, history.count())

        asset.sn = '123'
        asset.save()
        self.assertEqual(1, history.count())

        asset.sn = '1233'
        asset.save()
        self.assertEqual(2, history.count())

        licence = LicenceFactory()
        history = licence.get_history()
        licence.save()
        licence.save()
        self.assertEqual(0, history.count())

        for i in xrange(5):
            asset = AssetFactory()
            licence.assets.add(asset)
            self.assertEqual(i + 1, history.count())
