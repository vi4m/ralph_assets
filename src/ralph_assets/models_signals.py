# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


from django.db.models.signals import post_save
from django.dispatch import receiver

from ralph_assets.models import Asset
#, DeviceInfo


SAVE_PRIORITY = 215


# def _can_not_edit_localization(asset_dev_info):
#     return not Asset.objects.filter(device_info=asset_dev_info).exists()


# def _get_core_parent(asset_dev_info):
#     """
#     Finds parent for connected Ralph device.

#     Returns:
#     Tuple of two values:
#     - parent device (rack or blade system) or None
#     - True if found device is blade system
#     """

#     if (
#         _can_not_edit_localization(asset_dev_info) or
#         not asset_dev_info.rack or
#         not asset_dev_info.rack.deprecated_ralph_rack
#     ):
#         return None, False
#     if (
#         not asset_dev_info.asset.model.category or
#         not asset_dev_info.asset.model.category.is_blade
#     ):
#         return asset_dev_info.rack.deprecated_ralph_rack, False
#     try:
#         device_info = DeviceInfo.objects.filter(
#             asset__model__category__is_blade=False,
#             data_center=asset_dev_info.data_center,
#             server_room=asset_dev_info.server_room,
#             rack=asset_dev_info.rack,
#             position=asset_dev_info.position,
#         )[0]
#     except IndexError:
#         return None, True
#     else:
#         return device_info.get_ralph_device(), True


# def _update_localization(device, asset_dev_info):
#     if _can_not_edit_localization(asset_dev_info):
#         return
#     device_parent, is_blade_system = _get_core_parent(asset_dev_info)
#     if not device_parent:
#         return
#     device.parent = device_parent
#     device.save(priority=SAVE_PRIORITY)
#     # update dc for device_parent
#     if (
#         not asset_dev_info.rack.data_center.deprecated_ralph_dc or
#         is_blade_system
#     ):
#         return
#     data_center = asset_dev_info.rack.data_center.deprecated_ralph_dc
#     device_parent.parent = data_center
#     device_parent.save(priority=SAVE_PRIORITY)


# def _update_cached_localization(device, asset_dev_info):
#     if (
#         asset_dev_info.data_center and
#         asset_dev_info.data_center.deprecated_ralph_dc
#     ):
#         device.dc = asset_dev_info.data_center.deprecated_ralph_dc.sn
#     if (
#         asset_dev_info.rack and
#         asset_dev_info.rack.deprecated_ralph_rack
#     ):
#         device.rack = asset_dev_info.rack.deprecated_ralph_rack.sn
#     device.save(priority=SAVE_PRIORITY)


# def _update_localization_details(device, asset_dev_info):
#     if _can_not_edit_localization(asset_dev_info):
#         return
#     if asset_dev_info.position is not None:
#         device.chassis_position = asset_dev_info.position
#     if asset_dev_info.slot_no is not None:
#         device.position = asset_dev_info.slot_no
#     device.save(priority=SAVE_PRIORITY)


# def update_core_localization(asset_dev_info):
#     """
#     DEPRECATED

#     Synchronize Asset localization with Ralph Core localization - for backward
#     compatibility. In the future, localization will be stored only for Asset.
#     """

#     device = asset_dev_info.get_ralph_device()
#     if not device:
#         return
#     _update_localization(device=device, asset_dev_info=asset_dev_info)
#     _update_cached_localization(device=device, asset_dev_info=asset_dev_info)
#     _update_localization_details(device=device, asset_dev_info=asset_dev_info)


# @receiver(
#     post_save, sender=DeviceInfo, dispatch_uid='assets.deviceinfo.post_save',
# )
# def asset_device_info_post_save(sender, instance, **kwargs):
#     update_core_localization(asset_dev_info=instance)
