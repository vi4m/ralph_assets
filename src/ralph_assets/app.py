# -*- coding: utf-8 -*-
"""The pluggable app definitions."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from django.core.urlresolvers import reverse

from ralph.app import RalphModule


class Assets(RalphModule):
    """Assets main application."""

    url_prefix = 'assets'
    module_name = 'ralph_assets'
    disp_name = 'Assets'
    icon = 'fugue-box-label'
    default_settings_module = 'ralph_assets.settings'

    @property
    def home_url(self):
        home_url = reverse('asset_search', args=('dc',))
        return home_url

    def __init__(self, **kwargs):
        super(Assets, self).__init__(
            'ralph_assets',
            distribution='ralph_assets',
            **kwargs
        )
        self.append_app()
        self.insert_templates(__file__)
        self.register_logger('ralph_assets', {
            'handlers': ['file'],
            'propagate': True,
            'level': 'DEBUG',
        })
        self.settings['DEFAULT_DEPRECATION_RATE'] = 25
        self.settings['SHOW_RALPH_CORES_DIFF'] = False
