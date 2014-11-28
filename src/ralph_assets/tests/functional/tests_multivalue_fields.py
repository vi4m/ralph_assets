# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from django.test import TestCase
from ralph.account.models import Region

from ralph.cmdb.tests.utils import CIRelationFactory
from ralph_assets.models_assets import Asset, AssetType, AssetStatus
from ralph_assets.tests.functional.tests_view import TestDevicesView
from ralph_assets.tests.util import SCREEN_ERROR_MESSAGES
from ralph_assets.tests.utils.assets import (
    AssetCategoryFactory,
    AssetModelFactory,
    DCAssetFactory,
    WarehouseFactory,
)
from ralph.ui.tests.global_utils import login_as_su


class TestMultivalueFields(TestDevicesView, TestCase):
    asset_factory = DCAssetFactory
    mode = 'dc'

    def setUp(self):
        self.client = login_as_su()
        self.warehouse = WarehouseFactory()
        self.category = AssetCategoryFactory()
        self.model = AssetModelFactory(category=self.category)
        self.addform = '/assets/dc/add/device/'
        ci_relation = CIRelationFactory()
        self.common_test_data = self.get_asset_form_data({
            'barcode': '',
            'sn': '',
        })
        self.common_test_data.update(dict(
            asset=True,
            deprecation_rate=0,
            device_environment=ci_relation.child.id,
            invoice_date='2001-01-02',
            model=self.model.id,
            price='10',
            production_year=2011,
            ralph_device_id='',
            region=Region.get_default_region().id,
            service=ci_relation.parent.id,
            size=1,
            slots=1,
            source=1,
            status=AssetStatus.new.id,
            type=AssetType.data_center.id,
            warehouse=self.warehouse.id,
        ))

    def test_add_form_testing_sn_and_barcode(self):
        """
        Test multivalue fields.

        Scenario:
        1. Add many SNs and barcodes in different forms.
        2. Verify that the form doesn't add empty serial number
        3. Test relationship between SNs and barcodes.
        4. Verity names with white spaces (SNs, barcode).
        """

        test_data = [
            dict(
                sn='', barcode='', remarks='asset0',
                desc='SN or Barcode required.'
            ),
            dict(sn='sn1_1, sn2_1, sn1_1', remarks='asset1'),
            dict(sn='sn1_2, , , sn2_2', remarks='asset2'),
            dict(sn='sn1_3, ,, sn2_3', remarks='asset3'),
            dict(sn='sn1_4, ns2_4 \n sn3_4', remarks='asset4'),
            dict(
                sn='name with white spaces, 0000-0000-0000-0000',
                remarks='asset5'
            ),
            dict(sn='', barcode='any', remarks='asset6'),
            dict(sn='serialnumber1', barcode='any1, any2', remarks='asset7'),
            dict(
                sn='serialnumber2, serialnumber3',
                barcode='any3',
                remarks='asset8',
            ),
            dict(
                sn='serialnumber4, serialnumber5',
                barcode='any4, any 5',
                remarks='asset9',
            ),
            dict(
                sn='serialnumber6, serialnumber7, serialnumber8',
                barcode='any6 , , any 7',
                remarks='asset10',
            ),
            dict(
                sn='serialnumber9, serialnumber10, serialnumber11',
                barcode='any8 , \n, any9',
                remarks='asset11',
            ),
            dict(sn='serialnumber12', barcode='barcode1', remarks='asset12'),
        ]
        # Add form testing
        for partial_data in test_data:
            test = self.common_test_data.copy()
            test.update(partial_data)
            post = self.client.post(self.addform, test)
            added_assets = Asset.objects.filter(remarks=test['remarks'])
            if test['remarks'] == 'asset0':
                self.assertEqual(post.status_code, 200)
                for field in ['sn', 'barcode']:
                    self.assertFormError(
                        post, 'asset_form', field,
                        SCREEN_ERROR_MESSAGES['any_required'],
                    )
            elif test['remarks'] == 'asset1':
                self.assertEqual(post.status_code, 200)
                self.assertFormError(
                    post, 'asset_form', 'sn',
                    SCREEN_ERROR_MESSAGES['duplicated_sn_in_field']
                )
            elif test['remarks'] == 'asset2':
                self.assertEqual(post.status_code, 200)
                self.assertFormError(
                    post, 'asset_form', 'sn',
                    SCREEN_ERROR_MESSAGES['empty_items_disallowed']
                )
            elif test['remarks'] == 'asset3':
                self.assertEqual(post.status_code, 200)
                self.assertFormError(
                    post, 'asset_form', 'sn',
                    SCREEN_ERROR_MESSAGES['empty_items_disallowed']
                )
            elif test['remarks'] == 'asset4':
                self.assertEqual(post.status_code, 302)
                self.assertEqual(len(added_assets), 3)
                self.assertEqual(
                    ['sn1_4', 'ns2_4', 'sn3_4'],
                    [asset.sn for asset in added_assets]
                )
            elif test['remarks'] == 'asset5':
                self.assertFormError(
                    post, 'asset_form', 'sn',
                    SCREEN_ERROR_MESSAGES['contain_white_character']
                )
            elif test['remarks'] in ['asset9']:
                self.assertEqual(post.status_code, 200)
                self.assertFormError(
                    post, 'asset_form', 'barcode',
                    SCREEN_ERROR_MESSAGES['contain_white_character']
                )
            elif test['remarks'] in ['asset10', 'asset11']:
                self.assertEqual(post.status_code, 200)
                self.assertFormError(
                    post, 'asset_form', 'barcode',
                    SCREEN_ERROR_MESSAGES['empty_items_disallowed']
                )
            elif test['remarks'] == 'asset6':
                self.assertEqual(post.status_code, 302)
                self.assertEqual(len(added_assets), 1)
                self.assertEqual(
                    ['any'], [asset.barcode for asset in added_assets]
                )
            elif test['remarks'] in ['asset7', 'asset 8']:
                self.assertEqual(post.status_code, 200)
                self.assertFormError(
                    post, 'asset_form', 'barcode',
                    SCREEN_ERROR_MESSAGES['count_sn_and_bc']
                )
            elif test['remarks'] == 'asset9':
                self.assertEqual(post.status_code, 200)
                self.assertFormError(
                    post, 'asset_form', 'barcode',
                    SCREEN_ERROR_MESSAGES['contain_white_character']
                )
            elif test['remarks'] == 'asset12':
                duplicate = dict(
                    type=AssetType.data_center.id,
                    model=self.model.id,
                    support_period='1',
                    support_type='standard',
                    invoice_date='2001-01-02',
                    warehouse=self.warehouse.id,
                    status=AssetStatus.new.id,
                    sn='serialnumber13',
                    barcode='barcode1',
                    remarks='asset12',
                    ralph_device_id='',
                    size=1,
                )
                post = self.client.post(self.addform, duplicate)
                self.assertEqual(post.status_code, 200)
        empty_sn = Asset.objects.filter(sn=' ')
        self.assertEqual(len(empty_sn), 0)
        empty_sn = Asset.objects.filter(barcode=' ')
        self.assertEqual(len(empty_sn), 0)
