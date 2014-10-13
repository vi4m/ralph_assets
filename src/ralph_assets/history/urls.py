# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from django.conf.urls import patterns, url

from ralph_assets.history.views import HistoryListForModel


urlpatterns = patterns(
    '',
    url(
        (r'^(?P<content_type>[-\d]+)/(?P<object_id>[-\d]+)/$'),
        HistoryListForModel.as_view(),
        name='history_for_model',
    ),
)
