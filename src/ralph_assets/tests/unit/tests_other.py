# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
from dj.choices import Country

from django.contrib.auth.models import User
from django.test import TestCase
from django.test.utils import override_settings

from ralph.discovery.tests.util import DeviceFactory
from ralph_assets.models import AssetManufacturer
from ralph_assets import models_assets
from ralph_assets.models_sam import (
    AssetOwner,
    Licence,
    LicenceType,
    SoftwareCategory,
)
from ralph_assets.others import get_assets_rows, get_licences_rows
from ralph_assets.tests.util import (
    create_asset,
    create_category,
    create_model,
)
from ralph_assets.tests.utils import UserFactory
from ralph_assets.tests.utils.assets import (
    AssetCategoryFactory,
    AssetModelFactory,
    BOAssetFactory,
    DCAssetFactory,
    DeviceInfoFactory,
)
from ralph_assets.utils import iso2_to_iso3, iso3_to_iso2


class TestExportRelations(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('user', 'user@test.local')
        self.user.is_staff = False
        self.user.is_superuser = False
        self.user.first_name = 'Elmer'
        self.user.last_name = 'Stevens'
        self.user.save()

        self.owner = User.objects.create_user('owner', 'owner@test.local')
        self.owner.is_staff = False
        self.owner.is_superuser = False
        self.owner.first_name = 'Eric'
        self.owner.last_name = 'Brown'
        self.owner.save()

        self.category = create_category()
        self.model = create_model(category=self.category)
        self.asset = create_asset(
            sn='1111-1111-1111-1111',
            model=self.model,
            user=self.user,
            owner=self.owner,
            barcode='br-666',
            niw='niw=666',
        )

        self.software_category = SoftwareCategory(
            name='soft-cat1', asset_type=models_assets.AssetType.DC
        )
        self.software_category.save()

        self.manufacturer = AssetManufacturer(name='test_manufacturer')
        self.manufacturer.save()

        self.licence_type = LicenceType(name='test_licence_type')
        self.licence_type.save()

        self.property_of = AssetOwner(name="test_property")
        self.property_of.save()

        self.licence1 = Licence(
            licence_type=self.licence_type,
            software_category=self.software_category,
            manufacturer=self.manufacturer,
            property_of=self.property_of,
            number_bought=10,
            sn="test-sn",
            niw="niw-666",
            invoice_date=datetime.date(2014, 4, 28),
            invoice_no="666-999-666",
            price=1000.0,
            provider="test_provider",
            asset_type=models_assets.AssetType.DC,
        )
        self.licence1.save()

    def test_assets_rows(self):
        rows = [item for item in get_assets_rows()]

        self.assertEqual(
            rows,
            [
                [
                    'id', 'niw', 'barcode', 'sn', 'model__category__name',
                    'model__manufacturer__name', 'model__name',
                    'user__username', 'user__first_name', 'user__last_name',
                    'owner__username', 'owner__first_name',
                    'owner__last_name', 'status', 'service_name__name',
                    'property_of', 'warehouse__name',
                ],
                [
                    1, 'niw=666', 'br-666', '1111-1111-1111-1111',
                    'Subcategory', 'Manufacturer1', 'Model1', 'user',
                    'Elmer', 'Stevens', 'owner', 'Eric', 'Brown', 1, None,
                    None, 'Warehouse',
                ],
            ]
        )

    def test_licences_rows(self):
        self.licence1.assets.add(self.asset)
        self.licence1.users.add(self.user)
        self.licence1.users.add(self.owner)
        rows = [item for item in get_licences_rows()]

        self.assertEqual(
            rows,
            [
                [
                    'niw', 'software_category', 'number_bought', 'price',
                    'invoice_date', 'invoice_no', 'id', 'barcode', 'niw',
                    'user__username', 'user__first_name', 'user__last_name',
                    'owner__username', 'owner__first_name',
                    'owner__last_name', 'username', 'first_name',
                    'last_name', 'single_cost',
                ],
                [
                    'niw-666', 'soft-cat1', '10', '1000', '2014-04-28',
                    '666-999-666', '', '', '', '', '', '', '', '', '', '', '',
                    '',
                ],
                [
                    'niw-666', 'soft-cat1', '10', '1000', '2014-04-28',
                    '666-999-666', '1', 'br-666', 'niw=666', 'user', 'Elmer',
                    'Stevens', 'owner', 'Eric', 'Brown', '', '', '', '', '',
                    '', '', '', '', '', '', '',
                ],
                [
                    'niw-666', 'soft-cat1', '10', '1000', '2014-04-28',
                    '666-999-666', '', '', '', '', '', '', '', '', '', 'user',
                    'Elmer', 'Stevens', '100',
                ],
                [
                    'niw-666', 'soft-cat1', '10', '1000', '2014-04-28',
                    '666-999-666', '', '', '', '', '', '', '', '', '', 'owner',
                    'Eric', 'Brown', '100',
                ],
            ]
        )

    def test_licences_rows_only_assigned(self):
        self.licence1.assets.add(self.asset)
        self.licence1.users.add(self.user)
        self.licence1.users.add(self.owner)
        rows = [item for item in get_licences_rows(only_assigned=True)]

        self.assertEqual(
            rows,
            [
                [
                    'niw', 'software_category', 'number_bought', 'price',
                    'invoice_date', 'invoice_no', 'id', 'barcode', 'niw',
                    'user__username', 'user__first_name', 'user__last_name',
                    'owner__username', 'owner__first_name',
                    'owner__last_name', 'username', 'first_name',
                    'last_name', 'single_cost',
                ],
                [
                    'niw-666', 'soft-cat1', '10', '1000', '2014-04-28',
                    '666-999-666', '1', 'br-666', 'niw=666', 'user', 'Elmer',
                    'Stevens', 'owner', 'Eric', 'Brown', '', '', '', '', '',
                    '', '', '', '', '', '', '',
                ],
                [
                    'niw-666', 'soft-cat1', '10', '1000', '2014-04-28',
                    '666-999-666', '', '', '', '', '', '', '', '', '',
                    'user', 'Elmer', 'Stevens', '100',
                ],
                [
                    'niw-666', 'soft-cat1', '10', '1000', '2014-04-28',
                    '666-999-666', '', '', '', '', '', '', '', '', '',
                    'owner', 'Eric', 'Brown', '100',
                ],
            ]
        )


class TestHostnameGenerator(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.user_pl = UserFactory()
        self.user_pl.profile.country = Country.pl
        self.user_pl.profile.save()
        self.cat = AssetCategoryFactory()
        self.cat1 = AssetCategoryFactory()
        self.cat2 = AssetCategoryFactory()
        self.cat3 = AssetCategoryFactory()
        self.asset1 = BOAssetFactory()
        self.asset2 = BOAssetFactory()

    def _check_hostname_not_generated(self, asset):
        asset._try_assign_hostname(True)
        changed_asset = models_assets.Asset.objects.get(pk=asset.id)
        self.assertEqual(changed_asset.hostname, None)

    def _check_hostname_is_generated(self, asset):
        asset._try_assign_hostname(True)
        changed_asset = models_assets.Asset.objects.get(pk=asset.id)
        self.assertTrue(len(changed_asset.hostname) > 0)

    def test_generate_first_hostname(self):
        """Scenario:
         - none of assets has hostname
         - after generate first of asset have XXXYY00001 in hostname field
        """
        category = AssetCategoryFactory(code='PC')
        model = AssetModelFactory(category=category)
        asset = BOAssetFactory(model=model, owner=self.user_pl, hostname='')
        template_vars = {
            'code': asset.model.category.code,
            'country_code': asset.country_code,
        }
        asset.generate_hostname(template_vars=template_vars)
        self.assertEqual(asset.hostname, 'POLPC00001')

    def test_generate_next_hostname(self):
        category = AssetCategoryFactory(code='PC')
        model = AssetModelFactory(category=category)
        asset = BOAssetFactory(model=model, owner=self.user_pl, hostname='')
        BOAssetFactory(owner=self.user_pl, hostname='POLSW00003')
        models_assets.AssetLastHostname.increment_hostname(prefix='POLPC')
        models_assets.AssetLastHostname.increment_hostname(prefix='POLPC')
        template_vars = {
            'code': asset.model.category.code,
            'country_code': asset.country_code,
        }
        asset.generate_hostname(template_vars=template_vars)
        self.assertEqual(asset.hostname, 'POLPC00003')

    def test_cant_generate_hostname_for_model_without_category(self):
        model = AssetModelFactory(category=None)
        asset = BOAssetFactory(model=model, owner=self.user_pl, hostname='')
        self._check_hostname_not_generated(asset)

    def test_can_generate_hostname_for_model_with_hostname(self):
        category = AssetCategoryFactory(code='PC')
        model = AssetModelFactory(category=category)
        asset = BOAssetFactory(model=model, owner=self.user_pl)
        self._check_hostname_is_generated(asset)

    def test_cant_generate_hostname_for_model_without_user(self):
        model = AssetModelFactory()
        asset = BOAssetFactory(model=model, owner=None, hostname='')
        self._check_hostname_not_generated(asset)

    def test_cant_generate_hostname_for_model_without_user_and_category(self):
        model = AssetModelFactory(category=None)
        asset = BOAssetFactory(model=model, owner=None, hostname='')
        self._check_hostname_not_generated(asset)

    def test_generate_next_hostname_out_of_range(self):
        category = AssetCategoryFactory(code='PC')
        model = AssetModelFactory(category=category)
        asset = BOAssetFactory(model=model, owner=self.user_pl, hostname='')
        models_assets.AssetLastHostname.objects.create(
            prefix='POLPC', counter=99999
        )
        template_vars = {
            'code': asset.model.category.code,
            'country_code': asset.country_code,
        }
        asset.generate_hostname(template_vars=template_vars)
        self.assertEqual(asset.hostname, 'POLPC100000')

    def test_convert_iso2_to_iso3(self):
        self.assertEqual(iso2_to_iso3['PL'], 'POL')

    def test_convert_iso3_to_iso2(self):
        self.assertEqual(iso3_to_iso2['POL'], 'PL')


@override_settings(ASSETS_AUTO_ASSIGN_HOSTNAME=True)
class TestHostnameAssigning(TestCase):
    neutral_status = models_assets.AssetStatus.new
    trigger_status = models_assets.AssetStatus.in_progress

    def setUp(self):
        self.owner = UserFactory()
        self.neutral_status = models_assets.AssetStatus.new
        self.trigger_status = models_assets.AssetStatus.in_progress
        self.owner_country_name = models_assets.get_user_iso3_country_name(
            self.owner
        )

    def test_assigning_when_no_hostname(self):
        """
        Generate hostname when it's none.
        """
        no_hostname_asset = BOAssetFactory(**{'hostname': None})
        self.assertEqual(no_hostname_asset.hostname, None)
        no_hostname_asset._try_assign_hostname(True)
        self.assertNotEqual(no_hostname_asset.hostname, None)

    def test_assigning_when_different_country(self):
        """
        Generate hostname when user has diffrent country than country from
        hostname.
        """
        asset = BOAssetFactory(**{'owner': self.owner})
        old_hostname = asset.hostname
        self.assertNotIn(self.owner_country_name, asset.hostname)
        asset._try_assign_hostname(True)
        self.assertNotEqual(asset.hostname, old_hostname)
        self.assertIn(self.owner_country_name, asset.hostname)

    def test_assigning_when_same_country(self):
        """
        Keep existing hostname when user has the same country name
        """
        def _asset_from_country(iso3_country):
            asset = BOAssetFactory()
            hostname = asset.hostname.replace('XXX', iso3_country)
            asset.hostname = hostname
            asset.save()
            return asset
        asset = _asset_from_country(self.owner_country_name)
        old_hostname = asset.hostname
        asset._try_assign_hostname(True)
        self.assertEqual(asset.hostname, old_hostname)


class TestLinkedDevice(TestCase):
    def test_bo_asset(self):
        asset = BOAssetFactory()
        self.assertEqual(asset.linked_device, None)

    def test_dc_asset_with_linked_device(self):
        core_device = DeviceFactory()
        device_info = DeviceInfoFactory(ralph_device_id=core_device.id)
        asset = DCAssetFactory(device_info=device_info)
        self.assertEqual(asset.linked_device, core_device)

    def test_dc_asset_without_linked_device(self):
        asset = DCAssetFactory(device_info=None)
        asset.save()
        self.assertEqual(asset.linked_device, None)
