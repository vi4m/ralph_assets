# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import re

from rq import get_current_job
from bob.data_table import DataTableMixin

from django.conf import settings
from django.db.models import Q
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _

from ralph.util.reports import Report, set_progress
from ralph.business.models import Venture
from ralph_assets.forms import (
    BackOfficeSearchAssetForm,
    DataCenterSearchAssetForm,
)
from ralph_assets.models import Asset, AssetCategory, PartInfo, OfficeInfo
from ralph_assets.views.base import AssetsBase, DataTableColumnAssets


logger = logging.getLogger(__name__)


QUOTATION_MARKS = re.compile(r"^\".+\"$")
SEARCH_DELIMITERS = re.compile(r";|\|")


class AssetsSearchQueryableMixin(object):

    def handle_search_data(self, *args, **kwargs):
        search_fields = [
            'barcode',
            'budget_info',
            'category',
            'company',
            'cost_center',
            'deleted',
            'department',
            'deprecation_rate',
            'device_environment',
            'device_info',
            'hostname',
            'employee_id',
            'guardian',
            'id',
            'imei',
            'invoice_no',
            'location',
            'manufacturer',
            'model',
            'niw',
            'support_assigned',
            'order_no',
            'owner',
            'part_info',
            'profit_center',
            'provider',
            'purpose',
            'ralph_device_id',
            'remarks',
            'required_support',
            'service',
            'service_name',
            'sn',
            'source',
            'status',
            'task_url',
            'unlinked',
            'user',
            'warehouse',
        ]
        # handle simple 'equals' search fields at once.
        all_q = Q()
        for field in search_fields:
            field_value = self.request.GET.get(field)
            if field_value:
                exact = False
                multi = False
                # if search term is enclosed in "", we want exact matches
                if isinstance(field_value, basestring) and \
                        QUOTATION_MARKS.search(field_value):
                    exact = True
                    field_value = field_value[1:-1]
                elif re.search(SEARCH_DELIMITERS, field_value):
                    multi = True
                if field == 'part_info':
                    if field_value == 'device':
                        all_q &= Q(part_info__isnull=True)
                    elif field_value == 'part':
                        all_q &= Q(part_info__gte=0)
                elif field == 'model':
                    if exact:
                        all_q &= Q(model__name=field_value)
                    else:
                        all_q &= Q(model__name__icontains=field_value)
                elif field == 'category':
                    part = self.get_search_category_part(field_value)
                    if part:
                        all_q &= part
                elif field == 'deleted':
                    if field_value.lower() == 'on':
                        all_q &= Q(deleted__in=(True, False))
                elif field == 'manufacturer':
                    if exact:
                        all_q &= Q(model__manufacturer__name=field_value)
                    else:
                        all_q &= Q(
                            model__manufacturer__name__icontains=field_value
                        )
                elif field == 'barcode':
                    if exact:
                        all_q &= Q(barcode=field_value)
                    elif multi:
                        all_q &= self._search_fields_or(
                            ['barcode'],
                            re.split(SEARCH_DELIMITERS, field_value),
                        )
                    else:
                        all_q &= Q(barcode__contains=field_value)
                elif field == 'hostname':
                    if exact:
                        all_q &= Q(hostname=field_value)
                    elif multi:
                        all_q &= self._search_fields_or(
                            ['hostname'],
                            re.split(SEARCH_DELIMITERS, field_value),
                        )
                    else:
                        all_q &= Q(hostname__contains=field_value)
                elif field == 'sn':
                    if exact:
                        all_q &= Q(sn=field_value)
                    elif multi:
                        all_q &= self._search_fields_or(
                            ['sn'],
                            re.split(SEARCH_DELIMITERS, field_value),
                        )
                    else:
                        all_q &= Q(sn__icontains=field_value)
                elif field == 'niw':
                    if exact:
                        all_q &= Q(niw=field_value)
                    elif multi:
                        all_q &= self._search_fields_or(
                            ['niw'],
                            re.split(SEARCH_DELIMITERS, field_value),
                        )
                    else:
                        all_q &= Q(niw__icontains=field_value)
                elif field == 'provider':
                    if exact:
                        all_q &= Q(provider=field_value)
                    else:
                        all_q &= Q(provider__icontains=field_value)
                elif field == 'order_no':
                    if exact:
                        all_q &= Q(order_no=field_value)
                    else:
                        all_q &= Q(order_no__icontains=field_value)
                elif field == 'invoice_no':
                    if exact:
                        all_q &= Q(invoice_no=field_value)
                    else:
                        all_q &= Q(invoice_no__icontains=field_value)
                elif field == 'warehouse':
                    all_q &= Q(warehouse__id=field_value)
                elif field == 'owner':
                    all_q &= Q(owner__id=field_value)
                elif field == 'location':
                    all_q &= Q(location__icontains=field_value)
                elif field == 'employee_id':
                    all_q &= Q(owner__profile__employee_id=field_value)
                elif field == 'company':
                    all_q &= Q(owner__profile__company__icontains=field_value)
                elif field == 'profit_center':
                    all_q &= Q(owner__profile__profit_center=field_value)
                elif field == 'cost_center':
                    all_q &= Q(owner__profile__cost_center=field_value)
                elif field == 'department':
                    all_q &= Q(
                        owner__profile__department__icontains=field_value
                    )
                elif field == 'remarks':
                    all_q &= Q(remarks__icontains=field_value)
                elif field == 'user':
                    all_q &= Q(user__id=field_value)
                elif field == 'guardian':
                    all_q &= Q(guardian__id=field_value)
                elif field == 'deprecation_rate':
                    deprecation_rate_query_map = {
                        'null': Q(deprecation_rate__isnull=True),
                        'deprecated': Q(deprecation_rate=0),
                        '6': Q(deprecation_rate__gt=0,
                               deprecation_rate__lte=6),
                        '12': Q(deprecation_rate__gt=6,
                                deprecation_rate__lte=12),
                        '24': Q(deprecation_rate__gt=12,
                                deprecation_rate__lte=24),
                        '48': Q(deprecation_rate__gt=24,
                                deprecation_rate__lte=48),
                        '48<': Q(deprecation_rate__gt=48),
                    }
                    all_q &= deprecation_rate_query_map[field_value]
                elif field == 'unlinked' and field_value.lower() == 'on':
                        all_q &= ~Q(device_info=None)
                        all_q &= Q(device_info__ralph_device_id=None)
                elif field == 'ralph_device_id':
                    if exact:
                        all_q &= Q(device_info__ralph_device_id=field_value)
                    else:
                        all_q &= Q(
                            device_info__ralph_device_id__icontains=field_value
                        )
                elif field == 'task_url':
                    if exact:
                        all_q &= Q(task_url=field_value)
                    else:
                        all_q &= Q(task_url__icontains=field_value)
                elif field == 'id':
                        all_q &= Q(
                            id__in=[int(id) for id in field_value.split(",")],
                        )
                elif field == 'imei':
                    if exact:
                        all_q &= Q(office_info__imei=field_value)
                    else:
                        all_q &= Q(office_info__imei__icontains=field_value)
                elif field == 'service_name':
                    all_q &= Q(service_name=field_value)
                elif field == 'required_support':
                    user_choice = True if field_value == 'yes' else False
                    all_q &= Q(required_support=user_choice)
                elif field == 'support_assigned':
                    user_choice = True if field_value == 'none' else False
                    all_q &= Q(supports__isnull=user_choice)
                elif field == 'purpose':
                    all_q &= Q(office_info__purpose=field_value)
                elif field == 'budget_info':
                    if exact:
                        all_q &= Q(budget_info__name=field_value)
                    else:
                        all_q &= Q(budget_info__name__icontains=field_value)
                elif field == 'service':
                    if exact:
                        all_q &= Q(service__name=field_value)
                    else:
                        all_q &= Q(service__name__icontains=field_value)
                elif field == 'device_environment':
                    if exact:
                        all_q &= Q(device_environment__name=field_value)
                    else:
                        all_q &= Q(
                            device_environment__name__icontains=field_value,
                        )
                else:
                    q = Q(**{field: field_value})
                    all_q = all_q & q

        # now fields within ranges.
        search_date_fields = [
            'invoice_date', 'request_date', 'delivery_date',
            'production_use_date', 'provider_order_date', 'loan_end_date',
        ]
        for date in search_date_fields:
            start = self.request.GET.get(date + '_from')
            end = self.request.GET.get(date + '_to')
            if start:
                all_q &= Q(**{date + '__gte': start})
            if end:
                all_q &= Q(**{date + '__lte': end})
        self.items_count = Asset.objects.filter(all_q).count()
        return all_q


