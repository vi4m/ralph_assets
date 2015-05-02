# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from urllib import urlencode

from django.core.urlresolvers import reverse
from django.db import transaction

from ralph_assets.models import Asset, DeviceInfo, OfficeInfo, PartInfo


def get_transition_url(transition_type, assets_ids, asset_mode):
    """
    Generates url for transition *transition_type* for assets from list
    assets_ids in mode *asset_mode*.

    :transition_type: transition type, like 'return-asset', 'release-asset',
        etc.
    :assets_ids: list of assets' ids on which transition is executed
    :asset_mode: mode of asset, options are 'dc' or 'back_office'

    :returns: url to transition
    """
    success_url = None
    if transition_type:
        success_url = '?'.join([
            reverse('transition', args=[asset_mode, ]),
            urlencode({
                'select': assets_ids,
                'transition_type': transition_type,
            }, doseq=True),
        ])
    return success_url


def _move_data(src, dst, fields):
    for field in fields:
        if field in src:
            value = src.pop(field)
            dst[field] = value
    return src, dst


def update_management_ip(asset, data):
    """Update the management_ip of a given asset."""
    management_ip = data.get('management_ip')
    asset.management_ip = management_ip

    # ralph_device = asset.get_ralph_device()
    # if management_ip and ralph_device:
        # ralph_device.management_ip = management_ip


@transaction.commit_on_success
def _create_assets(creator_profile, asset_form, additional_form, mode):
    asset_data = {}
    for f_name, f_value in asset_form.cleaned_data.items():
        if f_name not in {
            "barcode", "category", "company", "cost_center",
            "department", "employee_id", "imei", "licences", "manager",
            "management_ip", "sn", "profit_center", "supports", "segment",
        }:
            asset_data[f_name] = f_value
    force_unlink = additional_form.cleaned_data.pop('force_unlink', None)
    sns = asset_form.cleaned_data.get('sn', [])
    barcodes = asset_form.cleaned_data.get('barcode', [])
    imeis = (
        asset_form.cleaned_data.pop('imei')
        if 'imei' in asset_form.cleaned_data else None
    )

    assets_ids = []
    for index in range(len(sns or barcodes)):
        asset_data['sn'] = sns[index] if sns else None
        asset_data['barcode'] = barcodes[index] if barcodes else None
        if imeis:
            additional_form.cleaned_data['imei'] = imeis[index]
        cleaned_additional_info = additional_form.cleaned_data
        if mode == 'dc':
            asset = Asset(created_by=creator_profile, **asset_data)
            device_info = DeviceInfo(**cleaned_additional_info)
            device_info.save(user=creator_profile.user)
            asset.device_info = device_info
            asset.save(user=creator_profile.user, force_unlink=force_unlink)
        elif mode == 'back_office':
            _move_data(asset_data, cleaned_additional_info, ['purpose'])
            asset = Asset(created_by=creator_profile, **asset_data)
            office_info = OfficeInfo()
            office_info.__dict__.update(**cleaned_additional_info)
            office_info.coa_oem_os = cleaned_additional_info['coa_oem_os']
            office_info.save(user=creator_profile.user)
            asset.office_info = office_info
            asset.save(user=creator_profile.user)
        asset.save(force_unlink=force_unlink)
        update_management_ip(asset, asset_form.cleaned_data)
        assets_ids.append(asset.id)
    return assets_ids


@transaction.commit_on_success
def _create_part(creator_profile, asset_data, part_info_data, sn):
    part_info = PartInfo(**part_info_data)
    part_info.save(user=creator_profile.user)
    asset = Asset(
        part_info=part_info,
        sn=sn.strip(),
        created_by=creator_profile,
        **asset_data
    )
    asset.save(user=creator_profile.user)
    return asset.id


@transaction.commit_on_success
def _update_office_info(user, asset, office_info_data):
    if not asset.office_info:
        office_info = OfficeInfo()
    else:
        office_info = asset.office_info
    if 'attachment' in office_info_data:
        if office_info_data['attachment'] is None:
            del office_info_data['attachment']
        elif office_info_data['attachment'] is False:
            office_info_data['attachment'] = None
    office_info.__dict__.update(**office_info_data)
    office_info.save(user=user)
    asset.office_info = office_info
    asset.save(user=user)
    return asset


@transaction.commit_on_success
def _update_device_info(user, asset, device_info_data):
    device_info = asset.device_info
    if not device_info:
        device_info = DeviceInfo()
    for key, value in device_info_data.iteritems():
        setattr(device_info, key, value)
    device_info.save(user=user)
    asset.device_info = device_info
    return asset


@transaction.commit_on_success
def _update_asset(modifier_profile, asset, asset_updated_data):
    if (
        'barcode' not in asset_updated_data or
        not asset_updated_data['barcode']
    ):
        asset_updated_data['barcode'] = None
    asset_updated_data.update({'modified_by': modifier_profile})
    asset.__dict__.update(**asset_updated_data)
    update_management_ip(asset, asset_updated_data)
    return asset


@transaction.commit_on_success
def _update_part_info(user, asset, part_info_data):
    if not asset.part_info:
        part_info = PartInfo()
    else:
        part_info = asset.part_info
    part_info.device = part_info_data.get('device')
    part_info.source_device = part_info_data.get('source_device')
    part_info.barcode_salvaged = part_info_data.get('barcode_salvaged')
    part_info.save(user=user)
    asset.part_info = part_info
    asset.part_info.save(user=user)
    return asset
