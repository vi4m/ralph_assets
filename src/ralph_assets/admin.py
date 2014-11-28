#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from lck.django.common.admin import ModelAdmin

from ralph_assets import models_assets
from ralph_assets.models import (
    Asset,
    AssetCategory,
    AssetCategoryType,
    AssetManufacturer,
    AssetModel,
    AssetOwner,
    CoaOemOs,
    Licence,
    ReportOdtSource,
    ReportOdtSourceLanguage,
    Service,
    Transition,
    TransitionsHistory,
    get_edit_url,
    Warehouse,
)
from ralph_assets.models_assets import REPORT_LANGUAGES
from ralph_assets.models_util import ImportProblem
from ralph_assets.licences.models import LicenceType, SoftwareCategory
from ralph_assets.models_support import Support, SupportType


class SupportAdmin(ModelAdmin):
    raw_id_fields = ('assets',)
    date_hierarchy = 'date_to'
    exclude = ('attachments',)
    list_display = ('name', 'contract_id',)
    list_filter = ('asset_type', 'status',)
    list_display = (
        'name',
        'contract_id',
        'date_to',
        'asset_type',
        'status',
        'support_type',
        'deleted',
    )


admin.site.register(Support, SupportAdmin)


class SupportTypeAdmin(ModelAdmin):
    search_fields = ('name',)


admin.site.register(SupportType, SupportTypeAdmin)


class SoftwareCategoryAdmin(ModelAdmin):
    search_fields = ('name',)
    list_display = ('name', 'asset_type',)
    list_filter = ('asset_type',)


admin.site.register(SoftwareCategory, SoftwareCategoryAdmin)


class LicenceTypeAdmin(ModelAdmin):
    search_fields = ('name',)


admin.site.register(LicenceType, LicenceTypeAdmin)


class AssetOwnerAdmin(ModelAdmin):
    search_fields = ('name',)


admin.site.register(AssetOwner, AssetOwnerAdmin)


class ImportProblemAdmin(ModelAdmin):
    change_form_template = "assets/import_problem_change_form.html"
    list_filter = ('severity', 'content_type',)
    list_display = ('message', 'object_id', 'severity', 'content_type',)

    def change_view(self, request, object_id, extra_context=None):
        extra_context = extra_context or {}
        problem = get_object_or_404(ImportProblem, pk=object_id)
        extra_context['resource_link'] = get_edit_url(problem.resource)
        return super(ImportProblemAdmin, self).change_view(
            request,
            object_id,
            extra_context,
        )

admin.site.register(ImportProblem, ImportProblemAdmin)


class WarehouseAdmin(ModelAdmin):
    save_on_top = True
    list_display = ('name',)
    search_fields = ('name',)


admin.site.register(Warehouse, WarehouseAdmin)


class BudgetInfoAdmin(ModelAdmin):
    save_on_top = True
    list_display = ('name',)
    search_fields = ('name',)


admin.site.register(models_assets.BudgetInfo, BudgetInfoAdmin)


class AssetAdmin(ModelAdmin):
    fields = (
        'sn',
        'type',
        'model',
        'status',
        'warehouse',
        'source',
        'invoice_no',
        'order_no',
        'price',
        'support_price',
        'support_type',
        'support_period',
        'support_void_reporting',
        'provider',
        'remarks',
        'barcode',
        'request_date',
        'provider_order_date',
        'delivery_date',
        'invoice_date',
        'production_use_date',
        'production_year',
        'deleted',
    )
    search_fields = (
        'sn',
        'barcode',
        'device_info__ralph_device_id',
    )
    list_display = ('sn', 'model', 'type', 'barcode', 'status', 'deleted',)
    list_filter = ('type',)

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Asset, AssetAdmin)


class AssetModelAdmin(ModelAdmin):
    save_on_top = True
    list_display = ('name', 'type', 'category', 'show_assets_count',)
    list_filter = ('type', 'category',)
    search_fields = ('name',)

    def queryset(self, request):
        return AssetModel.objects.annotate(assets_count=Count('assets'))

    def show_assets_count(self, instance):
        return instance.assets_count
    show_assets_count.short_description = _('Assets count')
    show_assets_count.admin_order_field = 'assets_count'


