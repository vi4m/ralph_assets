# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from django.db.models import Q
from lck.django.common import nested_commit_on_success

from ralph_assets.models import (
    Asset,
    AssetSource,
    AssetStatus,
    DCDeviceLookup,
    AssetLookupFuzzy,
)


class AssetLookup(DCDeviceLookup):
    pass


def get_asset_supports(asset):
    supports = []
    for support in asset.supports.all():
        supports.append({
            'name': support.name,
            'url': support.url,
        })
    return supports


def _create_asset_dict(asset):
    manufacturer_name = ''
    if asset.model.manufacturer:
        manufacturer_name = asset.model.manufacturer.name
    try:
        asset_source = AssetSource.from_id(asset.source).raw
    except ValueError:
        asset_source = None
    return {
        'asset_id': asset.id,
        'device_id': asset.device_info.ralph_device_id,
        'model': asset.model.name,
        'manufacturer': manufacturer_name,
        'source': asset_source,
        'invoice_no': asset.invoice_no,
        'order_no': asset.order_no,
        'invoice_date': asset.invoice_date,
        'sn': asset.sn,
        'barcode': asset.barcode,
        'price': asset.price,
        'support_price': asset.support_price,
        'support_period': asset.support_period,
        'support_type': asset.support_type,
        'support_void_reporting': asset.support_void_reporting,
        'provider': asset.provider,
        'status': AssetStatus.from_id(asset.status).raw,
        'remarks': asset.remarks,
        'niw': asset.niw,
        'warehouse': asset.warehouse.name,
        'request_date': asset.request_date,
        'delivery_date': asset.delivery_date,
        'production_use_date': asset.production_use_date,
        'provider_order_date': asset.provider_order_date,
        'category': asset.model.category.name,
        'slots': asset.slots,
        'price': asset.price,
        'deprecation_rate': asset.deprecation_rate,
        'is_deprecated': asset.is_deprecated(),
        'size': asset.device_info.size,
        'u_level': asset.device_info.u_level,
        'u_height': asset.device_info.u_height,
        'rack': asset.device_info.rack,
        'required_support': asset.required_support,
        'supports': get_asset_supports(asset),
        'url': asset.url,
    }


def get_asset(device_id):
    try:
        asset = Asset.objects.get(device_info__ralph_device_id=device_id)
    except Asset.DoesNotExist:
        return
    return _create_asset_dict(asset)


def get_asset_by_sn_or_barcode(identity):
    try:
        asset = Asset.objects.get(
            Q(sn=identity) | Q(barcode=identity)
        )
    except Asset.DoesNotExist:
        return
    return _create_asset_dict(asset)


def is_asset_assigned(asset_id, exclude_devices=[]):
    return Asset.objects.exclude(
        device_info__ralph_device_id__in=exclude_devices,
    ).filter(
        pk=asset_id,
        device_info__ralph_device_id__gt=0,
    ).exists()


@nested_commit_on_success
def assign_asset(device_id, asset_id=None):
    try:
        previous_asset = Asset.objects.get(
            device_info__ralph_device_id=device_id,
        )
    except Asset.DoesNotExist:
        pass
    else:
        previous_asset.device_info.ralph_device_id = None
        previous_asset.device_info.save()
        previous_asset.save()
    if asset_id:
        try:
            new_asset = Asset.objects.get(pk=asset_id)
        except Asset.DoesNotExist:
            return False
        new_asset.device_info.ralph_device_id = device_id
        new_asset.device_info.save()
        new_asset.save()
    return True


__all__ = [
    'assign_asset',
    'get_asset',
    'is_asset_assigned',
    'AssetLookup',
    'AssetLookupFuzzy',
]
