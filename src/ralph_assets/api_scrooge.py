# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from django.db.models import Q

from ralph_assets.models_assets import Asset, AssetModel, AssetType, Warehouse

logger = logging.getLogger(__name__)


def get_warehouses():
    """Yields dicts describing all warehouses"""
    for warehouse in Warehouse.objects.all():
        yield {
            'warehouse_id': warehouse.id,
            'warehouse_name': warehouse.name,
        }


def get_models():
    for model in AssetModel.objects.filter(
        type__in=AssetType.DC.choices
    ).select_related('manufacturer', 'category'):
        yield {
            'model_id': model.id,
            'name': model.name,
            'manufacturer': (
                model.manufacturer.name if model.manufacturer else None
            ),
            'category': model.category.name if model.category else None,
        }


def get_assets(date):
    """Yields dicts describing all assets"""
    for asset in Asset.objects_dc.filter(
        Q(invoice_date=None) | Q(invoice_date__lte=date),
        part_info=None,
    ).select_related('model', 'device_info'):
        if not asset.device_info_id:
            logger.error('Asset {0} has no device'.format(asset.id))
            continue
        if not asset.service_id:
            logger.error('Asset {0} has no service'.format(asset.id))
            continue
        if not asset.device_environment_id:
            logger.error('Asset {0} has no environment'.format(asset.id))
            continue
        device_info = asset.device_info
        hostname = None
        if device_info:
            ralph_device = device_info.get_ralph_device()
            if ralph_device:
                hostname = ralph_device.name

        yield {
            'asset_id': asset.id,
            'device_id': device_info.ralph_device_id if device_info else None,
            'asset_name': hostname,
            'service_id': asset.service_id,
            'environment_id': asset.device_environment_id,
            'sn': asset.sn,
            'barcode': asset.barcode,
            'warehouse_id': asset.warehouse_id,
            'cores_count': asset.cores_count,
            'power_consumption': asset.model.power_consumption,
            'collocation': asset.model.height_of_device,
            'depreciation_rate': asset.deprecation_rate,
            'is_depreciated': asset.is_deprecated(date=date),
            'price': asset.price,
            'model_id': asset.model_id,
        }
