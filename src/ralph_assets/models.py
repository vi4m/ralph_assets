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
from django.db import connection
from django.db.models import Q

from ralph.business.models import Department, PuppetVenture, PuppetVentureRole
from ralph.middleware import get_actual_regions
from ralph_assets.models_assets import *
# (
#     Asset,
#     AssetCategory,
#     AssetCategoryType,
#     AssetManufacturer,
#     AssetModel,
#     AssetOwner,
#     AssetSource,
#     AssetStatus,
#     AssetType,
#     CoaOemOs,
#     DeviceInfo,
#     OfficeInfo,
#     Orientation,
#     PartInfo,
#     ReportOdtSource,
#     ReportOdtSourceLanguage,
#     Service,
#     Warehouse,
#     BudgetInfo,
#     Ethernet, EthernetSpeed
# )
from ralph_assets.licences.models import (
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
from ralph_assets.models_dc_assets import ServerRoom, Rack


RALPH_DATE_FORMAT = '%Y-%m-%d'

from django.core.exceptions import PermissionDenied

from ajax_select import LookupChannel
from django.db import models as db
from django.utils.html import escape

#from ralph.util import presentation
from ralph_assets.models_assets import ServiceCatalog, DeviceEnvironment


class RestrictedLookupChannel(LookupChannel):
    """
    Base lookup returning results only if request user is authenticated.
    """
    def check_auth(self, request):
        """
        Write restriction rules here.
        """
        if not request.user.is_authenticated():
            raise PermissionDenied

    def get_query(self, text, request):
        founds = self.model.objects.filter(
            name__icontains=text
        ).order_by('name')[:10]
        return founds

    def get_result(self, obj):
        return obj.name

    def get_item_url(self, obj):
        return getattr(obj, 'url', None)

    def format_match(self, obj):
        return self.format_item_display(obj)

    def format_item_display(self, obj):
        return '{}'.format(escape(unicode(obj.name)))

    def get_base_objects(self):
        return self.model.objects


class ServiceCatalogLookup(RestrictedLookupChannel):
    model = ServiceCatalog
    #model = DeviceEnvironment


class DeviceEnvironmentLookup(RestrictedLookupChannel):
    model = DeviceEnvironment

    def get_query(self, query, request):
        try:
            service = ServiceCatalog.objects.get(id=query)
        except ServiceCatalog.DoesNotExist:
            envs = ServiceCatalog.objects.none()
        else:
            envs = service.get_environments()
        return envs


class BudgetInfoLookup(RestrictedLookupChannel):
    model = BudgetInfo

    def get_query(self, q, request):
        return BudgetInfo.objects.filter(
            name__icontains=q,
        ).order_by('name')[:10]

    def format_item_display(self, obj):
        return "<span>{name}</span>".format(name=obj.name)


class SoftwareCategoryLookup(RestrictedLookupChannel):
    model = SoftwareCategory

    def get_query(self, q, request):
        return SoftwareCategory.objects.filter(
            name__icontains=q
        ).order_by('name')[:10]


class VentureLookup(RestrictedLookupChannel):
    model = PuppetVenture


class ServerRoomLookup(RestrictedLookupChannel):
    model = ServerRoom

    def get_query(self, pk, request):
        return ServerRoom.objects.filter(
            Q(data_center__pk=pk),
        ).order_by('name')


class RackLookup(RestrictedLookupChannel):
    model = Rack

    def get_query(self, pk, request):
        return Rack.objects.filter(
            Q(server_room__pk=pk)
        ).order_by('name')


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


# class LinkedDeviceNameLookup(DeviceLookup):
#     model = Asset

#     def get_query(self, text, request):
#         matched_devices_ids = Device.objects.values_list(
#             'id', flat=True
#         ).filter(name__icontains=text)
#         query = Q(
#             Q(barcode__icontains=text) |
#             Q(sn__icontains=text)
#             # Q(device_info__ralph_device_id__in=matched_devices_ids)
#         )
#         return self.get_base_objects().filter(query).order_by()[:10]

#     def format_item_display(self, obj):
#         item = super(LinkedDeviceNameLookup, self).format_item_display(obj)
#         try:
#             hostname = obj.linked_device.name
#         except AttributeError:
#             pass
#         else:
#             item += '<span class="device-hostname">{hostname}</span>'.format(
#                 hostname=escape(hostname),
#             )
#         return item


class FreeLicenceLookup(RestrictedLookupChannel):
    """Lookup the licences that have any specimen left."""

    model = Licence
    min_length = 4

    def get_query(self, query, request):
        cursor = connection.cursor()
        raw_sql = """
        SELECT
            ralph_assets_licence.id,
            number_bought - IFNULL(SUM(quantity), 0) as on_stock
        FROM
            ralph_assets_licence
            INNER JOIN ralph_assets_softwarecategory ON (
                ralph_assets_licence.software_category_id =	ralph_assets_softwarecategory.id
            )
            LEFT JOIN (
                SELECT licence_id, quantity FROM ralph_assets_licenceasset
                UNION ALL
                SELECT licence_id, quantity FROM ralph_assets_licenceuser) t ON
                    t.licence_id = ralph_assets_licence.id
        WHERE
            ralph_assets_licence.region_id IN (select uu.id from account_region uu where uu.name in ({region_expression}))
        AND (
            ralph_assets_softwarecategory.name like %s
        OR
            ralph_assets_licence.niw LIKE %s
        )
        GROUP by
            ralph_assets_licence.id
        HAVING
            on_stock > 0
        ORDER BY
            number_bought DESC
        LIMIT 10
        """  # noqa
        regions = [region.name for region in get_actual_regions()]
        region_expression = ', '.join(['%s'] * len(regions))
        raw_sql = raw_sql.format(region_expression=region_expression)
        expression = '%{}%'.format(query)

        args = []
        args.extend(regions)
        args.extend([expression] * 2)
        cursor.execute(raw_sql, args)
        ids = [row[0] for row in cursor.fetchall()]
        results = Licence.objects.filter(id__in=ids)
        return results

    def get_result(self, obj):
        return obj.id

    def format_item_display(self, obj):
        return """
        <span>{name}</span>
        <span class="licence-niw">{niw}</span>
        <span>({free} free)</span>
        """.format(
            name=escape(str(obj)),
            niw=obj.niw,
            free=obj.free,
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

    def get_item_url(self, obj):
        return obj.get_absolute_url()

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
        # FIXME?
        # dev_ids = Device.objects.filter(
            # model__type=DeviceType.unknown,
        # ).values_list('id', flat=True)
        assets = Asset.objects.select_related(
            'model__name',
        ).filter(
            # Q(device_info__ralph_device_id=None) |
            # Q(device_info__ralph_device_id__in=dev_ids),
        )#.filter(part_info=None)

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


class VentureDepartmentLookup(RestrictedLookupChannel):
    model = Department

    def get_query(self, q, request):
        return self.model.objects.filter(
            name__icontains=q).order_by('name')[:10]


def get_edit_url(object_):
    if isinstance(object_, User):
        return reverse(
            'edit_user_relations', kwargs={'username': object_.username},
        )
    else:
        try:
            return object_.get_absolute_url()
        except AttributeError:
            return None


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
    'BOAssetModelLookup',
    'BODeviceLookup',
    'CoaOemOs',
    'DCAssetModelLookup',
    'DCDeviceLookup',
    'DeviceInfo',
    'DeviceLookup',
    'Licence',
    'LicenceType',
    'OfficeInfo',
    'Orientation',
    'PartInfo',
    'ReportOdtSource',
    'ReportOdtSourceLanguage',
    'Service',
    'SoftwareCategory',
    'Transition',
    'TransitionsHistory',
    'Warehouse',
    'Ethernet'
]

# Load signals (hook - don't remove it)
import ralph_assets.models_signals  # noqa
