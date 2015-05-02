#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from django import forms
from django.contrib import admin
from django.contrib.admin.filters import SimpleListFilter
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from lck.django.common.admin import ModelAdmin

from ralph import middleware
from ralph_assets import models_assets
from ralph_assets import models_assets as models
from ralph_assets.models import (
    DCAsset, BOAsset,
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
from ralph_assets.models_dc_assets import Accessory
from ralph_assets.models_util import ImportProblem
from ralph_assets.licences.models import LicenceType, SoftwareCategory
from ralph_assets.models_support import Support, SupportType




import re
import logging

from django import forms
from django.conf import settings
from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from lck.django.common.admin import (
    ForeignKeyAutocompleteTabularInline,
    ModelAdmin,
)
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.template.defaultfilters import slugify

# from ralph.business.admin import RolePropertyValueInline
from ralph.ui.forms.network import NetworkForm
from ralph.ui.widgets import ReadOnlyWidget
from django.core.exceptions import ValidationError


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


class AssetRegionFilter(SimpleListFilter):
    """
    Allow to filter assets by region
    """
    title = _('region')
    parameter_name = 'region'

    def lookups(self, request, model_admin):
        return [(r.id, r.name) for r in middleware.get_actual_regions()]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(region_id=self.value())
        else:
            return queryset


class DCAssetAdminForm(forms.ModelForm):
    class Meta:
        model = models_assets.DCAsset

    def __init__(self, *args, **kwargs):
        super(DCAssetAdminForm, self).__init__(*args, **kwargs)
        # return only valid regions for current user
        self.fields['region'].queryset = middleware.get_actual_regions()


class BOAssetAdminForm(forms.ModelForm):
    class Meta:
        model = models_assets.BOAsset

    def __init__(self, *args, **kwargs):
        super(BOAssetAdminForm, self).__init__(*args, **kwargs)
        # return only valid regions for current user
        self.fields['region'].queryset = middleware.get_actual_regions()




class ProcessorInline(ForeignKeyAutocompleteTabularInline):
    model = models.Processor
    # readonly_fields = ('label', 'index', 'speed')
    exclude = ('created', 'modified')
    extra = 0
    related_search_fields = {
        'model': ['^name'],
    }


class MemoryInline(ForeignKeyAutocompleteTabularInline):
    model = models.Memory
    exclude = ('created', 'modified')
    extra = 0
    related_search_fields = {
        'model': ['^name'],
    }


class EthernetInline(ForeignKeyAutocompleteTabularInline):
    model = models.Ethernet
    exclude = ('created', 'modified')
    extra = 0
    related_search_fields = {
        'model': ['^name'],
    }


class StorageInline(ForeignKeyAutocompleteTabularInline):
    model = models.Storage
    readonly_fields = (
        'label',
        'size',
        'sn',
        'model',
        'created',
        'modified',
        'mount_point',
    )
    extra = 0
    related_search_fields = {
        'model': ['^name'],
    }


class InboundConnectionInline(ForeignKeyAutocompleteTabularInline):
    model = models.Connection
    extra = 1
    related_search_fields = {
        'outbound': ['^name']
    }
    fk_name = 'inbound'
    verbose_name = _("Inbound Connection")
    verbose_name_plural = _("Inbound Connections")


class OutboundConnectionInline(ForeignKeyAutocompleteTabularInline):
    model = models.Connection
    extra = 1
    related_search_fields = {
        'inbound': ['^name'],
    }
    fk_name = 'outbound'
    verbose_name = _("Outbound Connection")
    verbose_name_plural = _("Outbound Connections")


# class DeviceAdmin(ModelAdmin):
#     form = DeviceForm
#     inlines = [
#         ProcessorInline,
#         MemoryInline,
#         EthernetInline,
#         StorageInline,
#         IPAddressInline,
#         ChildDeviceInline,
#         RolePropertyValueInline,
#         InboundConnectionInline,
#         OutboundConnectionInline,
#     ]
#     list_display = ('name', 'sn', 'created', 'modified')
#     list_filter = ('model__type',)
#     list_per_page = 250
#     readonly_fields = ('last_seen',)
#     save_on_top = True
#     search_fields = ('name', 'name2', 'sn', 'model__type',
#                      'model__name', 'ethernet__mac')
#     related_search_fields = {
#         'parent': ['^name'],
#         'logical_parent': ['^name'],
#         'venture': ['^name'],
#         'venture_role': ['^name'],
#         'management': ['^address', '^hostname'],
#         'model': ['^name', ],
#     }

#     def get_readonly_fields(self, request, obj=None):
#         ro_fields = super(DeviceAdmin, self).get_readonly_fields(request, obj)
#         if obj and obj.get_asset():
#             ro_fields = ro_fields + ('parent', 'management',)
#         return ro_fields

#     def save_model(self, request, obj, form, change):
#         obj.save(user=request.user, sync_fields=True, priority=SAVE_PRIORITY)

#     def save_formset(self, request, form, formset, change):
#         if formset.model.__name__ == 'RolePropertyValue':
#             for instance in formset.save(commit=False):
#                 instance.save(user=request.user)
#         elif formset.model.__name__ == 'IPAddress':
#             for instance in formset.save(commit=False):
#                 if not instance.id:
#                     # Sometimes IP address exists and does not have any
#                     # assigned device. In this case we should reuse it,
#                     # otherwise we can get IntegrityError.
#                     try:
#                         ip_id = models.IPAddress.objects.filter(
#                             address=instance.address,
#                         ).values_list('id', flat=True)[0]
#                     except IndexError:
#                         pass
#                     else:
#                         instance.id = ip_id
#                 instance.save()
#         else:
#             formset.save(commit=True)

# admin.site.register(models.Device, DeviceAdmin)


class IPAliasInline(admin.TabularInline):
    model = models.IPAlias
    exclude = ('created', 'modified')
    extra = 0




class IPAddressInlineFormset(forms.models.BaseInlineFormSet):

    def get_queryset(self):
        qs = super(IPAddressInlineFormset, self).get_queryset().filter(
            is_management=False,
        )
        return qs


class IPAddressInline(ForeignKeyAutocompleteTabularInline):
    formset = IPAddressInlineFormset
    model = models.IPAddress
    readonly_fields = ('snmp_name', 'last_seen')
    exclude = ('created', 'modified', 'dns_info', 'http_family',
               'snmp_community', 'last_puppet', 'is_management')
    edit_separately = True
    extra = 0
    related_search_fields = {
        'asset': ['^name'],
        'network': ['^name'],
    }

class ChildDCAssetInline(ForeignKeyAutocompleteTabularInline):
    model = models.DCAsset
    edit_separately = True
    readonly_fields = ('hostname', 'model', 'sn', 'remarks', 'last_seen',)
    # exclude = ('name2', 'created', 'modified', 'boot_firmware', 'barcode',
    #            'hard_firmware', 'diag_firmware', 'mgmt_firmware', 'price',
    #            'purchase_date', 'warranty_expiration_date', 'role',
    #            'support_expiration_date', 'deprecation_kind', 'margin_kind',
    #            'chassis_position', 'position', 'support_kind', 'management',
    #            'logical_parent')
    extra = 0
    related_search_fields = {
        'model': ['^name'],
    }
    fk_name = 'parent'



class DCAssetAdmin(ModelAdmin):
    fields = (
        'sn',
        # 'type',
        'model',
        'status',
        'warehouse',
        'region',
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
    inlines = [
        ProcessorInline,
        MemoryInline,
        EthernetInline,
        StorageInline,
        IPAddressInline,
        ChildDCAssetInline,
        # RolePropertyValueInline,
        InboundConnectionInline,
        OutboundConnectionInline,
    ]
    search_fields = (
        'sn',
        'barcode',
    )
    list_display = ('sn', 'model','barcode', 'status', 'deleted',)
    list_filter = (AssetRegionFilter,)
    form = DCAssetAdminForm

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(DCAsset, DCAssetAdmin)


class BOAssetAdmin(ModelAdmin):
    fields = (
        'sn',
        # 'type',
        'model',
        'status',
        'warehouse',
        'region',
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

        'license_key',
        'coa_number',
        'coa_oem_os',
        'imei',
        'purpose'
    )

    search_fields = (
        'sn',
        'barcode',
    )
    list_display = ('sn', 'model', 'barcode', 'status', 'deleted',)
    list_filter = (AssetRegionFilter,)
    form = BOAssetAdminForm

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(BOAsset, BOAssetAdmin)


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


def _greater_than_zero_validation(value):
    if value <= 0:
        raise forms.ValidationError(_(
            'Please specify value greater than zero.',
        ))


class DataCenterForm(forms.ModelForm):

    class Meta:
        model = models_assets.DataCenter

    def clean_visualization_cols_num(self):
        data = self.cleaned_data['visualization_cols_num']
        _greater_than_zero_validation(data)
        return data

    def clean_visualization_rows_num(self):
        data = self.cleaned_data['visualization_rows_num']
        _greater_than_zero_validation(data)
        return data


class DataCenterAdmin(ModelAdmin):
    form = DataCenterForm
    save_on_top = True
    list_display = ('name', 'visualization_cols_num', 'visualization_rows_num')
    search_fields = ('name',)
    fieldsets = (
        (None, {
            'fields': ('name',),
        }),
        (_('Visualization'), {
            'fields': ('visualization_cols_num', 'visualization_rows_num'),
        }),
    )


admin.site.register(models_assets.DataCenter, DataCenterAdmin)


class ServerRoomAdmin(ModelAdmin):
    save_on_top = True
    list_display = ('name', 'data_center')
    search_fields = ('name', 'data_center__name')


admin.site.register(models_assets.ServerRoom, ServerRoomAdmin)


class RackForm(forms.ModelForm):

    class Meta:
        model = models_assets.Rack

    def clean_visualization_col(self):
        data = self.cleaned_data['visualization_col']
        _greater_than_zero_validation(data)
        return data

    def clean_visualization_row(self):
        data = self.cleaned_data['visualization_row']
        _greater_than_zero_validation(data)
        return data

    def clean(self):
        cleaned_data = super(RackForm, self).clean()
        data_center = cleaned_data.get('data_center')
        visualization_col = cleaned_data.get('visualization_col')
        visualization_row = cleaned_data.get('visualization_row')
        if not data_center or not visualization_col or not visualization_row:
            return cleaned_data
        # Check collisions.
        qs = models_assets.Rack.objects.filter(
            data_center=data_center,
            visualization_col=visualization_col,
            visualization_row=visualization_row,
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        collided_racks = qs.values_list('name', flat=True)
        if collided_racks:
            raise forms.ValidationError(
                _('Selected possition collides with racks: %(racks)s.') % {
                    'racks': ' ,'.join(collided_racks),
                },
            )
        # Check dimensions.
        if data_center.visualization_cols_num < visualization_col:
            raise forms.ValidationError(
                _(
                    'Maximum allowed column number for selected data center '
                    'is %(cols_num)d.'
                ) % {
                    'cols_num': data_center.visualization_cols_num,
                },
            )
        if data_center.visualization_rows_num < visualization_row:
            raise forms.ValidationError(
                _(
                    'Maximum allowed row number for selected data center '
                    'is %(rows_num)d.'
                ) % {
                    'rows_num': data_center.visualization_rows_num,
                },
            )
        return cleaned_data


class AccessoryInline(admin.TabularInline):
    fields = ('accessory', 'position', 'remarks', 'orientation')
    model = models_assets.Rack.accessories.through
    extra = 1


class RackAdmin(ModelAdmin):
    form = RackForm
    save_on_top = True
    #raw_id_fields = ('deprecated_ralph_rack',)
    list_display = ('name', 'data_center', 'server_room', 'max_u_height',)
    search_fields = (
        'name', 'data_center__name', 'server_room__name', 'max_u_height',
    )
    fieldsets = (
        (None, {
            'fields': (
                'name', 'data_center', 'server_room', 'max_u_height',

            ),
        }),
        (_('Visualization'), {
            'fields': (
                'visualization_col', 'visualization_row', 'orientation'
            ),
        }),
    )
    inlines = [
        AccessoryInline,
    ]


admin.site.register(models_assets.Rack, RackAdmin)


class AccessoryAdmin(ModelAdmin):
    save_on_top = True
    list_display = ('name',)
    search_fields = ('name',)

admin.site.register(Accessory, AccessoryAdmin)


# models from core ------------------------------------


SAVE_PRIORITY = 215
HOSTS_NAMING_TEMPLATE_REGEX = re.compile(r'<[0-9]+,[0-9]+>.*\.[a-zA-Z0-9]+')


def copy_network(modeladmin, request, queryset):
    for net in queryset:
        name = 'Copy of %s' % net.name
        address = net.address.rsplit('/', 1)[0] + '/1'
        new_net = models.Network(
            name=name,
            address=address,
            gateway=net.gateway,
            kind=net.kind,
            data_center=net.data_center,
        )
        try:
            new_net.save()
        except ValidationError:
            messages.error(request, "Network %s already exists." % address)
        except Exception:
            message = "Failed to create %s." % address
            messages.error(request, message)
            logging.exception(message)
        else:
            new_net.terminators = net.terminators.all()
            new_net.save()

copy_network.short_description = "Copy network"


class NetworkAdmin(ModelAdmin):

    def address(self):
        return self.address

    address.short_description = _("network address")
    address.admin_order_field = 'min_ip'

    def gateway(self):
        return self.gateway

    gateway.short_description = _("gateway address")
    gateway.admin_order_field = 'gateway_as_int'

    def terms(self):
        return ", ".join([n.name for n in self.terminators.order_by('name')])

    terms.short_description = _("network terminators")

    list_display = ('name', 'vlan', address, gateway, terms, 'data_center',
                    'environment', 'kind')

    list_filter = (
        'data_center', 'terminators', 'environment', 'kind', 'dhcp_broadcast',
    )
    list_per_page = 250
    radio_fields = {
        'data_center': admin.HORIZONTAL,
        'environment': admin.HORIZONTAL,
        'kind': admin.HORIZONTAL,
    }
    search_fields = ('name', 'address', 'vlan')
    # FIXME: dnsedit
    filter_horizontal = ('terminators', 'racks') #, 'custom_dns_servers')
    save_on_top = True
    form = NetworkForm
    actions = [copy_network]

admin.site.register(models.Network, NetworkAdmin)


class NetworkKindAdmin(ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

admin.site.register(models.NetworkKind, NetworkKindAdmin)


class NetworkTerminatorAdmin(ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

admin.site.register(models.NetworkTerminator, NetworkTerminatorAdmin)


class EnvironmentAdminForm(forms.ModelForm):

    class Meta:
        model = models.Environment

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if slugify(name) != name.lower():
            raise forms.ValidationError(
                _('You can use only this characters: [a-zA-Z0-9_-]')
            )
        return name

    def clean_hosts_naming_template(self):
        template = self.cleaned_data['hosts_naming_template']
        if re.search("[^a-z0-9<>,\.|-]", template):
            raise forms.ValidationError(
                _("Please remove disallowed characters."),
            )
        for part in template.split("|"):
            if not HOSTS_NAMING_TEMPLATE_REGEX.search(part):
                raise forms.ValidationError(
                    _(
                        "Incorrect template structure. Please see example "
                        "below.",
                    ),
                )
        return template


class EnvironmentAdmin(ModelAdmin):
    list_display = (
        'name',
        'data_center',
        'queue',
        'domain',
        'hosts_naming_template',
        'next_server'
    )
    search_fields = ('name',)
    form = EnvironmentAdminForm
    list_filter = ('data_center', 'queue')

admin.site.register(models.Environment, EnvironmentAdmin)


class DiscoveryQueueAdmin(ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

admin.site.register(models.DiscoveryQueue, DiscoveryQueueAdmin)







# class DeviceModelAdmin(ModelAdmin):

#     def count(self):
#         return models.Device.objects.filter(model=self).count()

#     list_display = ('name', 'type', count, 'created', 'modified')
#     list_filter = ('type',)
#     search_fields = ('name',)

# admin.site.register(models.DeviceModel, DeviceModelAdmin)


# class DeviceModelInline(admin.TabularInline):
#     model = models.DeviceModel
#     exclude = ('created', 'modified')
#     extra = 0


# class DeviceForm(forms.ModelForm):

#     class Meta:
#         model = models.Device

#     def __init__(self, *args, **kwargs):
#         super(DeviceForm, self).__init__(*args, **kwargs)
#         if self.instance.id is not None:
#             asset = self.instance.get_asset()
#             if asset:
#                 self.fields['dc'].widget = ReadOnlyWidget()
#                 self.fields['rack'].widget = ReadOnlyWidget()
#                 self.fields['chassis_position'].widget = ReadOnlyWidget()
#                 self.fields['position'].widget = ReadOnlyWidget()

#     def clean_sn(self):
#         sn = self.cleaned_data['sn']
#         if not sn:
#             sn = None
#         return sn

#     def clean_model(self):
#         model = self.cleaned_data['model']
#         if not model:
#             raise forms.ValidationError(_("Model is required"))
#         return model

#     def clean_barcode(self):
#         barcode = self.cleaned_data['barcode']
#         return barcode or None

#     def clean(self):
#         cleaned_data = super(DeviceForm, self).clean()
#         model = self.cleaned_data.get('model')
#         if all((
#             'ralph_assets' in settings.INSTALLED_APPS,
#             not self.instance.id,  # only when we create new device
#             model
#         )):
#             if model and model.type not in models.ASSET_NOT_REQUIRED:
#                 raise forms.ValidationError(
#                     "Adding this type of devices is allowed only via "
#                     "Assets module."
#                 )
#         return cleaned_data


class IPAddressForm(forms.ModelForm):

    class Meta:
        model = models.IPAddress

    def clean(self):
        cleaned_data = super(IPAddressForm, self).clean()
        device = cleaned_data.get('asset')
        if device and (
            'asset' in self.changed_data or
            'is_management' in self.changed_data
        ):
            is_management = cleaned_data.get('is_management', False)
            if is_management and device.management_ip:
                msg = 'This asset already has management IP.'
                self._errors['asset'] = self.error_class([msg])
        return cleaned_data


class IPAddressAdmin(ModelAdmin):
    form = IPAddressForm
    inlines = [IPAliasInline]

    def ip_address(self):
        """Used for proper ordering."""
        return self.address
    ip_address.short_description = _("IP address")
    ip_address.admin_order_field = 'number'

    list_display = (
        ip_address, 'hostname', 'asset', 'snmp_name', 'is_public', 'created',
        'modified',
    )
    list_filter = ('is_public', 'snmp_community')
    list_per_page = 250
    save_on_top = True
    search_fields = ('address', 'hostname', 'number', 'snmp_name')
    related_search_fields = {
        'asset': ['^name'],
        'network': ['^name'],
        # FIXME:
        # 'venture': ['^name'],
    }

admin.site.register(models.IPAddress, IPAddressAdmin)



class LoadBalancerTypeAdmin(ModelAdmin):
    pass

admin.site.register(
    models.LoadBalancerType,
    LoadBalancerTypeAdmin,
)


class LoadBalancerVirtualServerAdmin(ModelAdmin):
    related_search_fields = {
        'asset': ['^name'],
    }

admin.site.register(
    models.LoadBalancerVirtualServer,
    LoadBalancerVirtualServerAdmin,
)


class LoadBalancerMemberAdmin(ModelAdmin):
    pass

admin.site.register(
    models.LoadBalancerMember,
    LoadBalancerMemberAdmin,
)


class ComponentModelInline(admin.TabularInline):
    model = models.ComponentModel
    exclude = ('created', 'modified')
    extra = 0


class ComponentModelAdmin(ModelAdmin):

    def count(self):
        return self.get_count()

    list_filter = ('type',)
    list_display = ('name', 'type', count, 'family',)
    search_fields = ('name', 'type', 'group__name', 'family')

admin.site.register(models.ComponentModel, ComponentModelAdmin)


class GenericComponentAdmin(ModelAdmin):
    search_fields = ('label', 'sn', 'model__name')
    list_display = ('label', 'model', 'sn')
    related_search_fields = {
        'asset': ['^hostname'],
        'model': ['^name']
    }

admin.site.register(models.GenericComponent, GenericComponentAdmin)


class DiskShareMountInline(ForeignKeyAutocompleteTabularInline):
    model = models.DiskShareMount
    exclude = ('created', 'modified')
    related_search_fields = {
        'asset': ['^hostname'],
        'address': ['^address'],
    }
    extra = 0


class DiskShareAdmin(ModelAdmin):
    inlines = [DiskShareMountInline]
    search_fields = ('wwn',)
    related_search_fields = {
        'asset': ['^hostname'],
        'model': ['^name']
    }

admin.site.register(models.DiskShare, DiskShareAdmin)


# class HistoryChangeAdmin(ModelAdmin):
#     list_display = ('date', 'user', 'asset', 'component', 'field_name',
#                     'old_value', 'new_value')
#     list_per_page = 250
#     readonly_fields = ('date', 'asset', 'user', 'field_name', 'new_value',
#                        'old_value', 'component')
#     search_fields = ('user__username', 'field_name', 'new_value')

# admin.site.register(models.HistoryChange, HistoryChangeAdmin)


class DeviceEnvironmentAdmin(ModelAdmin):
    save_on_top = True
    list_display = ('name',)
    search_fields = ('name',)


admin.site.register(models.DeviceEnvironment, DeviceEnvironmentAdmin)


class DatabaseTypeAdmin(ModelAdmin):
    pass

admin.site.register(
    models.DatabaseType,
    DatabaseTypeAdmin,
)


class DatabaseAdmin(ModelAdmin):
    list_filter = ('database_type__name',)
    list_display = ('name', 'service', 'device_environment', 'database_type')
    search_fields = ('name', 'service')
    related_search_fields = {
        'parent_device': ['^name'],
    }

admin.site.register(
    models.Database,
    DatabaseAdmin,
)
