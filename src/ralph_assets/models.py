#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import difflib

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.utils.html import escape
from django.utils.translation import ugettext_lazy as _
from django.db.models import Q

from ralph_assets.models_assets import (
    Asset,
    AssetCategory,
    AssetCategoryType,
    AssetManufacturer,
    AssetModel,
    AssetOwner,
    AssetSource,
    AssetStatus,
    AssetType,
    CoaOemOs,
    DeviceInfo,
    OfficeInfo,
    PartInfo,
    ReportOdtSource,
    Service,
    Warehouse,
)
from ralph_assets.models_sam import (
    Licence,
    LicenceType,
    SoftwareCategory,
)
from ralph_assets.models_support import Support
from ralph_assets.models_transition import (
    Action,
    Transition,
    TransitionsHistory,
)
from ralph.ui.channels import RestrictedLookupChannel
from ralph_assets.models_util import (
    WithForm,
)
from ralph.discovery.models import Device, DeviceType


RALPH_DATE_FORMAT = '%Y-%m-%d'


class DeviceLookup(RestrictedLookupChannel):
    model = Asset

    def get_query(self, q, request):
        query = Q(
            Q(device_info__gt=0) & Q(
                Q(barcode__istartswith=q) |
                Q(sn__istartswith=q) |
                Q(model__name__icontains=q)
            )
        )
        return self.get_base_objects().filter(query).order_by('sn')[:10]

    def get_result(self, obj):
        return obj.id

    def format_item_display(self, obj):
        return """
        <span class="asset-model">{model}</span>
        <span class="asset-barcode">{barcode}</span>
        <span class="asset-sn">{sn}</span>
        """.format(
            model=escape(obj.model),
            barcode=escape(obj.barcode or ''),
            sn=escape(obj.sn),
        )


class LinkedDeviceNameLookup(DeviceLookup):
    model = Asset

    def get_query(self, text, request):
        matched_devices_ids = Device.objects.values_list(
            'id', flat=True
        ).filter(name__icontains=text)
        query = Q(
            Q(barcode__icontains=text)
            | Q(sn__icontains=text)
            | Q(device_info__ralph_device_id__in=matched_devices_ids)
        )
        return self.get_base_objects().filter(query).order_by()[:10]

    def format_item_display(self, obj):
        item = super(LinkedDeviceNameLookup, self).format_item_display(obj)
        try:
            hostname = obj.linked_device.name
        except AttributeError:
            pass
        else:
            item += '<span class="device-hostname">{hostname}</span>'.format(
                hostname=escape(hostname),
            )
        return item


class FreeLicenceLookup(RestrictedLookupChannel):
    """Lookup the licences that have any specimen left."""

    model = Licence

    def get_query(self, query, request):
        expression = '%{}%'.format(query)
        return self.model.objects.raw(
            """SELECT
                ralph_assets_licence.*,
                ralph_assets_softwarecategory.name,
                (
                    COUNT(ralph_assets_licence_assets.asset_id)  +
                    COUNT(ralph_assets_licence_users.user_id)
                ) AS used
            FROM
                ralph_assets_licence
            INNER JOIN ralph_assets_softwarecategory ON (
                ralph_assets_licence.software_category_id =
                ralph_assets_softwarecategory.id
            )
            LEFT JOIN ralph_assets_licence_assets ON (
                ralph_assets_licence.id =
                ralph_assets_licence_assets.licence_id
            )
            LEFT JOIN ralph_assets_licence_users ON (
                ralph_assets_licence.id =
                ralph_assets_licence_users.licence_id
            )
            WHERE
                ralph_assets_softwarecategory.name LIKE %s
            OR
                ralph_assets_licence.niw LIKE %s
            GROUP BY ralph_assets_licence.id
            HAVING used < ralph_assets_licence.number_bought
            LIMIT 10;
            """,
            (expression, expression)
        )

    def get_result(self, obj):
        return obj.id

    def format_item_display(self, obj):
        free = str(obj.number_bought - obj.assets.count() - obj.users.count())
        return """
        <span>{name}</span>
        <span class="licence-niw">{niw}</span>
        <span>({free} free)</span>
        """.format(
            name=escape(str(obj)),
            niw=obj.niw,
            free=free,
        )


