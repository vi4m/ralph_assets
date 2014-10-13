# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import urllib

from datetime import date

import django.dispatch
from dj.choices import Country
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.utils import override_settings


from ralph.ui.tests.global_utils import login_as_su
from ralph.ui.tests.global_utils import UserFactory
from ralph_assets import signals
from ralph_assets.models_assets import Asset
from ralph_assets.models_transition import Action
from ralph_assets.tests.utils import MessagesTestMixin
from ralph_assets.tests.utils.assets import BOAssetFactory, WarehouseFactory
from ralph_assets.tests.utils.transitions import (
    TransitionFactory, TransitionsHistoryFactory,
)
from ralph_assets.tests.utils.sam import LicenceFactory


ASSETS_TRANSITIONS = {
    'ENABLE': True,
    'SLUGS': {
        'RELEASE-ASSET': 'release-asset',
        'LOAN-ASSET': 'loan-asset',
        'RETURN-ASSET': 'return-asset',
        'CHANGE-HOSTNAME': 'change-hostname',
    }
}


@override_settings(ASSETS_AUTO_ASSIGN_HOSTNAME=True)
@override_settings(ASSETS_TRANSITIONS=ASSETS_TRANSITIONS)
class TestTransitionHostname(MessagesTestMixin, TestCase):

    def setUp(self):
        self.client = login_as_su()
        self.prepare_transition()

    def assertMessageEqual(self, response, text):
        """
        Asserts that the response includes the message text.
        """
        messages = [m.message for m in response.context['messages']]
        if text not in messages:
            self.fail(
                'No message with text "{}", messages were: {}'.format(
                    text, messages,
                )
            )

    def prepare_transition(self):
        self.transition = TransitionFactory()
        self.transition.actions.add(Action.objects.get(name='change_hostname'))

    def test_change_hostname_success(self):
        asset = BOAssetFactory(**{
            'hostname': '',
            'model__category__code': 'PC',
        })
        post_data = {'country': Country.pl.id}
        url_base = reverse('transition', args=('back_office',))
        url_params = {'select': asset.id, 'transition_type': 'change-hostname'}
        url = "{}?{}".format(url_base, urllib.urlencode(url_params))
        self.client.post(url, post_data, follow=True)
        changed_asset = Asset.objects.get(pk=asset.id)
        self.assertEqual(changed_asset.hostname, 'POLPC00001')

    def test_change_hostname_failed(self):
        """Asset model has not assigned category with code,
        hostname will be not generated"""
        asset = BOAssetFactory(**{
            'hostname': '',
            'model__category__code': '',
        })
        post_data = {'country': Country.pl.id}
        url_base = reverse('transition', args=('back_office',))
        url_params = {'select': asset.id, 'transition_type': 'change-hostname'}
        url = "{}?{}".format(url_base, urllib.urlencode(url_params))
        response = self.client.get(url, follow=True)
        self.assertMessageEqual(
            response,
            'Asset has no assigned category with code',
        )
        self.client.post(url, post_data, follow=True)
        changed_asset = Asset.objects.get(pk=asset.id)
        self.assertEqual(changed_asset.hostname, None)

    def _get_simple_transition_data(self):
        """Executes steps required by transition"""
        asset = BOAssetFactory(**{
            'hostname': '',
            'model__category__code': 'PC',
        })
        post_data = {'country': Country.pl.id}
        url_base = reverse('transition', args=('back_office',))
        url_params = {
            'select': asset.id,
            'transition_type': 'change-hostname',
        }
        url = "{}?{}".format(
            url_base, urllib.urlencode(url_params)
        )
        return url, post_data

    def test_successful_post_transition(self):
        """
        Transition is done successfully.
        """
        @django.dispatch.receiver(signals.post_transition)
        def post_transition_handler(
            sender, user, assets, transition, **kwargs
        ):
            pass

        url, post_data = self._get_simple_transition_data()
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(len(response.context['messages']), 1)
        self.assertEqual(
            str(response.context['messages']._loaded_messages[0]),
            "Transitions performed successfully",
        )

    def test_failed_post_transition(self):
        """
        Transition is done unsuccessfully.
        """
        @django.dispatch.receiver(signals.post_transition)
        def post_transition_handler(
            sender, user, assets, transition, **kwargs
        ):
            from ralph_assets.views import transition
            raise transition.PostTransitionException(
                "Unable to generate document - try later, please."
            )

        url, post_data = self._get_simple_transition_data()
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(len(response.context['messages']), 1)
        self.assertEqual(
            str(response.context['messages']._loaded_messages[0]),
            "Unable to generate document - try later, please.",
        )


