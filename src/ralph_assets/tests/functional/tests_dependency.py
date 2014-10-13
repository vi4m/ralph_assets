# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from django.test import TestCase
from ralph.cmdb.tests.utils import CIRelationFactory

from ralph_assets.models_assets import (
    Asset,
    AssetCategory,
    MODE2ASSET_TYPE,
)
from ralph_assets.tests.utils.assets import (
    AssetModelFactory,
    WarehouseFactory,
)
from ralph.ui.tests.global_utils import login_as_su


class TestDependency(TestCase):
    """Test adding/edit single asset with Dependency"""

    def setUp(self):
        self.client = login_as_su(is_superuser=True)
        self.category_blade = AssetCategory.objects.get(name='Server Blade')
        self.category_non_blade = AssetCategory.objects.get(name='Server Rack')
        self.model_blade = AssetModelFactory(category=self.category_blade)
        self.model_none_blade = AssetModelFactory(
            category=self.category_non_blade,
        )
        self.warehouse = WarehouseFactory()
        self.ci_relation = CIRelationFactory()

    def test_add_device_with_blade_model(self):
        """Add device when choosen model category is_blade"""
        self.client.post(
            reverse('add_device', kwargs={'mode': 'dc'}),
            {
                'category': self.category_blade.pk,
                'deprecation_rate': '25',
                'device_environment': self.ci_relation.child.id,
                'model': self.model_blade.id,
                'ralph_device_id': '',
                'service': self.ci_relation.parent.id,
                'sn': '123456789',
                'type': MODE2ASSET_TYPE['dc'].id,
                'warehouse': self.warehouse.id,
            }
        )
        self.assertEqual(Asset.objects.count(), 1)

    def test_add_device_non_blade_model(self):
        """Add device when choosen model category is not blade"""
        self.client.post(
            reverse('add_device', kwargs={'mode': 'dc'}),
            {
                'category': self.category_non_blade.pk,
                'deprecation_rate': '25',
                'device_environment': self.ci_relation.child.id,
                'model': self.model_none_blade.id,
                'ralph_device_id': '',
                'service': self.ci_relation.parent.id,
                'sn': '123456789',
                'type': MODE2ASSET_TYPE['dc'].id,
                'warehouse': self.warehouse.id,
            }
        )
        self.assertEqual(Asset.objects.count(), 1)
