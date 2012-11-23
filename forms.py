#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from django import forms
from django.utils.translation import ugettext_lazy as _

from ralph.ui.widgets import DateWidget

from assets.models import (
    AssetType, AssetModel, AssetStatus, LicenseTypes, AssetSource, Magazine)


def _all_assets_models():
    yield '', '---------'
    for asset_model in AssetModel.objects.all():
        yield asset_model.id, "%s %s" % (
            asset_model.manufacturer.name,
            asset_model.name,
        )


def _all_magazines():
    yield '', '---------'
    for magazine in Magazine.objects.all():
        yield magazine.id, magazine.name


class BaseAssetForm(forms.Form):
    type = forms.ChoiceField(choices=AssetType(), label=_("Type"))
    model = forms.ChoiceField(choices=_all_assets_models(), label=_("Model"))
    invoice_no = forms.CharField(
        max_length=30, required=False, label=_("Invoice number"))
    order_no = forms.CharField(
        max_length=50, required=False, label=_("Order number"))
    buy_date = forms.DateField(widget=DateWidget, label=_("Buy date"))
    support_period = forms.IntegerField(
        label=_("Support period in months"),
        min_value=0,
    )
    support_type = forms.CharField(label=_("Support type description"))
    support_void_reporting = forms.BooleanField(
        label=_("Support void reporting"),
        initial=True,
    )
    provider = forms.CharField(label=_("Provider"), max_length=100)
    status = forms.ChoiceField(choices=AssetStatus(), label=_("Status"))
    sn = forms.CharField(
        label=_("SN/SNs"),
        widget=forms.widgets.Textarea(attrs={'rows': 25})
    )

    def __init__(self, *args, **kwargs):
        super(BaseAssetForm, self).__init__(*args, **kwargs)
        self.fields['model'].choices = _all_assets_models()


class BaseDeviceAssetForm(BaseAssetForm):
    barcode = forms.CharField(
        label=_("Barcode/Barcodes"),
        required=False,
        widget=forms.widgets.Textarea(attrs={'rows': 25}),
    )
    size = forms.IntegerField(label=_("Size"), min_value=1)
    magazine = forms.ChoiceField(choices=_all_magazines(), label=_("Magazine"))

    def __init__(self, *args, **kwargs):
        super(BaseDeviceAssetForm, self).__init__(*args, **kwargs)
        self.fields['magazine'].choices = _all_magazines()


def _validate_multivalue_data(data):
    error_msg = _("Field can't be empty. Please put the items separated "
                  "by new line or comma.")
    data = data.strip()
    if not data:
        raise forms.ValidationError(error_msg)
    if data.find(" ") > 0:
        raise forms.ValidationError(error_msg)
    if not filter(len, data.split("\n")) and not filter(len, data.split(",")):
        raise forms.ValidationError(error_msg)


class AddPartAssetForm(BaseAssetForm):
    def clean_sn(self):
        data = self.cleaned_data["sn"]
        _validate_multivalue_data(data)
        return data


class AddDeviceAssetForm(BaseDeviceAssetForm):
    def clean_sn(self):
        data = self.cleaned_data["sn"]
        _validate_multivalue_data(data)
        return data

    def clean_barcode(self):
        data = self.cleaned_data["barcode"].strip()
        sn_data = self.cleaned_data.get("sn", "").strip()
        if data:
            if data.find(",") != -1:
                barcodes_count = len(filter(len, data.split(",")))
            else:
                barcodes_count = len(filter(len, data.split("\n")))
            if sn_data.find(",") != -1:
                sn_count = len(filter(len, sn_data.split(",")))
            else:
                sn_count = len(filter(len, sn_data.split("\n")))
            if sn_count != barcodes_count:
                raise forms.ValidationError(_("Barcode list could be empty or "
                                              "must have the same number of "
                                              "items as a SN list."))
        return data


class OfficeAssetForm(forms.Form):
    source = forms.ChoiceField(choices=AssetSource(), label=_("Source"))
    license_key = forms.CharField(
        label=_("License key"),
        max_length=255,
        required=False,
    )
    version = forms.CharField(
        label=_("Version"),
        max_length=50,
        required=False,
    )
    unit_price = forms.DecimalField(
        label=_("Unit price"),
        max_digits=20,
        decimal_places=2,
        initial=0,
    )
    attachment = forms.FileField(label=_("Attachment"), required=False)
    license_type = forms.ChoiceField(
        choices=LicenseTypes(),
        label=_("License type"),
        required=False,
    )
    date_of_last_inventory = forms.DateField(
        widget=DateWidget,
        required=False,
        label=_("Date of last inventory"),
    )
    last_logged_user = forms.CharField(
        label=_("Last logged user"),
        required=False,
        max_length=100,
    )


class EditPartAssetForm(BaseAssetForm, OfficeAssetForm):
    pass


class EditDeviceAssetForm(BaseAssetForm, OfficeAssetForm):
    pass