class LicenceLookup(RestrictedLookupChannel):
    model = Licence

    def get_query(self, q, request):
        query = Q(software_category__name__icontains=q)
        try:
            number = int(q)
        except ValueError:
            pass
        else:
            query |= Q(number_bought=number)
        return (self.get_base_objects().filter(query)
                .order_by('software_category__name')[:10])

    def get_result(self, obj):
        return obj.id

    def format_item_display(self, obj):
        return """
            <span class="licence-bought">{bought}</span>
            <span class="licence-name">{name}</span>
            <span class="licence-niw">({niw})</span>
        """.format(
            bought=escape(obj.number_bought),
            name=escape(obj.software_category.name or ''),
            niw=escape(obj.niw),
        )


class SupportLookup(RestrictedLookupChannel):
    model = Support

    def get_query(self, q, request):
        query = Q(
            Q(name__istartswith=q) |
            Q(contract_id__istartswith=q)
        )
        return self.get_base_objects().filter(query).order_by('name')[:10]

    def get_result(self, obj):
        return obj.id

    def format_item_display(self, obj):
        return """
            <span class='support-contract_id'>{contract_id}</span>
            <span class='support-name'>{name}</span>
            <span class='support-end'>({expired}: {end})</span>
        """.format(
            contract_id=escape(obj.contract_id),
            name=escape(obj.name),
            expired=_('expired'),
            end=obj.get_natural_end_support(),
        )


class RalphDeviceLookup(RestrictedLookupChannel):
    model = Device

    def get_query(self, q, request):
        query = Q(
            Q(
                Q(barcode__istartswith=q) |
                Q(id__istartswith=q) |
                Q(sn__istartswith=q) |
                Q(model__name__icontains=q)
            )
        )
        return Device.objects.filter(query).order_by('sn')[:10]

    def get_result(self, obj):
        return obj.id

    def format_item_display(self, obj):
        return """
        <span class="asset-model">{model}</span>
        <span class="asset-barcode">{barcode}</span>
        <span class="asset-sn">{sn}</span>
        """.format(
            model=escape(obj.model),
            barcode=escape(obj.barcode or ''),
            sn=escape(obj.sn),
        )


class AssetLookupBase(RestrictedLookupChannel):
    model = Asset

    def get_query(self, q, request):
        return Asset.objects.filter(
            Q(barcode__icontains=q) |
            Q(sn__icontains=q)
        ).order_by('sn', 'barcode')[:10]

    def get_result(self, obj):
        return obj.id

    def format_item_display(self, obj):
        return '{}'.format(escape(unicode(obj)))


class AssetLookup(AssetLookupBase):

    def get_query(self, q, request):
        return Asset.objects.filter(
            Q(model__name__icontains=q) |
            Q(barcode__icontains=q) |
            Q(sn__icontains=q)
        ).order_by('sn', 'barcode')[:10]

    def format_item_display(self, obj):
        return """
        <span class="asset-model">{model}</span>
        <span class="asset-barcode">{barcode}</span>
        <span class="asset-sn">{sn}</span>
        """.format(
            model=escape(obj.model),
            barcode=escape(obj.barcode or ''),
            sn=escape(obj.sn),
        )


class AssetModelLookup(RestrictedLookupChannel):
    model = AssetModel

    def get_query(self, q, request):
        return self.model.objects.filter(
            (
                Q(manufacturer__name__icontains=q) |
                Q(category__name__icontains=q) |
                Q(name__icontains=q)
            ) & Q(type=self.type)
        ).order_by('name')[:10]

    def format_item_display(self, obj):
        manufacturer = getattr(obj, 'manufacturer', None) or '-'
        category = getattr(obj, 'category', None) or '-'
        return """
        <span>{model}</span>
        <span class="auto-complete-blue">({manufacturer})</span>
        <span class="asset-category">({category})</span>
        """.format(
            model=escape(obj.name),
            manufacturer=escape(manufacturer),
            category=escape(category),
        )


class DCAssetModelLookup(AssetModelLookup):
    type = AssetType.data_center


