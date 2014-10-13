# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from django.test import TestCase

from ralph_assets import models_assets
from ralph_assets.tests.utils.assets import (
    AssetFactory,
    AssetCategoryFactory,
    AssetModelFactory,
    WarehouseFactory,
)
from ralph_assets.tests.util import (
    SCREEN_ERROR_MESSAGES,
    get_bulk_edit_post_data,
)
from ralph.ui.tests.global_utils import login_as_su


class TestValidations(TestCase):
    """Scenario:
    1. test validation (required fields) add, edit
    2. test wrong data in fields
    """

    def setUp(self):
        self.client = login_as_su()
        self.category = AssetCategoryFactory()
        self.model = AssetModelFactory(category=self.category)
        self.warehouse = WarehouseFactory()
        self.first_asset = AssetFactory(
            model=self.model,
        )
        self.second_asset = AssetFactory(
            model=self.model,
        )

        self.asset_with_duplicated_sn = AssetFactory(
            model=self.model,
        )

        # Prepare required fields (formset_name, field_name)
        self.required_fields = [
            ('asset_form', 'model'),
            ('asset_form', 'warehouse'),
        ]

        self.model1 = AssetModelFactory()

    def test_try_send_empty_add_form(self):
        send_post = self.client.post(
            '/assets/back_office/add/device/',
            {'ralph_device_id': '', 'sn': 'sn'},  # Test hock
        )
        self.assertEqual(send_post.status_code, 200)

        for field in self.required_fields:
            self.assertFormError(
                send_post, field[0], field[1], 'This field is required.'
            )

    def test_try_send_empty_edit_form(self):
        send_post = self.client.post(
            # TODO: there is high probability thst device is not exists
            '/assets/dc/edit/device/1/',
            {'ralph_device_id': ''},  # Test hock
        )
        self.assertEqual(send_post.status_code, 200)

        for field in self.required_fields:
            self.assertFormError(
                send_post, field[0], field[1], 'This field is required.'
            )

    def test_invalid_field_value(self):
        # instead of integers we send strings, error should be thrown
        url = '/assets/back_office/add/device/'
        post_data = {
            'size': 'string',
            'invoice_date': 'string',
            'ralph_device_id': '',
            'sn': 'string',
        }
        send_post = self.client.post(url, post_data)
        self.assertEqual(send_post.status_code, 200)

        self.assertFormError(
            send_post, 'asset_form', 'invoice_date', 'Enter a valid date.'
        )

    def test_send_wrong_data_in_bulkedit_form(self):
        url = '/assets/dc/bulkedit/?select=%s&select=%s&select=%s' % (
            self.first_asset.id,
            self.second_asset.id,
            self.asset_with_duplicated_sn.id,
        )
        post_data = get_bulk_edit_post_data(
            {
                'invoice_date': 'wrong_field_data',
                'sn': self.asset_with_duplicated_sn.sn,
            },
            {
                'invoice_date': '',
                'model': '',
                'status': '',
                'source': '',
            },
            {
                'invoice_no': '',
            }
        )

        send_post_with_empty_fields = self.client.post(url, post_data)

        # Try to send post with empty field send_post should be false
        try:
            self.assertRedirects(
                send_post_with_empty_fields,
                url,
                status_code=302,
                target_status_code=200,
            )
            send_post = True
        except AssertionError:
            send_post = False
        # If not here is error msg
        self.assertFalse(send_post, 'Empty fields was send!')

        # Find what was wrong
        bulk_data = [
            dict(
                row=0, field='invoice_date', error='Enter a valid date.',
            ),
            dict(
                row=0, field='sn', error='Asset with this Sn already exists.',
            ),
            dict(
                row=1,
                field='invoice_date',
                error='Invoice date cannot be empty.',
            ),
            dict(
                row=1, field='model', error='This field is required.',
            ),
            dict(
                row=2,
                field='invoice_no',
                error='Invoice number cannot be empty.',
            )
        ]
        for bulk in bulk_data:
            formset = send_post_with_empty_fields.context_data['formset']
            self.assertEqual(
                formset[bulk['row']]._errors[bulk['field']][0],
                bulk['error']
            )

        # if sn was duplicated, the message should be shown on the screen
        msg = SCREEN_ERROR_MESSAGES['duplicated_sn_or_bc']
        self.assertTrue(msg in send_post_with_empty_fields.content)

    def test_add_part(self):
        """
        1. Add part
        2. Add part again (with the same SN)
        3. Check that error message about existing SN is shown
        """
        required_part_data = {
            'type': 101,
            'model': self.model.id,
            'warehouse': self.warehouse.id,
            'sn': 'sn',
            'deprecation_rate': '5',
        }
        send_post = self.client.post(
            '/assets/back_office/add/part/',
            required_part_data,
        )
        self.assertEqual(send_post.status_code, 302)

        send_post = self.client.post(
            '/assets/back_office/add/part/',
            required_part_data,
        )
        self.assertEqual(send_post.status_code, 200)
        inserted_device = models_assets.Asset.objects.filter(
            sn=required_part_data['sn']
        ).get()
        expected = (
            'Following items already exist: <a href="'
            '/assets/back_office/edit/device/{id}/">{id}</a>'.format(
                id=inserted_device.id
            )
        )
        self.assertEqual(
            send_post.context['asset_form'].errors['sn'][0], expected
        )