@override_settings(ASSETS_TRANSITIONS=ASSETS_TRANSITIONS)
class TestTransition(TestCase):
    """
    Test transition assign and unassign fields.
    """

    def setUp(self):
        self.client = login_as_su()
        self._prepare_users()
        self._prepare_warehouse()

    def _prepare_warehouse(self):
        self.warehouse = WarehouseFactory()

    def _prepare_users(self):
        self.user = UserFactory()
        self.owner = UserFactory()

    def _prepare_assets(self, custom_values={}):
        self.assets = [BOAssetFactory(**custom_values) for _ in xrange(2)]

    def _prepare_transition_assign(self):
        self.transition = TransitionFactory(**{
            'name': 'release-asset',
            'slug': 'release-asset',
        })
        actions = Action.objects.filter(name__in=[
            'assign_user',
            'assign_owner',
            'assign_loan_end_date',
            'assign_warehouse',
            'change_status',
        ])
        self.transition.actions.add(*actions)

    def _prepare_transition_unassign(self):
        self.transition = TransitionFactory(**{
            'name': 'return-asset',
            'slug': 'return-asset',
        })
        actions = Action.objects.filter(name__in=[
            'unassign_user',
            'unassign_owner',
            'unassign_loan_end_date',
            'unassign_licences',
        ])
        self.transition.actions.add(*actions)

    def _assign_licence_to_assets(self):
        for asset in self.assets:
            asset.licence_set.add(LicenceFactory())

    def _base_test_transition_form_assign(self, url_params, post_params):
        url_base = reverse('transition', args=('back_office',))

        url = "{}?{}".format(
            url_base, urllib.urlencode(url_params, doseq=True)
        )
        response = self.client.post(url, post_params, follow=True)
        self.assertEqual(response.status_code, 200)

    def test_transition_form_assign(self):
        self._prepare_assets()
        self._prepare_transition_assign()
        asset_ids = Asset.objects.values_list('id', flat=True)
        url_params = {'select': asset_ids, 'transition_type': 'release-asset'}
        post_params = {
            'user': self.user.id,
            'warehouse': self.warehouse.id,
            'loan_end_date': date.today().strftime('%Y-%m-%d'),
        }
        self._base_test_transition_form_assign(url_params, post_params)
        self.assertEqual(
            Asset.objects.values(
                'warehouse', 'status', 'user', 'loan_end_date',
            ).distinct().count(),
            1,
        )

    def test_transition_form_unassign(self):
        self._prepare_assets({'user': self.user})
        self._prepare_transition_unassign()
        self._assign_licence_to_assets()
        asset_ids = Asset.objects.values_list('id', flat=True)
        url_params = {'select': asset_ids, 'transition_type': 'return-asset'}
        self._base_test_transition_form_assign(url_params, {})
        self.assertEqual(
            Asset.objects.values(
                'user', 'owner', 'loan_end_date', 'licence',
            ).distinct().count(),
            1,
        )

    def test_transition_history_file(self):
        self._prepare_assets()
        self._prepare_transition_unassign()
        history_id = TransitionsHistoryFactory(
            **{'transition': self.transition}
        ).id
        url = reverse('transition_history_file', args=(history_id,))
        response = self.client.get(url)
        self.assertEqual(response.get('Content-Type'), 'application/pdf')

        not_found_url = reverse('transition_history_file', args=(666,))
        response = self.client.get(not_found_url)
        self.assertEqual(response.status_code, 404)

    def test_transition_history_file_not_found_in_disk(self):
        self._prepare_assets()
        self._prepare_transition_unassign()
        transition_history = TransitionsHistoryFactory(
            **{'transition': self.transition}
        )
        transition_history.report_file = None
        transition_history.save()
        url = reverse('transition_history_file', args=(transition_history.id,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