class BOAssetModelLookup(AssetModelLookup):
    type = AssetType.back_office


class ManufacturerLookup(RestrictedLookupChannel):
    model = AssetManufacturer

    def get_query(self, q, request):
        return self.model.objects.filter(Q(name__icontains=q)).order_by(
            'name'
        )[:10]

    def format_item_display(self, obj):
        return "<span>{name}</span>".format(name=obj.name)


class SoftwareCategoryLookup(RestrictedLookupChannel):
    model = SoftwareCategory

    def get_query(self, q, request):
        return SoftwareCategory.objects.filter(
            name__icontains=q
        ).order_by('name')[:10]

    def format_item_display(self, obj):
        return "<span>{name}</span>".format(name=obj.name)


class WarehouseLookup(RestrictedLookupChannel):
    model = Warehouse

    def get_query(self, q, request):
        return Warehouse.objects.filter(
            Q(name__icontains=q)
        ).order_by('name')[:10]

    def get_result(self, obj):
        return obj.id

    def format_item_display(self, obj):
        return escape(obj.name)


class DCDeviceLookup(DeviceLookup):
    def get_base_objects(self):
        return Asset.objects_dc


class BODeviceLookup(DeviceLookup):
    def get_base_objects(self):
        return Asset.objects_bo


class AssetLookupFuzzy(AssetLookupBase):
    def get_query(self, query, request):
        dev_ids = Device.objects.filter(
            model__type=DeviceType.unknown,
        ).values_list('id', flat=True)
        assets = Asset.objects.select_related(
            'model__name',
        ).filter(
            Q(device_info__ralph_device_id=None) |
            Q(device_info__ralph_device_id__in=dev_ids),
        ).filter(part_info=None)

        def comparator(asset):
            seq = "".join(
                [part or '' for part in
                    [
                        asset.sn,
                        asset.barcode,
                        asset.model.name,
                    ]]
            ).replace(" ", "").lower()
            ratio = difflib.SequenceMatcher(
                None,
                seq,
                query.replace(" ", "").lower(),
            ).ratio()
            if ratio:
                return 1 / ratio
            return 999

        assets = sorted(assets, key=comparator)
        return assets[:10]

    def format_match(self, obj):
        ret = obj.__unicode__()
        ret += " - {}".format(obj.invoice_no)
        return ret


class UserLookup(RestrictedLookupChannel):
    model = User

    def get_query(self, q, request):
        try:
            q1, q2 = q.split()
        except ValueError:
            result = User.objects.filter(
                Q(username__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q)
            ).order_by('username')[:10]
        else:
            result = User.objects.filter(
                Q(first_name__icontains=q1, last_name__icontains=q2) |
                Q(first_name__icontains=q2, last_name__icontains=q1)
            )[:10]
        return result

    def get_result(self, obj):
        return obj.id

    def get_item_url(self, obj):
        return reverse('user_view', args=(obj.username,))

    def format_item_display(self, obj):
        return """
        <span>{first_name} {last_name}</span>
        <span class="asset-user-department">{department}</span>
         """.format(
            first_name=obj.first_name,
            last_name=obj.last_name,
            department=obj.profile.department,
        )


def get_edit_url(object_):
    if isinstance(object_, User):
        return reverse(
            'edit_user_relations', kwargs={'username': object_.username},
        )
    elif isinstance(object_, WithForm):
        return object_.url


__all__ = [
    'Action',
    'Asset',
    'AssetCategory',
    'AssetCategoryType',
    'AssetManufacturer',
    'AssetModel',
    'AssetOwner',
    'AssetSource',
    'AssetStatus',
    'AssetType',
    'CoaOemOs',
    'DeviceInfo',
    'Licence',
    'LicenceType',
    'OfficeInfo',
    'PartInfo',
    'ReportOdtSource',
    'Service',
    'SoftwareCategory',
    'Transition',
    'TransitionsHistory',
    'Warehouse',
    'DeviceLookup',
    'DCDeviceLookup',
    'BODeviceLookup',
    'DCAssetModelLookup',
    'BOAssetModelLookup',
]
