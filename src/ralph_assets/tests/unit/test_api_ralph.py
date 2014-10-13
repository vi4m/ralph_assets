# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from django.test import TestCase

from ralph_assets.api_ralph import get_asset, get_asset_by_sn_or_barcode
from ralph_assets.tests.utils.assets import (
    AssetCategoryFactory,
    AssetModelFactory,
    DCAssetFactory,
)
from ralph_assets.tests.utils.supports import DCSupportFactory


class TestApiRalph(TestCase):
    """Test internal API for Ralph"""

    def test_get_asset(self):
        """Test get asset information by ralph_device_id."""
        support1 = DCSupportFactory()
        support2 = DCSupportFactory()
        category = AssetCategoryFactory()
        model = AssetModelFactory(category=category)
        asset = DCAssetFactory(
            model=model,
            supports=[support1, support2],
        )
        asset_data = get_asset(asset.device_info.ralph_device_id)
        self.assertEqual(asset_data['sn'], asset.sn)
        self.assertEqual(asset_data['barcode'], asset.barcode)
        self.assertEqual(asset_data['supports'][0]['name'], support1.name)
        self.assertEqual(asset_data['supports'][0]['url'], support1.url)
        self.assertEqual(asset_data['supports'][1]['name'], support2.name)
        self.assertEqual(asset_data['supports'][1]['url'], support2.url)
        self.assertEqual(
            asset_data['required_support'], asset.required_support,
        )

    def test_none_existisng_asset(self):
        """Getting an assets when assest does not exist"""
        self.assertEqual(get_asset(666), None)

    def test_get_asset_with_empty_asset_source(self):
        """Getting an asset with empty 'source' field should also succeed."""
        category = AssetCategoryFactory()
        model = AssetModelFactory(category=category)
        asset = DCAssetFactory(model=model, source=None)
        asset_data = get_asset(asset.device_info.ralph_device_id)
        self.assertEqual(asset_data['source'], None)

    def test_get_asset_by_sn_or_barcode(self):
        category = AssetCategoryFactory()
        model = AssetModelFactory(category=category)
        asset = DCAssetFactory(
            model=model,
        )
        # by sn
        asset_data = get_asset_by_sn_or_barcode(asset.sn)
        self.assertEqual(asset_data['sn'], asset.sn)
        self.assertEqual(asset_data['barcode'], asset.barcode)
        # by barcode
        asset_data = get_asset_by_sn_or_barcode(asset.barcode)
        self.assertEqual(asset_data['sn'], asset.sn)
        self.assertEqual(asset_data['barcode'], asset.barcode)
        # not exists
        self.assertEqual(get_asset_by_sn_or_barcode('foo_ziew_123'), None)
