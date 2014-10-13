# -*- coding: utf-8 -*-
"""Forms for SAM module."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from ajax_select.fields import (
    AutoCompleteSelectField,
    AutoCompleteSelectMultipleField,
    AutoCompleteWidget,
)
from collections import OrderedDict
from django import forms
from django.forms import ChoiceField
from django.utils.translation import ugettext_lazy as _
from django_search_forms.form import SearchForm
from django_search_forms.fields import (
    DateRangeSearchField,
    ExactSearchField,
    MultiSearchField,
    RelatedSearchField,
    TextSearchField,
)
from django_search_forms.fields_ajax import (
    RelatedAjaxSearchField,
    AjaxTextSearch,
)

from ralph.ui.widgets import DateWidget
from ralph_assets import models_sam
from ralph_assets.forms import (
    LOOKUPS,
    MultilineField,
    MultivalFieldForm,
    ReadOnlyFieldsMixin,
)
from ralph_assets.models import AssetType
from ralph_assets.models_assets import MODE2ASSET_TYPE
from ralph_assets.models_sam import AssetOwner, LicenceType


class SoftwareCategoryWidget(AutoCompleteWidget):
    """A widget for SoftwareCategoryField."""

    def render(self, name, value, attrs=None):
        if isinstance(value, basestring):
            sc_name = value
        else:
            try:
                sc_name = models_sam.SoftwareCategory.objects.get(
                    pk=value
                ).name
            except models_sam.SoftwareCategory.DoesNotExist:
                sc_name = ''
        return super(
            SoftwareCategoryWidget, self
        ).render(name, sc_name, attrs)


class SoftwareCategoryField(AutoCompleteSelectField):
    """A field that either finds or creates a SoftwareCategory. NOTE:
    these values are *not* saved. The view should save it after validating
    the whole form"""

    def clean(self, value):
        value = super(SoftwareCategoryField, self).clean(value)
        try:
            return models_sam.SoftwareCategory.objects.get(
                name=value)
        except models_sam.SoftwareCategory.DoesNotExist:
            return models_sam.SoftwareCategory(
                name=value
            )


class LicenceForm(forms.ModelForm):
    """Base form for licences."""

    class Meta:
        fieldset = OrderedDict([
            ('Basic info', [
                'asset_type', 'manufacturer', 'licence_type',
                'software_category', 'parent', 'niw', 'sn', 'property_of',
                'valid_thru', 'assets', 'users', 'remarks', 'service_name',
                'license_details',
            ]),
            ('Financial info', [
                'order_no', 'invoice_date', 'invoice_no', 'price', 'provider',
                'number_bought', 'accounting_id', 'budget_info',
            ]),
        ])
        widgets = {
            'invoice_date': DateWidget,
            'license_details': forms.Textarea(attrs={'rows': 3}),
            'remarks': forms.Textarea(attrs={'rows': 3}),
            'sn': forms.Textarea(attrs={'rows': 3}),
            'valid_thru': DateWidget,
        }

    asset_type = ChoiceField(
        required=True,
        choices=[('', '----')] + [
            (choice.id, choice.name) for choice in [
                AssetType.back_office, AssetType.data_center
            ]
        ],
    )
    parent = AutoCompleteSelectField(
        ('ralph_assets.models', 'LicenceLookup'),
        required=False,
        label=_('Parent licence'),
    )
    software_category = SoftwareCategoryField(
        ('ralph_assets.models', 'SoftwareCategoryLookup'),
        widget=SoftwareCategoryWidget,
        plugin_options=dict(
            add_link='/admin/ralph_assets/softwarecategory/add/?name=',
        )
    )
    manufacturer = AutoCompleteSelectField(
        ('ralph_assets.models', 'ManufacturerLookup'),
        widget=AutoCompleteWidget,
        plugin_options=dict(
            add_link='/admin/ralph_assets/assetmanufacturer/add/',
        ),
        required=False,
    )
    budget_info = AutoCompleteSelectField(
        LOOKUPS['budget_info'],
        required=False,
        plugin_options=dict(
            add_link='/admin/ralph_assets/budgetinfo/add/',
        )
    )
    assets = AutoCompleteSelectMultipleField(
        LOOKUPS['linked_device'], required=False, label=_('Assigned Assets')
    )
    users = AutoCompleteSelectMultipleField(
        LOOKUPS['asset_user'], required=False, label=_('Assigned Users')
    )

    def __init__(self, mode, *args, **kwargs):
        self.mode = mode
        super(LicenceForm, self).__init__(*args, **kwargs)

    def clean(self, *args, **kwargs):
        result = super(LicenceForm, self).clean(*args, **kwargs)
        if len(result.get('assets', [])) > result.get('number_bought'):
            raise forms.ValidationError(_(
                "You don't have sufficient licences!"
            ))
        if 'software_category' not in result:
            return result
        if result['software_category'].asset_type is None:
            result['software_category'].asset_type = MODE2ASSET_TYPE[self.mode]
        if result['software_category'].pk is None:
            result['software_category'].save()
        return result


class AddLicenceForm(LicenceForm, MultivalFieldForm):
    """Class for adding a licence or multiple licences."""

    multival_fields = ['sn', 'niw']
    allow_duplicates = ['sn']

    class Meta(LicenceForm.Meta):
        model = models_sam.Licence
        fields = (
            'accounting_id',
            'asset_type',
            'budget_info',
            'invoice_date',
            'invoice_no',
            'licence_type',
            'license_details',
            'manufacturer',
            'niw',
            'number_bought',
            'order_no',
            'parent',
            'price',
            'property_of',
            'provider',
            'remarks',
            'service_name',
            'sn',
            'software_category',
            'valid_thru',
        )

    sn = MultilineField(
        db_field_path='sn',
        reject_duplicates=False,
        label=_('Licence key'),
        required=True,
        widget=forms.Textarea(attrs={'rows': 25}),
    )
    niw = MultilineField(
        db_field_path='niw',
        label=_('Inventory number'),
        required=True,
        widget=forms.Textarea(attrs={'rows': 25}),
    )

    def clean(self):
        data = super(AddLicenceForm, self).clean()
        self.different_multival_counters(data)
        return data


class EditLicenceForm(ReadOnlyFieldsMixin, LicenceForm):
    """Form for licence edit."""

    readonly_fields = ('created',)

    class Meta(LicenceForm.Meta):
        model = models_sam.Licence
        fieldset = OrderedDict([
            ('Basic info', [
                'asset_type', 'manufacturer', 'licence_type',
                'software_category', 'parent', 'niw', 'sn', 'property_of',
                'valid_thru', 'assets', 'users', 'remarks', 'service_name',
                'license_details', 'created',
            ]),
            ('Financial info', [
                'order_no', 'invoice_date', 'invoice_no', 'price', 'provider',
                'number_bought', 'accounting_id', 'budget_info',
            ]),
        ])

        fields = (
            'accounting_id',
            'asset_type',
            'assets',
            'budget_info',
            'created',
            'invoice_date',
            'invoice_no',
            'licence_type',
            'license_details',
            'manufacturer',
            'niw',
            'number_bought',
            'order_no',
            'parent',
            'price',
            'property_of',
            'provider',
            'remarks',
            'service_name',
            'sn',
            'software_category',
            'users',
            'valid_thru',
        )

    sn = forms.CharField(widget=forms.Textarea, label=_('Licence key'))
    niw = forms.CharField(label=_('Inventory number'))


class SoftwareCategorySearchForm(SearchForm):
    class Meta(object):
        Model = models_sam.SoftwareCategory
        fields = ['name']


class LicenceSearchForm(SearchForm):
    class Meta(object):
        Model = models_sam.Licence
        fields = []

    niw = MultiSearchField(label=_('NIW'))
    sn = TextSearchField(label=_('SN'))
    remarks = TextSearchField(label=_('Additional remarks'))
    software_category = RelatedAjaxSearchField(
        LOOKUPS['softwarecategory'],
    )
    property_of = RelatedSearchField(Model=AssetOwner)
    licence_type = RelatedSearchField(LicenceType)
    parent_licence = RelatedAjaxSearchField(
        LOOKUPS['licence']
    )
    valid_thru = DateRangeSearchField()
    invoice_no = ExactSearchField()
    invoice_date = DateRangeSearchField()
    order_no = ExactSearchField()
    order_date = DateRangeSearchField()
    budget_info = AjaxTextSearch(
        '__name', LOOKUPS['budget_info'], required=False,
    )
    manufacturer = AjaxTextSearch(
        '__name', LOOKUPS['manufacturer'], required=False,
    )
    id = MultiSearchField(widget=forms.HiddenInput())


class BulkEditLicenceForm(LicenceForm):

    class Meta(LicenceForm.Meta):
        model = models_sam.Licence
        fields = (
            'asset_type',
            'manufacturer',
            'licence_type',
            'property_of',
            'software_category',
            'number_bought',
            'parent',
            'invoice_date',
            'valid_thru',
            'order_no',
            'price',
            'accounting_id',
            'provider',
            'invoice_no',
            'niw',
            'service_name',
            'sn',
            'remarks',
            'budget_info',
            'assets',
            'users',
        )
    sn = forms.CharField(label=_('Licence key'))
    remarks = forms.CharField(label=_('Additional remarks'), required=False)

    def __init__(self, *args, **kwargs):
        super(BulkEditLicenceForm, self).__init__(None, *args, **kwargs)
        banned_fillables = set(['niw', 'assets', 'users'])
        for field_name in self.fields:
            classes = "span12 fillable"
            if field_name in banned_fillables:
                classes = "span12"
            self.fields[field_name].widget.attrs.update({'class': classes})
