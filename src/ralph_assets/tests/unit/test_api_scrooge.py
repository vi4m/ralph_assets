# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from datetime import date

from django.test import TestCase

from ralph_assets import models
from ralph_assets import api_scrooge
from ralph_assets.tests.utils.assets import (
    DCAssetFactory,
    AssetModelFactory,
    WarehouseFactory,
)


class TestApiScrooge(TestCase):
    """Test internal API for Scrooge"""

    def test_get_warehouse(self):
        warehouse1 = WarehouseFactory()
        warehouse2 = WarehouseFactory()
        result = [w for w in api_scrooge.get_warehouses()]
        self.assertEquals(result, [
            {
                'warehouse_id': warehouse1.id,
                'warehouse_name': warehouse1.name,
            },
            {
                'warehouse_id': warehouse2.id,
                'warehouse_name': warehouse2.name,
            },
        ])

    def test_get_models(self):
        model1 = AssetModelFactory(type=models.AssetType.data_center)
        model2 = AssetModelFactory(
            type=models.AssetType.data_center,
            manufacturer=None,
        )
        model3 = AssetModelFactory(
            type=models.AssetType.data_center,
            category=None
        )
        AssetModelFactory(type=models.AssetType.back_office)
        result = [m for m in api_scrooge.get_models()]
        self.assertEquals(result, [
            {
                'model_id': model1.id,
                'name': model1.name,
                'manufacturer': model1.manufacturer.name,
                'category': model1.category.name,
            },
            {
                'model_id': model2.id,
                'name': model2.name,
                'manufacturer': None,
                'category': model2.category.name,
            },
            {
                'model_id': model3.id,
                'name': model3.name,
                'manufacturer': model3.manufacturer.name,
                'category': None,
            },
        ])

    def _compare_asset(self, asset, api_result, date, name):
        self.assertEquals(api_result, {
            'asset_id': asset.id,
            'device_id': asset.device_info.ralph_device_id,
            'asset_name': name,
            'service_id': asset.service.id,
            'environment_id': asset.device_environment_id,
            'sn': asset.sn,
            'barcode': asset.barcode,
            'warehouse_id': asset.warehouse_id,
            'cores_count': asset.cores_count,
            'power_consumption': asset.model.power_consumption,
            'collocation': asset.model.height_of_device,
            'depreciation_rate': asset.deprecation_rate,
            'is_depreciated': asset.is_deprecated(date=date),
            'price': asset.price,
            'model_id': asset.model_id,
        })

    def test_get_assets(self):
        asset = DCAssetFactory(
            invoice_date=date(2013, 10, 11),
        )
        today = date(2013, 11, 12)
        result = [a for a in api_scrooge.get_assets(today)]
        self._compare_asset(
            asset,
            result[0],
            today,
            asset.device_info.get_ralph_device().name
        )

    def test_get_assets_without_invoice(self):
        asset = DCAssetFactory(
            invoice_date=None,
        )
        today = date(2013, 11, 12)
        result = [a for a in api_scrooge.get_assets(today)]
        self._compare_asset(
            asset,
            result[0],
            today,
            asset.device_info.get_ralph_device().name
        )

    def test_get_asset_without_hostname(self):
        asset = DCAssetFactory()
        asset.device_info.ralph_device_id = None
        asset.device_info.save()
        today = date(2013, 11, 12)
        result = [a for a in api_scrooge.get_assets(today)]
        self._compare_asset(
            asset,
            result[0],
            today,
            None,
        )

    def test_get_assets_without_device_info(self):
        DCAssetFactory(
            device_info=None,
        )
        today = date(2013, 11, 12)
        result = [a for a in api_scrooge.get_assets(today)]
        self.assertEquals(result, [])

    def test_get_assets_without_service(self):
        DCAssetFactory(
            service=None,
        )
        today = date(2013, 11, 12)
        result = [a for a in api_scrooge.get_assets(today)]
        self.assertEquals(result, [])

    def test_get_assets_without_environment(self):
        DCAssetFactory(
            service=None,
            device_environment=None,
        )
        today = date(2013, 11, 12)
        result = [a for a in api_scrooge.get_assets(today)]
        self.assertEquals(result, [])