admin.site.register(AssetModel, AssetModelAdmin)


class AssetCategoryAdminForm(forms.ModelForm):
    def clean(self):
        data = self.cleaned_data
        parent = self.cleaned_data.get('parent')
        type = self.cleaned_data.get('type')
        if parent and parent.type != type:
            raise ValidationError(
                _("Parent type must be the same as selected type")
            )
        return data


class AssetCategoryAdmin(ModelAdmin):
    def name(self):
        type = AssetCategoryType.desc_from_id(self.type)
        if self.parent:
            name = '|-- ({}) {}'.format(type, self.name)
        else:
            name = '({}) {}'.format(type, self.name)
        return name
    form = AssetCategoryAdminForm
    save_on_top = True
    list_display = (name, 'parent', 'slug', 'type', 'code',)
    list_filter = ('type', 'is_blade',)
    search_fields = ('name',)
    prepopulated_fields = {"slug": ("type", "parent", "name",)}


admin.site.register(AssetCategory, AssetCategoryAdmin)


class AssetManufacturerAdmin(ModelAdmin):
    save_on_top = True
    list_display = ('name',)
    search_fields = ('name',)


admin.site.register(AssetManufacturer, AssetManufacturerAdmin)


class ReportOdtSourceLanguageInline(admin.TabularInline):
    model = ReportOdtSourceLanguage
    extra = 0
    max_num = len(REPORT_LANGUAGES['choices'])
    fields = ('template', 'language',)


class ReportOdtSourceAdmin(ModelAdmin):
    save_on_top = True
    search_fields = ('name', 'slug',)
    list_display = ('name', 'slug',)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [
        ReportOdtSourceLanguageInline,
    ]


admin.site.register(ReportOdtSource, ReportOdtSourceAdmin)


class TransitionAdmin(ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ('actions',)
    list_filter = ('from_status', 'to_status', 'required_report',)
    list_display = (
        'name', 'slug', 'from_status', 'to_status', 'required_report',
    )


admin.site.register(Transition, TransitionAdmin)


class TransitionsHistoryAdmin(ModelAdmin):
    list_display = ('transition', 'logged_user', 'affected_user', 'created',)
    readonly_fields = (
        'transition', 'assets', 'logged_user', 'affected_user', 'report_file',
    )

    def has_add_permission(self, request):
        return False


admin.site.register(TransitionsHistory, TransitionsHistoryAdmin)


class CoaOemOsAdmin(ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


admin.site.register(CoaOemOs, CoaOemOsAdmin)


class ServiceAdmin(ModelAdmin):
    list_display = ('name', 'profit_center', 'cost_center',)
    search_fields = ('name', 'profit_center', 'cost_center',)


admin.site.register(Service, ServiceAdmin)


class LicenceAdmin(ModelAdmin):
    def name(self):
        return self.__unicode__()

    raw_id_fields = (
        'assets',
        'attachments',
        'manufacturer',
        'parent',
        'property_of',
        'software_category',
        'users',
    )
    search_fields = (
        'software_category__name', 'manufacturer__name', 'sn', 'niw',
    )
    list_display = (
        name, 'licence_type', 'number_bought', 'niw', 'asset_type', 'provider',
    )
    list_filter = ('licence_type', 'asset_type', 'budget_info', 'provider',)


admin.site.register(Licence, LicenceAdmin)


class DataCenterAdmin(ModelAdmin):
    save_on_top = True
    list_display = ('name',)
    search_fields = ('name',)


admin.site.register(models_assets.DataCenter, DataCenterAdmin)


class ServerRoomAdmin(ModelAdmin):
    save_on_top = True
    list_display = ('name', 'data_center')
    search_fields = ('name', 'data_center')


admin.site.register(models_assets.ServerRoom, ServerRoomAdmin)


class RackAdmin(ModelAdmin):
    save_on_top = True
    list_display = ('name', 'data_center', 'max_u_height', 'server_room',)
    search_fields = ('name', 'data_center', 'max_u_height', 'server_room',)


admin.site.register(models_assets.Rack, RackAdmin)
