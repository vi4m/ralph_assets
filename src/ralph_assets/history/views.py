# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from django.db.models.fields import FieldDoesNotExist

from ralph_assets.history.models import History
from ralph_assets.views.base import AssetsBase, ContentTypeMixin, PaginateMixin
from ralph_assets.models_assets import ASSET_TYPE2MODE


class HistoryBase(AssetsBase):
    @property
    def active_submodule(self):
        if str(self.content_type) == 'asset':
            return 'hardware'
        mapper = {
            'licence': 'licences',
            'support': 'supports',
        }
        return mapper[str(self.content_type)]

    def get_context_data(self, **kwargs):
        context = super(HistoryBase, self).get_context_data(**kwargs)
        obj = self.content_type.get_object_for_this_type(id=self.object_id)
        mode = getattr(obj, 'type', None)
        if mode:
            sidebars = context['active_menu'].get_sidebar_items()
            context.update({
                'sidebar': sidebars['hardware_{}'.format(
                    ASSET_TYPE2MODE[mode])
                ],
            })
        return context


class HistoryListForModel(PaginateMixin, ContentTypeMixin, HistoryBase):
    """View for history of object."""
    template_name = 'assets/history/history_for_model.html'

    def dispatch(self, request, *args, **kwargs):
        self.status = bool(request.GET.get('status', ''))
        return super(HistoryListForModel, self).dispatch(
            request, *args, **kwargs
        )

    def get_paginate_queryset(self):
        history = History.objects.get_history_for_this_content_type(
            content_type=self.content_type,
            object_id=self.object_id,
        )
        self.show_status_button = True
        try:
            self.model._meta.get_field_by_name('status')
        except FieldDoesNotExist:
            self.show_status_button = False
        if self.status and self.show_status_button:
            history = history.filter(field_name__exact='status')
        return history

    def get_context_data(self, **kwargs):
        context = super(HistoryListForModel, self).get_context_data(**kwargs)
        context.update({
            'status': self.status,
            'show_status_button': self.show_status_button,
        })
        return context
