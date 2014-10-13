# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from django.core.urlresolvers import resolve, reverse
from django.utils.translation import ugettext_lazy as _

from bob.menu import MenuItem

from ralph.menu import Menu
from ralph_assets.app import Assets as app
from ralph_assets.views.report import ReportViewBase


class AssetMenu(Menu):
    module = MenuItem(
        label=app.disp_name,
        name=app.module_name,
        fugue_icon=app.icon,
        href='/assets/dc/search',
    )

    def __init__(self, *args, **kwargs):
        super(AssetMenu, self).__init__(*args, **kwargs)
        url = self.request.META['PATH_INFO']
        self.mode = resolve(url).kwargs.get('mode', 'dc')

    def get_submodules(self):
        return [
            MenuItem(
                fugue_icon='fugue-computer',
                view_name='asset_search',
                view_kwargs={'mode': self.mode},
                label=_('Hardware'),
                name='hardware',
            ),
            MenuItem(
                fugue_icon='fugue-lifebuoy',
                view_name='support_list',
                label=_('Supports'),
                name='supports',
            ),
            MenuItem(
                fugue_icon='fugue-cheque',
                href=reverse('licence_list'),
                view_name='licence_list',
                label=_('Licences'),
                name='licences',
            ),
            MenuItem(
                fugue_icon='fugue-user-green-female',
                view_name='user_list',
                label=_('User list'),
                name='users',
            ),
            MenuItem(
                fugue_icon='fugue-table',
                view_name='assets_reports',
                label=_('Reports'),
                name='assets_reports',
            ),
            MenuItem(
                fugue_icon='fugue-cheque--plus',
                view_name='xls_upload',
                label=_('XLS/CSV import'),
                name='assets_import',
            ),
        ]

    def get_sidebar_items(self):
        hardware_dc = [
            {
                'label': _('Search'),
                'view_name': 'asset_search',
                'view_kwargs': {'mode': 'dc'},
                'fugue_icon': 'fugue-magnifier',
            },
            {
                'label': _('Add device'),
                'view_name': 'add_device',
                'view_kwargs': {'mode': 'dc'},
                'fugue_icon': 'fugue-block--plus',
            },
            {
                'label': _('Add part'),
                'view_name': 'add_part',
                'view_kwargs': {'mode': 'dc'},
                'fugue_icon': 'fugue-block--plus',
            },
        ]
        hardware_bo = [
            {
                'label': _('Search'),
                'view_name': 'asset_search',
                'view_kwargs': {'mode': 'back_office'},
                'fugue_icon': 'fugue-magnifier',
            },
            {
                'label': _('Add device'),
                'view_name': 'add_device',
                'view_kwargs': {'mode': 'back_office'},
                'fugue_icon': 'fugue-block--plus',
            },
            {
                'label': _('Add part'),
                'view_name': 'add_part',
                'view_kwargs': {'mode': 'back_office'},
                'fugue_icon': 'fugue-block--plus',
            },
        ]
        supports = [
            {
                'label': _('Search'),
                'view_name': 'support_list',
                'fugue_icon': 'fugue-magnifier',
            },
            {
                'label': _('Add support'),
                'view_name': 'add_support',
                'fugue_icon': 'fugue-block--plus',
            },
        ]
        licences = [
            {
                'label': _('Search'),
                'view_name': 'licence_list',
                'fugue_icon': 'fugue-magnifier',
            },
            {
                'label': _('Add licence'),
                'view_name': 'add_licence',
                'fugue_icon': 'fugue-block--plus',
            },
        ]
        reports = [
            {
                'label': report.name,
                'view_name': 'report_detail',
                'view_kwargs': {'mode': 'all', 'slug': report.slug},
                'name': report.name,
                'fugue_icon': 'fugue-table',
            }
            for report in ReportViewBase.reports
        ]
        return {
            'hardware_dc': self.generate_menu_items(hardware_dc),
            'hardware_back_office': self.generate_menu_items(hardware_bo),
            'supports': self.generate_menu_items(supports),
            'licences': self.generate_menu_items(licences),
            'assets_reports': self.generate_menu_items(reports),
        }

menu_class = AssetMenu