class GenericSearch(Report, AssetsBase, DataTableMixin):
    """A generic view that contains a bob grid and a search form"""

    sort_variable_name = 'sort'
    export_variable_name = 'export'
    template_name = 'assets/search.html'

    def get_context_data(self, *args, **kwargs):
        ret = super(GenericSearch, self).get_context_data(*args, **kwargs)
        ret.update(
            super(GenericSearch, self).get_context_data_paginator(
                *args, **kwargs
            )
        )
        ret.update({
            'sort_variable_name': self.sort_variable_name,
            'url_query': self.request.GET,
            'sort': self.sort,
            'columns': self.columns,
            'form': self.form,
            'items_count': self.items_count,
        })
        return ret

    def get(self, request, *args, **kwargs):
        self.form = self.Form(self.request.GET)
        qs = self.handle_search_data(request)
        self.data_table_query(qs)
        if self.export_requested():
            return self.response
        return super(GenericSearch, self).get(request, *args, **kwargs)

    def handle_search_data(self, request):
        query = self.form.get_query()
        query_set = self.Model.objects.filter(query)
        self.items_count = query_set.count()
        return query_set.all()


class _AssetSearch(AssetsSearchQueryableMixin, AssetsBase):

    def set_mode(self, mode):
        self.header = 'Search {} Assets'.format(
            {
                'dc': 'DC',
                'back_office': 'BO',
            }[mode]
        )
        if mode == 'dc':
            self.objects = Asset.objects_dc
            self.admin_objects = Asset.admin_objects_dc
            search_form = DataCenterSearchAssetForm
        elif mode == 'back_office':
            self.objects = Asset.objects_bo
            self.admin_objects = Asset.admin_objects_bo
            search_form = BackOfficeSearchAssetForm
        self.form = search_form(self.request.GET, mode=mode)
        super(_AssetSearch, self).set_mode(mode)

    def get_search_category_part(self, field_value):
        try:
            category_id = field_value
        except ValueError:
            pass
        else:
            category = AssetCategory.objects.get(slug=category_id)
            children = [x.slug for x in category.get_children()]
            categories = [category_id, ] + children
            return Q(model__category_id__in=categories)

    def get_all_items(self, query):
        include_deleted = self.request.GET.get('deleted')
        if include_deleted and include_deleted.lower() == 'on':
            return self.admin_objects.filter(query)
        return self.objects.filter(query)

    def _search_fields_or(self, fields, values):
        q = Q()
        for value in values:
            value = value.strip()
            if not value:
                continue
            for field in fields:
                q |= Q(**{field: value})
        return q


