# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import json

from bob.data_table import DataTableColumn
from bob.views.bulk_edit import BulkEditBase as BobBulkEditBase

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView

from ralph.discovery.models_device import Device
from ralph.ui.views.common import MenuMixin
from ralph.account.models import Perm, ralph_permission
from ralph_assets import forms as assets_forms
from ralph_assets.app import Assets as app
from ralph_assets.models_assets import AssetType
from ralph_assets.models import Asset
from ralph_assets.forms import OfficeForm

MAX_PAGE_SIZE = 65535
HISTORY_PAGE_SIZE = 25

logger = logging.getLogger(__name__)


def get_return_link(mode):
    return "/assets/%s/" % mode


class ACLGateway(object):
    """
    Assets module class which mainly checks user access to page.
    """
    perms = [
        {
            'perm': Perm.has_assets_access,
            'msg': _("You don't have permission to see Assets."),
        },
    ]

    @ralph_permission(perms)
    def dispatch(self, request, *args, **kwargs):
        return super(ACLGateway, self).dispatch(request, *args, **kwargs)


class AssetsBase(ACLGateway, MenuMixin, TemplateView):
    module_name = app.module_name
    columns = []
    status = ''
    section = None
    mode = None
    detect_changes = False
    template_name = "assets/base.html"

    def dispatch(self, request, mode=None, *args, **kwargs):
        self.request = request
        self.set_mode(mode)
        self.set_asset_objects(mode)
        return super(AssetsBase, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        context = super(AssetsBase, self).get_context_data(**kwargs)
        context.update({
            'asset_reports_enable': settings.ASSETS_REPORTS['ENABLE'],
            'columns': self.columns,
            'columns': object(),
            'details': self.kwargs.get('details', 'info'),
            'mode': self.mode,
            'multivalues_fields': ['sn', 'barcode', 'imei'],
            'search_url': reverse('search', args=[
                self.kwargs.get('details', 'info'), ''
            ]),
        })
        return context

    def set_asset_objects(self, mode):
        if mode == 'dc':
            self.asset_objects = Asset.objects_dc
        elif mode == 'back_office':
            self.asset_objects = Asset.objects_bo

    def set_mode(self, mode):
        self.mode = mode

    def validate_barcodes(self, barcodes):
        """
        Checks if barcodes used in asset form are already linked to any assets.
        """
        if barcodes:
            found = Device.objects.filter(barcode__in=barcodes).all()
            found = Asset.objects.filter(
                device_info__ralph_device_id__in=found,
            ).all()
        else:
            found = []
        return found

    def write_office_info2asset_form(self):
        """
        Writes fields from office_info form to asset form.
        """
        if self.asset.type in AssetType.BO.choices:
            self.office_info_form = OfficeForm(instance=self.asset.office_info)
            fields = ['imei', 'purpose']
            for field in fields:
                if field not in self.asset_form.fields:
                    continue
                self.asset_form.fields[field].initial = (
                    getattr(self.asset.office_info, field, '')
                )

    def form_dispatcher(self, class_name):
        """
        Returns form class depending on view mode ('backoffice' or
        'datacenter') and passed *class_name* arg.

        :param class_name: base class name common for both views BO, DC
        :returns class: form class from *ralph_assets.forms* module
        :rtype class:
        """
        mode_name = (
            'BackOffice' if self.mode == 'back_office' else 'DataCenter'
        )
        form_class_name = "{}{}Form".format(mode_name, class_name)
        try:
            form_class = getattr(assets_forms, form_class_name)
        except AttributeError:
            raise Exception("No form class named: {}".format(form_class_name))
        return form_class


class DataTableColumnAssets(DataTableColumn):
    """
    A container object for all the information about a columns header

    :param foreign_field_name - set if field comes from foreign key
    """

    def __init__(self, header_name, foreign_field_name=None, **kwargs):
        super(DataTableColumnAssets, self).__init__(header_name, **kwargs)
        self.foreign_field_name = foreign_field_name


class BulkEditBase(BobBulkEditBase):
    template_name = 'assets/bulk_edit.html'

    def get_form_bulk(self):
        if not self.form_bulk:
            return self.form_dispatcher('BulkEditAsset')
        else:
            return self.form_bulk

    def get_query_from_request(self, *args, **kwargs):
        if self.request.GET.get('from_query'):
            query = super(
                BulkEditBase, self,
            ).handle_search_data(self.args, self.kwargs)
        else:
            query = Q(pk__in=self.get_items_ids())
        return query


class ActiveSubmoduleByAssetMixin(object):
    model_mapper = {
        'asset': 'hardware',
        'support': 'supports',
        'licence': 'licences',
    }

    @property
    def active_submodule(self):
        name = self.get_object_class().__name__.lower()
        return self.model_mapper[name]

    def get_object_class(self):
        raise NotImplementedError('Please override get_object_class() method '
                                  'in {}.'.format(self.__class__.__name__))


class SubmoduleModeMixin(object):
    @property
    def active_submodule(self):
        return 'hardware'


class HardwareModeMixin(object):
    def get_context_data(self, *args, **kwargs):
        context = super(HardwareModeMixin, self).get_context_data(
            *args, **kwargs
        )
        sidebars = context['active_menu'].get_sidebar_items()
        context.update({
            'sidebar': sidebars['hardware_{}'.format(self.mode)],
        })
        return context


class AjaxMixin(object):
    def dispatch(self, request, *args, **kwargs):
        if not request.is_ajax():
            return HttpResponseBadRequest()
        return super(AjaxMixin, self).dispatch(request, *args, **kwargs)


class JsonResponseMixin(object):
    content_type = 'application/json'

    def render_json_response(self, context_data, status=200):
        content = json.dumps(context_data)
        return HttpResponse(
            content, content_type=self.content_type, status=status
        )


class PaginateMixin(object):
    paginate_queryset = None
    query_variable_name = 'page'

    def get_paginate_queryset(self):
        if not self.paginate_queryset:
            raise Exception(
                'Please specified ``paginate_queryset`` or '
                'override ``get_paginate_queryset`` method.',
            )
        return self.paginate_queryset

    def get_context_data(self, **kwargs):
        context = super(PaginateMixin, self).get_context_data(**kwargs)
        try:
            page = int(self.request.GET.get(self.query_variable_name, 1))
        except ValueError:
            page = 1
        if page == 0:
            page = 1
            page_size = MAX_PAGE_SIZE
        else:
            page_size = HISTORY_PAGE_SIZE
        page_content = Paginator(
            self.get_paginate_queryset(), page_size
        ).page(page)
        context.update({
            'page_content': page_content,
            'query_variable_name': self.query_variable_name,
        })
        return context


class ContentTypeMixin(object):
    """Helper for views. This mixin add model, content_type, object_id,
    content_type_id."""
    content_type_id_kwarg_name = 'content_type'
    object_id_kwarg_name = 'object_id'

    def dispatch(self, request, *args, **kwargs):
        self.content_type_id = kwargs[self.content_type_id_kwarg_name]
        self.content_type = ContentType.objects.get(pk=self.content_type_id)
        self.model = self.content_type.model_class()
        self.object_id = kwargs[self.object_id_kwarg_name]
        return super(ContentTypeMixin, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ContentTypeMixin, self).get_context_data(**kwargs)
        context.update({
            'content_type': self.content_type,
            'content_type_id': self.content_type_id,
            'object_id': self.object_id,
            'content_object': self.model.objects.get(pk=self.object_id),
        })
        return context