class AssetSearchDataTable(_AssetSearch, DataTableMixin):
    """
        The main-screen search form for all type of assets.
        (version without async reports)
    """
    rows_per_page = 15
    csv_file_name = 'ralph.csv'
    sort_variable_name = 'sort'
    export_variable_name = 'export'
    _ = DataTableColumnAssets
    sidebar_selected = 'search'
    template_name = 'assets/search_asset.html'

    def __init__(self, *args, **kwargs):
        super(AssetSearchDataTable, self).__init__(*args, **kwargs)
        _ = self._
        show_back_office = (self.column_visible, 'back_office')
        show_dc = (self.column_visible, 'dc')
        self.columns = [
            _('Dropdown', selectable=True, bob_tag=True),
            _('Asset id', field='pk', export=True),
            _('Type', bob_tag=True),
            _('Status', field='status', sort_expression='status',
              bob_tag=True, export=True),
            _('Barcode', field='barcode', sort_expression='barcode',
              bob_tag=True, export=True),
            _('Category', field='model__category',
              sort_expression='model__category', bob_tag=True,
              show_conditions=show_back_office, export=True),
            _('Manufacturer', field='model__manufacturer__name',
              sort_expression='model__manufacturer__name',
              bob_tag=True, export=True, show_conditions=show_back_office),
            _('Model', field='model__name', sort_expression='model__name',
              bob_tag=True, export=True),
            _('User', field='user__username', sort_expression='user__username',
              bob_tag=True, export=True, show_conditions=show_back_office),
            _('Warehouse', field='warehouse__name',
              sort_expression='warehouse__name', bob_tag=True, export=True),
            _('SN', field='sn', sort_expression='sn', bob_tag=True,
              export=True),
            _('IMEI', field='office_info__imei',
              sort_expression='office_info__imei', bob_tag=True, export=True,
              show_conditions=show_back_office),
            _('Property of', field='property_of__name',
              sort_expression='property_of__name', bob_tag=True, export=True,
              show_conditions=show_back_office),
            _('Hostname', field='hostname', sort_expression='hostname',
              bob_tag=True, export=True, show_conditions=show_back_office),
            _('Service name', field='service_name__name',
              sort_expression='service_name__name', bob_tag=True, export=True,
              show_conditions=show_back_office),
            _('Invoice date', field='invoice_date',
              sort_expression='invoice_date', bob_tag=True, export=True),
            _('Invoice no.', field='invoice_no', sort_expression='invoice_no',
              bob_tag=True, export=True),
            _('Order no.', field='order_no', sort_expression='order_no',
              bob_tag=True, export=True, show_conditions=show_dc),
            _('Additional remarks', field='remarks',
              sort_expression='remarks', bob_tag=True, export=True,
              show_conditions=show_back_office),
            _('Created', field='created', sort_expression='created',
              bob_tag=True, show_conditions=show_back_office),
            _('Price', field='price', sort_expression='price',
              bob_tag=True, export=True, show_conditions=show_dc),
            _('Venture', field='venture', bob_tag=True, export=True,
              show_conditions=show_dc),
            _('Discovered', bob_tag=True, field='is_discovered', export=True,
              foreign_field_name='is_discovered', show_conditions=show_dc),
            _('Actions', bob_tag=True,
              show_conditions=(
                  lambda show: show, not settings.ASSET_HIDE_ACTION_SEARCH,
              )),
            _('Department', field='department', foreign_field_name='venture',
              export=True),
            _('Barcode salvaged', field='barcode_salvaged',
              foreign_field_name='part_info', export=True),
            _('Source device', field='source_device',
              foreign_field_name='part_info', export=True),
            _('Device', field='device',
              foreign_field_name='part_info', export=True),
            _('Provider', field='provider', export=True),
            _('Remarks', field='remarks', export=True),
            _('Source', field='source', export=True),
            _('Support peroid', field='support_peroid', export=True),
            _('Support type', field='support_type', export=True),
            _('Support void_reporting', field='support_void_reporting',
              export=True),
            _('Inventory number', field='niw', foreign_field_name='',
              export=True),
            _('Ralph ID', field='device_info',
              foreign_field_name='ralph_device_id', export=True),
            _('Type', field='type', export=True),
            _('Deprecation rate', field='deprecation_rate',
              foreign_field_name='', export=True),
        ]

    def column_visible(self, mode):
        return self.mode == mode

    def handle_search_data(self, get_csv=False, *args, **kwargs):
        if self.form.is_valid():
            all_q = super(
                AssetSearchDataTable, self,
            ).handle_search_data(*args, **kwargs)
            queryset = self.get_all_items(all_q)
            self.assets_count = queryset.count() if all_q.children else None
            if get_csv:
                return self.get_csv_data(queryset)
            else:
                self.data_table_query(queryset)
        else:
            queryset = self.objects.none()
            self.assets_count = None
            self.data_table_query(queryset)
            messages.error(self.request, _("Please correct the errors."))

    def get_csv_header(self):
        header = super(AssetSearchDataTable, self).get_csv_header()
        return ['type'] + header

    def get_csv_rows(self, queryset, type, model):
        data = [self.get_csv_header()]
        total = queryset.count()
        processed = 0
        job = get_current_job()
        for asset in queryset:
            row = ['part'] if asset.part_info else ['device']
            for item in self.columns:
                field = item.field
                if field:
                    nested_field_name = item.foreign_field_name
                    if nested_field_name == type:
                        cell = self.get_cell(
                            getattr(asset, type), field, model
                        )
                    elif nested_field_name == 'part_info':
                        cell = self.get_cell(asset.part_info, field, PartInfo)
                    elif nested_field_name == 'venture':
                        cell = self.get_cell(asset.venture, field, Venture)
                    elif nested_field_name == 'is_discovered':
                        cell = unicode(asset.is_discovered)
                    else:
                        cell = self.get_cell(asset, field, Asset)
                    row.append(unicode(cell))
            data.append(row)
            processed += 1
            set_progress(job, processed / total)
        set_progress(job, 1)
        return data

    def get_context_data(self, *args, **kwargs):
        ret = super(
            AssetSearchDataTable, self,
        ).get_context_data(*args, **kwargs)
        ret.update(
            super(AssetSearchDataTable, self).get_context_data_paginator(
                *args,
                **kwargs
            )
        )
        ret.update({
            'form': self.form,
            'header': self.header,
            'sort': self.sort,
            'columns': self.columns,
            'sort_variable_name': self.sort_variable_name,
            'export_variable_name': self.export_variable_name,
            'csv_url': self.request.path_info + '/csv',
            'asset_transitions_enable': settings.ASSETS_TRANSITIONS['ENABLE'],
            'asset_hide_action_search': settings.ASSET_HIDE_ACTION_SEARCH,
            'assets_count': self.assets_count,
        })
        return ret

    def get(self, *args, **kwargs):
        self.handle_search_data()
        if self.export_requested():
            return self.response
        return super(AssetSearchDataTable, self).get(*args, **kwargs)

    def is_async(self, request, *args, **kwargs):
        self.export = request.GET.get('export')
        return self.export == 'csv'

    def get_result(self, request, *args, **kwargs):
        self.set_mode(kwargs['mode'])
        return self.handle_search_data(get_csv=True)

    def get_response(self, request, result):
        return self.make_csv_response(result)

    def get_csv_data(self, queryset):
        return self.get_csv_rows(
            queryset, type='office_info', model=OfficeInfo
        )

    def get_columns_nested(self, mode):
        _ = DataTableColumnAssets
        if mode == 'back_office':
            return [
                _(
                    'Date of last inventory',
                    field='date_of_last_inventory',
                    foreign_field_name='office_info',
                    export=True,
                ),
                _(
                    'Last logged user',
                    field='last_logged_user',
                    foreign_field_name='office_info',
                    export=True,
                ),
                _(
                    'License key',
                    field='license_key',
                    foreign_field_name='office_info',
                    export=True,
                ),
                _(
                    'License type',
                    field='license_type',
                    foreign_field_name='office_info',
                    export=True,
                ),
                _(
                    'Unit price',
                    field='unit_price',
                    foreign_field_name='office_info',
                    export=True,
                ),
                _(
                    'Version',
                    field='version',
                    foreign_field_name='office_info',
                    export=True,
                ),
            ]
        elif mode == 'dc':
            return [
                _(
                    'asset id',
                    field='id',
                    export=True,
                ),
                _(
                    'Ralph device id',
                    field='ralph_device_id',
                    foreign_field_name='device_info',
                    export=True,
                ), _(
                    'Rack',
                    field='rack',
                    foreign_field_name='device_info',
                    export=True,
                ),
                _(
                    'U level',
                    field='u_level',
                    foreign_field_name='device_info',
                    export=True,
                ),
                _(
                    'U height',
                    field='u_height',
                    foreign_field_name='device_info',
                    export=True,
                ),
                _(
                    'modified',
                    field='modified',
                    export=True,
                ),

            ]
