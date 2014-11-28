#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import re

from ajax_select.fields import (
    AutoCompleteSelectField,
    AutoCompleteField,
    AutoCompleteSelectMultipleField,
)
from bob.forms import (
    AJAX_UPDATE,
    CLONE,
    Dependency,
    dependency_conditions,
    DependencyForm,
    REQUIRE,
    SHOW,
)
from collections import OrderedDict
from django.core.urlresolvers import reverse
from django.forms import (
    BooleanField,
    CharField,
    ChoiceField,
    DateField,
    Form,
    IntegerField,
    ModelChoiceField,
    ModelForm,
    ValidationError,
)
from django.forms.widgets import HiddenInput, Textarea, TextInput
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from mptt.forms import TreeNodeChoiceField

from ralph_assets.models import (
    Asset,
    AssetCategory,
    AssetCategoryType,
    AssetSource,
    AssetStatus,
    AssetType,
    DeviceInfo,
    OfficeInfo,
    PartInfo,
    RALPH_DATE_FORMAT,
    Service,
)
from ralph_assets import models_assets
from ralph.discovery import models_device
from ralph.middleware import get_actual_regions
from ralph.ui.widgets import DateWidget, ReadOnlyWidget, SimpleReadOnlyWidget
from ralph.ui.forms.addresses import IPWithHostField


RALPH_DATE_FORMAT_LIST = [RALPH_DATE_FORMAT]


# We use lambdas, so the fieldsets can be recreated after modifications

asset_fieldset = lambda: OrderedDict([
    ('Basic Info', [
        'type', 'category', 'model', 'niw', 'barcode', 'sn', 'warehouse',
        'location', 'status', 'task_url', 'loan_end_date', 'remarks',
        'service_name', 'property_of', 'region',
    ]),
    ('Financial Info', [
        'order_no', 'invoice_date', 'invoice_no', 'price', 'provider',
        'deprecation_rate', 'source', 'request_date', 'provider_order_date',
        'delivery_date', 'deprecation_end_date', 'budget_info',
        'force_deprecation',
    ]),
    ('User Info', [
        'user', 'owner', 'employee_id', 'company', 'department', 'manager',
        'profit_center', 'cost_center',
    ]),
])

asset_search_back_office_fieldsets = lambda: OrderedDict([
    ('Basic Info', {
        'noncollapsed': [
            'barcode', 'status', 'imei', 'sn', 'model', 'hostname',
            'required_support', 'support_assigned', 'service',
            'device_environment', 'region',
        ],
        'collapsed': [
            'warehouse', 'task_url', 'category', 'loan_end_date_from',
            'loan_end_date_to', 'part_info', 'niw', 'manufacturer',
            'service_name', 'location', 'remarks',
        ],
    }),
    ('User data', {
        'noncollapsed': ['user', 'owner', 'segment'],
        'collapsed': [
            'company', 'department', 'employee_id', 'cost_center',
            'profit_center',
        ],
    }),
    ('Financial data', {
        'noncollapsed': [
            'invoice_no', 'invoice_date_from', 'invoice_date_to', 'order_no',
            'budget_info',
        ],
        'collapsed': [
            'provider', 'source', 'ralph_device_id', 'request_date_from',
            'request_date_to', 'provider_order_date_from',
            'provider_order_date_to', 'delivery_date_from', 'delivery_date_to',
            'deprecation_rate',
        ]
    })
])

asset_search_dc_fieldsets = lambda: OrderedDict([
    ('Basic Info', {
        'noncollapsed': [
            'barcode', 'sn', 'model', 'manufacturer', 'warehouse',
            'required_support', 'support_assigned', 'service',
            'device_environment', 'region',
        ],
        'collapsed': [
            'status', 'task_url', 'category', 'loan_end_date_from',
            'loan_end_date_to', 'part_info', 'niw', 'service_name',
            'location', 'remarks',
        ],
    }),
    ('User data', {
        'noncollapsed': ['user', 'owner'],
        'collapsed': [
            'company', 'department', 'employee_id', 'cost_center',
            'profit_center',
        ],
    }),
    ('Financial data', {
        'noncollapsed': [
            'invoice_no', 'invoice_date_from', 'invoice_date_to', 'order_no',
            'budget_info',
        ],
        'collapsed': [
            'provider', 'source', 'ralph_device_id', 'request_date_from',
            'request_date_to', 'provider_order_date_from',
            'provider_order_date_to', 'delivery_date_from', 'delivery_date_to',
            'deprecation_rate',
        ]
    })
])

LOOKUPS = {
    'asset': ('ralph_assets.models', 'DeviceLookup'),
    'asset_all': ('ralph_assets.models', 'AssetLookup'),
    'asset_bodevice': ('ralph_assets.models', 'BODeviceLookup'),
    'asset_bomodel': ('ralph_assets.models', 'BOAssetModelLookup'),
    'asset_dcdevice': ('ralph_assets.models', 'DCDeviceLookup'),
    'asset_dcmodel': ('ralph_assets.models', 'DCAssetModelLookup'),
    'asset_model': ('ralph_assets.models', 'AssetModelLookup'),
    'asset_user': ('ralph_assets.models', 'UserLookup'),
    'asset_warehouse': ('ralph_assets.models', 'WarehouseLookup'),
    'budget_info': ('ralph_assets.licences.models', 'BudgetInfoLookup'),
    'device_environment': ('ralph.ui.channels', 'DeviceEnvironmentLookup'),
    'free_licences': ('ralph_assets.models', 'FreeLicenceLookup'),
    'licence': ('ralph_assets.models', 'LicenceLookup'),
    'linked_device': ('ralph_assets.models', 'LinkedDeviceNameLookup'),
    'manufacturer': ('ralph_assets.models', 'ManufacturerLookup'),
    'ralph_device': ('ralph_assets.models', 'RalphDeviceLookup'),
    'service': ('ralph.ui.channels', 'ServiceCatalogLookup'),
    'softwarecategory': ('ralph_assets.models', 'SoftwareCategoryLookup'),
    'support': ('ralph_assets.models', 'SupportLookup'),
}


class ReadOnlyFieldsMixin(object):
    readonly_fields = ()

    def __init__(self, *args, **kwargs):
        super(ReadOnlyFieldsMixin, self).__init__(*args, **kwargs)
        for field in (
            field for name, field in self.fields.iteritems()
            if name in self.readonly_fields
        ):
            field.widget.attrs['disabled'] = 'true'
            field.required = False

    def clean(self):
        cleaned_data = super(ReadOnlyFieldsMixin, self).clean()
        for field in self.readonly_fields:
            cleaned_data[field] = getattr(self.instance, field)
        return cleaned_data


class MultivalFieldForm(ModelForm):
    """A form that has several multiline fields that need to have the
    same number of entries.

    :param multival_fields: list of form fields which require the same item
    count
    :param allow_duplicates: list of fields, if particular multivalue field
    allows duplicates, append it to this list
    """

    multival_fields = []
    allow_duplicates = []

    def __init__(self, *args, **kwargs):
        bad_fields = set(self.allow_duplicates).difference(
            set(self.multival_fields)
        )
        if len(bad_fields):
            raise Exception(
                "This field(s) is(are) not multival_fields: {}".format(
                    bad_fields,
                )
            )
        super(MultivalFieldForm, self).__init__(*args, **kwargs)

    def different_multival_counters(self, cleaned_data):
        """Adds a validation error if if form's multivalues fields have
        different count of items."""
        items_count_per_multi = set()
        for field in self.multival_fields:
            if cleaned_data.get(field, []):
                items_count_per_multi.add(len(cleaned_data.get(field, [])))
        if len(items_count_per_multi) > 1:
            for field in self.multival_fields:
                if field in cleaned_data:
                    msg = "Fields: {} - require the same count".format(
                        ', '.join(self.multival_fields)
                    )
                    self.errors.setdefault(field, []).append(msg)

    def unique_multival_fields(self, request_data):
        for field_name in self.multival_fields:
            if field_name in self.allow_duplicates:
                continue
            try:
                self[field_name].field.check_field_uniqueness(
                    self._meta.model,
                    request_data.get(field_name, [])
                )
            except ValidationError as err:
                self._errors.setdefault(field_name, [])
                self._errors[field_name] += err.messages

    def clean(self):
        data = super(MultivalFieldForm, self).clean()
        self.different_multival_counters(data)
        self.unique_multival_fields(data)
        return data


def move_after(_list, static, dynamic):
    """
    Move *static* elem. after *dynamic* elem. in list *_list*
    Both *static* and *dynamic* MUST belong to *_list*.
    :return list: return _list with moved *dynamic* elem.
    """
    _list.remove(dynamic)
    next_pos = _list.index(static) + 1
    _list.insert(next_pos, dynamic)
    return _list


def validate_snbcs(snbcs):
    """
    This validator checks if all snbcs item are snbc.
    Name 'snbc' is a join of 'serial number' (sn) and barcode ('bc'), because
    both things shares the same validation requirements.
    """
    def _validate_snbc(snbc):
        if ' ' in snbc:
            raise ValidationError(
                _("Item can't contain white characters.")
            )
        if len(snbc) > 200:
            raise ValidationError(
                _("Item max length is 200 characters.")
            )
    for snbc in snbcs:
        _validate_snbc(snbc)


class MultilineField(CharField):
    """
    This widget is a textarea which treats its content as many values seperated
    by: commas or "new lines"
    Validation:
        - separated values cannot duplicate each other,
        - empty values are disallowed,
        - db uniqueness is also checked.
    """
    separators = ",|\n"

    def __init__(self, db_field_path, reject_duplicates=True, *args, **kwargs):
        """
        :param string db_field_path: check arg *field_path* of function
        *_check_field_uniqueness*
        """
        self.db_field_path = db_field_path
        self.reject_duplicates = reject_duplicates
        super(MultilineField, self).__init__(*args, **kwargs)

    def validate(self, values):
        if not values and self.required:
            error_msg = _(
                "Field can't be empty. Please put the item OR items separated "
                "by new line or comma."
            )
            raise ValidationError(error_msg, code='required')
        items = set()
        for value in values:
            if value in items and self.reject_duplicates:
                raise ValidationError(_("There are duplicates in field."))
            elif value == '':
                raise ValidationError(_("Empty items disallowed, remove it."))
            elif value:
                items.add(value)

    def to_python(self, value):
        items = []
        if value:
            for item in re.split(self.separators, value):
                items.append(item.strip())
        return items

    def clean(self, value):
        value = super(MultilineField, self).clean(value)
        return value

    def check_field_uniqueness(self, Model, values):
        '''
            Check field (pointed by *self.db_field_path*) uniqueness.
            If duplicated value is found then raise ValidationError

            :param string Model: model field to be unique (as a string)
            :param list values: list of field values
        '''
        if not self.db_field_path or not values:
            return
        conditions = {
            '{}__in'.format(self.db_field_path): values
        }
        assets = Model.objects.filter(**conditions)
        if assets:
            raise ValidationError(mark_safe(
                'Following items already exist: ' +
                ', '.join([
                    '<a href="{}">{}</a>'.format(asset.url, asset.id)
                    for asset in assets
                ])
            ))


imei_until_2003 = re.compile(r'^\d{6} *\d{2} *\d{6} *\d$')
imei_since_2003 = re.compile(r'^\d{8} *\d{6} *\d$')


def validate_imei(imei):
    is_imei = imei_until_2003.match(imei) or imei_since_2003.match(imei)
    if not is_imei:
        raise ValidationError('"{}" is not IMEI format'.format(imei))


def validate_imeis(imeis):
    for imei in imeis:
        validate_imei(imei)


class ModeNotSetException(Exception):
    pass


class BarcodeField(CharField):
    def to_python(self, value):
        return value if value else None


class BulkEditAssetForm(DependencyForm, ModelForm):
    '''
        Form model for bulkedit assets, contains column definition and
        validadtion. Most important are sn and barcode fields. When you type
        sn you can place many sn numbers separated by pressing enter.
        Barcode count must be the same like sn count.
    '''
    class Meta:
        model = Asset
        widgets = {
            'delivery_date': DateWidget(),
            'deprecation_end_date': DateWidget(),
            'device_info': HiddenInput(),
            'invoice_date': DateWidget(),
            'provider_order_date': DateWidget(),
            'request_date': DateWidget(),
        }

    @property
    def dependencies(self):
        return [
            Dependency(
                'owner',
                'user',
                dependency_conditions.NotEmpty(),
                CLONE,
                page_load_update=False,
            ),
        ]

    barcode = BarcodeField(max_length=200, required=False)
    source = ChoiceField(
        required=False,
        choices=[('', '----')] + AssetSource(),
    )
    owner = AutoCompleteSelectField(
        LOOKUPS['asset_user'],
        required=False,
    )
    user = AutoCompleteSelectField(
        LOOKUPS['asset_user'],
        required=False,
    )

    def clean(self):
        invoice_no = self.cleaned_data.get('invoice_no', False)
        invoice_date = self.cleaned_data.get('invoice_date', False)
        if 'invoice_date' not in self.errors:
            if invoice_no and not invoice_date:
                self._errors["invoice_date"] = self.error_class([
                    _("Invoice date cannot be empty.")
                ])
        if 'invoice_on' not in self.errors:
            if invoice_date and not invoice_no:
                self._errors["invoice_no"] = self.error_class([
                    _("Invoice number cannot be empty.")
                ])
        serial_number_exists = \
            Asset.objects.filter(sn=self.cleaned_data['sn']).count()
        if 'sn' in self.changed_data and serial_number_exists:
            self._errors["sn"] = self.error_class([
                _("Asset with this Sn already exists.")

            ])
        return self.cleaned_data

    def clean_barcode(self):
        barcode = self.cleaned_data.get('barcode')
        if barcode:
            barcode_exists = Asset.objects.filter(barcode=barcode).count()
            if 'barcode' in self.changed_data and barcode_exists:
                self._errors["barcode"] = self.error_class([
                    _("Asset with this barcode already exists.")
                ])
        return barcode

    def _update_field_css_class(self, field_name):
        if field_name not in self.banned_fillables:
            classes = "span12 fillable"
        else:
            classes = "span12"
        self.fields[field_name].widget.attrs.update({'class': classes})

    def __init__(self, *args, **kwargs):
        super(BulkEditAssetForm, self).__init__(*args, **kwargs)
        self.banned_fillables = set(['sn', 'barcode', 'imei'])
        for field_name in self.fields:
            self._update_field_css_class(field_name)


class BackOfficeBulkEditAssetForm(BulkEditAssetForm):
    class Meta(BulkEditAssetForm.Meta):
        fields = (
            'type', 'status', 'barcode', 'hostname', 'model', 'user', 'owner',
            'warehouse', 'sn', 'property_of', 'purpose', 'remarks',
            'service_name', 'invoice_no', 'invoice_date', 'price', 'provider',
            'task_url', 'office_info', 'deprecation_rate', 'order_no',
            'source', 'deprecation_end_date',
        )

    def __init__(self, *args, **kwargs):
        super(BackOfficeBulkEditAssetForm, self).__init__(*args, **kwargs)
        self.banned_fillables.add('hostname')
        self._update_field_css_class('hostname')

    def clean_hostname(self):
        # make field readonly
        return self.instance.hostname or None

    hostname = CharField(
        required=False, widget=SimpleReadOnlyWidget(),
    )
    model = AutoCompleteSelectField(
        LOOKUPS['asset_bomodel'],
        required=True,
        plugin_options=dict(
            add_link='/admin/ralph_assets/assetmodel/add/?name=',
        )
    )
    purpose = ChoiceField(
        choices=[('', '----')] + models_assets.AssetPurpose(),
        label=_('Purpose'),
        required=False,
    )
    type = ChoiceField(
        required=True,
        choices=[('', '----')] + [
            (choice.id, choice.name) for choice in AssetType.BO.choices
        ],
    )


class DataCenterBulkEditAssetForm(BulkEditAssetForm):
    class Meta(BulkEditAssetForm.Meta):
        fields = (
            'status', 'barcode', 'model', 'user', 'owner', 'warehouse', 'sn',
            'property_of', 'remarks', 'service_name', 'invoice_no',
            'invoice_date', 'price', 'provider', 'task_url',
            'deprecation_rate', 'order_no', 'source', 'deprecation_end_date',
        )

    model = AutoCompleteSelectField(
        LOOKUPS['asset_dcmodel'],
        required=True,
        plugin_options=dict(
            add_link='/admin/ralph_assets/assetmodel/add/?name=',
        )
    )


class DeviceForm(ModelForm):
    class Meta:
        model = DeviceInfo
        fields = (
            'data_center',
            'server_room',
            'rack',
            'orientation',
            'position',
            'slot_no',
            'ralph_device_id',
        )

    force_unlink = BooleanField(required=False, label=_('Force unlink'))
    create_stock = BooleanField(
        required=False,
        label=_('Create stock device'),
    )

    def __init__(self, *args, **kwargs):
        kwargs.pop('mode')
        exclude = kwargs.pop('exclude', None)
        super(DeviceForm, self).__init__(*args, **kwargs)

        self.fields['ralph_device_id'] = AutoCompleteSelectField(
            LOOKUPS['ralph_device'],
            required=False,
            help_text=_('Enter ralph id, barcode, sn, or model.'),
        )
        if exclude == 'create_stock':
            del self.fields['create_stock']

    def clean_ralph_device_id(self):
        return self.data['ralph_device_id'] or None

    def clean_create_stock(self):
        create_stock = self.cleaned_data.get('create_stock', False)
        if create_stock:
            if not self.cleaned_data.get('ralph_device_id'):
                return create_stock
            else:
                raise ValidationError(
                    _("'Ralph device id' field should be blank")
                )
        else:
            return create_stock

    def clean(self):
        ralph_device_id = self.cleaned_data.get('ralph_device_id')
        force_unlink = self.cleaned_data.get('force_unlink')
        if ralph_device_id:
            device_info = None
            try:
                device_info = self.instance.__class__.objects.get(
                    ralph_device_id=ralph_device_id
                )
            except DeviceInfo.DoesNotExist:
                pass
            if device_info:
                # if we want to assign ralph_device_id that belongs to another
                # Asset/DeviceInfo...
                if (str(device_info.ralph_device_id) == ralph_device_id and
                        device_info.id != self.instance.id):
                    if force_unlink:
                        device_info.ralph_device_id = None
                        device_info.save()
                    else:
                        msg = _(
                            'Device with this Ralph device id already exist '
                            '<a href="../{}">(click here to see it)</a>. '
                            'Please tick "Force unlink" checkbox if you want '
                            'to unlink it.'
                        )
                        self._errors["ralph_device_id"] = self.error_class([
                            mark_safe(msg.format(escape(device_info.asset.id)))
                        ])
        return self.cleaned_data


class BasePartForm(ModelForm):
    class Meta:
        model = PartInfo
        fields = ('barcode_salvaged',)

    def __init__(self, *args, **kwargs):
        """mode argument is required for distinguish ajax sources"""
        mode = kwargs.get('mode')
        if mode:
            del kwargs['mode']
        else:
            raise ModeNotSetException("mode argument not given.")
        super(BasePartForm, self).__init__(*args, **kwargs)

        channel = 'asset_dcdevice' if mode == 'dc' else 'asset_bodevice'
        self.fields['device'] = AutoCompleteSelectField(
            LOOKUPS[channel],
            required=False,
            help_text=_('Enter barcode, sn, or model.'),
        )
        self.fields['source_device'] = AutoCompleteSelectField(
            LOOKUPS[channel],
            required=False,
            help_text=_('Enter barcode, sn, or model.'),
        )
        if self.instance.source_device:
            self.fields[
                'source_device'
            ].initial = self.instance.source_device.id
        if self.instance.device:
            self.fields['device'].initial = self.instance.device.id


class DependencyAssetForm(DependencyForm):
    """
    Containts common solution for adding asset and editing asset section.
    Launches a plugin which depending on the category field gives the
    opportunity to complete fields
    """

    def __init__(self, *args, **kwargs):
        if 'instance' in kwargs:
            initial = kwargs.setdefault('initial', {})
            initial['licences'] = [
                licence['pk']
                for licence in kwargs['instance'].licences.values('pk')
            ]
            initial['supports'] = [
                support['pk']
                for support in kwargs['instance'].supports.values('pk')
            ]
        super(DependencyAssetForm, self).__init__(*args, **kwargs)

    @property
    def dependencies(self):
        """
        On the basis of data from the database gives the opportunity
        to complete fields

        :returns object: Logic to test if category is in selected categories
        :rtype object:
        """
        deps = [
            Dependency(
                'imei',
                'category',
                dependency_conditions.MemberOf(
                    AssetCategory.objects.filter(pk__in=[
                        "1-1-back-office-mobile-devices",
                        "1-1-1-back-office-mobile-devices-mobile-phone",
                        "1-1-1-back-office-mobile-devices-smartphone",
                        "1-1-1-back-office-mobile-devices-tablet",
                    ]).all()
                ),
                SHOW,
            ),
            Dependency(
                'imei',
                'category',
                dependency_conditions.MemberOf(
                    AssetCategory.objects.filter(pk__in=[
                        "1-1-back-office-mobile-devices",
                        "1-1-1-back-office-mobile-devices-mobile-phone",
                        "1-1-1-back-office-mobile-devices-smartphone",
                    ]).all()
                ),
                REQUIRE,
            ),
            Dependency(
                'category',
                'model',
                dependency_conditions.Any(),
                AJAX_UPDATE,
                url=reverse('model_dependency_view'),
            ),
            Dependency(
                'location',
                'owner',
                dependency_conditions.NotEmpty(),
                AJAX_UPDATE,
                url=reverse('category_dependency_view'),
                page_load_update=False,
            ),
            Dependency(
                'loan_end_date',
                'status',
                dependency_conditions.Exact(AssetStatus.loan.id),
                SHOW,
            ),
            Dependency(
                'loan_end_date',
                'status',
                dependency_conditions.Exact(AssetStatus.loan.id),
                REQUIRE,
            ),
            Dependency(
                'note',
                'status',
                dependency_conditions.Exact(AssetStatus.loan.id),
                SHOW,
            ),
            Dependency(
                'owner',
                'user',
                dependency_conditions.NotEmpty(),
                CLONE,
                page_load_update=False,
            ),
        ]
        ad_fields = (
            'company',
            'cost_center',
            'department',
            'employee_id',
            'manager',
            'profit_center',
            'segment',
        )
        deps.extend(
            [
                Dependency(
                    slave,
                    'owner',
                    dependency_conditions.NotEmpty(),
                    AJAX_UPDATE,
                    url=reverse('category_dependency_view'),
                ) for slave in ad_fields
            ]
        )
        deps.extend(
            [
                Dependency(
                    slave,
                    'owner',
                    dependency_conditions.NotEmpty(),
                    SHOW,
                ) for slave in ad_fields
            ]
        )
        for dep in deps:
            yield dep


class BaseAssetForm(ModelForm):

    edit_management_ip = False

    def __init__(self, *args, **kwargs):
        super(BaseAssetForm, self).__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if self.edit_management_ip:
            self.fields['management_ip'] = IPWithHostField(required=False)
            self.fieldsets['Basic Info'].append('management_ip')
            if instance and self.edit_management_ip:
                device = instance.get_ralph_device()
                if device:
                    management_ip = device.management_ip
                    self.fields['management_ip'].initial =\
                        management_ip and management_ip.as_tuple()

    class Meta:
        model = Asset

    def clean(self):
        cleaned_data = super(BaseAssetForm, self).clean()
        env = cleaned_data.get("device_environment")
        service = cleaned_data.get("service")
        if env and service:
            service_envs = service.get_environments()
            if env not in service_envs:
                msg = _(
                    "This value is not valid anymore for selected "
                    "'service catalog'. Valid options: {}".format(
                        ', '.join([_env.name for _env in service_envs])
                    )
                )
                self._errors["device_environment"] = msg
        return cleaned_data

    def customize_fields(self):
        """
        This is the place for fields customization.
        Sometimes field can't be set completely during init. (like, change
        field completition depending on data from request, eg.
        mode=DataCenter|BackOffice).
        """
        if self.mode == "dc":
            self.fields['model'].widget.plugin_options['add_link'] +=\
                '&type=' + str(AssetType.data_center.id)
            self.fields['model'].widget.channel = LOOKUPS['asset_dcmodel']
            self.fields['type'].choices = [
                (c.id, c.desc) for c in AssetType.DC.choices]
        elif self.mode == "back_office":
            self.fields['model'].widget.plugin_options['add_link'] +=\
                '&type=' + str(AssetType.back_office.id)
            self.fields['model'].widget.channel = LOOKUPS['asset_bomodel']
            self.fields['type'].choices = [
                (c.id, c.desc) for c in AssetType.BO.choices]


class BaseAddAssetForm(DependencyAssetForm, BaseAssetForm):
    '''
        Base class to display form used to add new asset
    '''

    class Meta:
        model = Asset
        fields = (
            'budget_info',
            'company',
            'cost_center',
            'delivery_date',
            'department',
            'deprecation_end_date',
            'deprecation_rate',
            'employee_id',
            'force_deprecation',
            'imei',
            'invoice_date',
            'invoice_no',
            'loan_end_date',
            'location',
            'manager',
            'model',
            'niw',
            'note',
            'order_no',
            'owner',
            'price',
            'profit_center',
            'property_of',
            'provider',
            'provider_order_date',
            'region',
            'remarks',
            'request_date',
            'required_support',
            'service_name',
            'source',
            'status',
            'task_url',
            'type',
            'user',
            'warehouse',
        )
        widgets = {
            'delivery_date': DateWidget(),
            'deprecation_end_date': DateWidget(),
            'invoice_date': DateWidget(),
            'loan_end_date': DateWidget(),
            'note': Textarea(attrs={'rows': 3}),
            'provider_order_date': DateWidget(),
            'remarks': Textarea(attrs={'rows': 3}),
            'request_date': DateWidget(),
        }
    model = AutoCompleteSelectField(
        LOOKUPS['asset_model'],
        required=True,
        plugin_options=dict(
            add_link='/admin/ralph_assets/assetmodel/add/?name=',
        )
    )
    licences = AutoCompleteSelectMultipleField(
        LOOKUPS['free_licences'],
        required=False,
    )
    warehouse = AutoCompleteSelectField(
        LOOKUPS['asset_warehouse'],
        required=True,
        plugin_options=dict(
            add_link='/admin/ralph_assets/warehouse/add/?name=',
        )
    )
    category = CharField(
        widget=HiddenInput(),
        required=False,
    )
    source = ChoiceField(
        required=False,
        choices=[('', '----')] + AssetSource(),
    )
    imei = CharField(
        min_length=15, max_length=18, validators=[validate_imei],
        label=_('IMEI'), required=False,
    )
    owner = AutoCompleteSelectField(
        LOOKUPS['asset_user'],
        required=False,
    )
    location = CharField(required=False)
    company = CharField(
        max_length=64,
        required=False,
    )
    employee_id = CharField(
        max_length=64,
        required=False,
    )
    cost_center = CharField(
        max_length=1024,
        required=False,
    )
    profit_center = CharField(
        max_length=1024,
        required=False,
    )
    department = CharField(
        max_length=64,
        required=False,
    )
    manager = CharField(
        max_length=1024,
        required=False,
    )
    user = AutoCompleteSelectField(
        LOOKUPS['asset_user'],
        required=False,
    )
    supports = AutoCompleteSelectMultipleField(
        LOOKUPS['support'],
        required=False,
    )
    budget_info = AutoCompleteSelectField(
        LOOKUPS['budget_info'],
        required=False,
        plugin_options=dict(
            add_link='/admin/ralph_assets/budgetinfo/add/',
        )
    )

    def __init__(self, *args, **kwargs):
        self.fieldsets = asset_fieldset()
        self.mode = kwargs.pop('mode', None)
        super(BaseAddAssetForm, self).__init__(*args, **kwargs)
        self.customize_fields()
        for readonly_field in (
            'company',
            'employee_id',
            'cost_center',
            'profit_center',
            'department',
            'manager',
        ):
            self.fields[readonly_field].widget = ReadOnlyWidget()

    def clean_category(self):
        data = self.cleaned_data["category"]
        if not data:
            return data
        try:
            category = AssetCategory.objects.get(pk=data)
        except AssetCategory.DoesNotExist:
            raise ValidationError('"{}" is not proper category'.format(data))
        if not category.parent:
            raise ValidationError(
                _("Category must be selected from the subcategory")
            )
        return category

    def clean_imei(self):
        return self.cleaned_data['imei'] or None


class BaseEditAssetForm(DependencyAssetForm, BaseAssetForm):
    '''
        Base class to display form used to edit asset
    '''

    class Meta:
        model = Asset
        fields = (
            'barcode',
            'budget_info',
            'company',
            'cost_center',
            'deleted',
            'delivery_date',
            'department',
            'deprecation_end_date',
            'deprecation_rate',
            'employee_id',
            'force_deprecation',
            'imei',
            'invoice_date',
            'invoice_no',
            'loan_end_date',
            'location',
            'manager',
            'model',
            'niw',
            'note',
            'order_no',
            'owner',
            'price',
            'profit_center',
            'property_of',
            'provider',
            'provider_order_date',
            'region',
            'remarks',
            'request_date',
            'required_support',
            'service_name',
            'sn',
            'source',
            'status',
            'task_url',
            'type',
            'user',
            'warehouse',
        )
        widgets = {
            'barcode': Textarea(attrs={'rows': 1}),
            'delivery_date': DateWidget(),
            'deprecation_end_date': DateWidget(),
            'invoice_date': DateWidget(),
            'loan_end_date': DateWidget(),
            'note': Textarea(attrs={'rows': 3}),
            'provider_order_date': DateWidget(),
            'remarks': Textarea(attrs={'rows': 3}),
            'request_date': DateWidget(),
            'sn': Textarea(attrs={'rows': 1, 'readonly': '1'}),
        }
    model = AutoCompleteSelectField(
        LOOKUPS['asset_model'],
        required=True,
        plugin_options=dict(
            add_link='/admin/ralph_assets/assetmodel/add/?name=',
        )
    )
    licences = AutoCompleteSelectMultipleField(
        LOOKUPS['free_licences'],
        required=False,
    )
    warehouse = AutoCompleteSelectField(
        LOOKUPS['asset_warehouse'],
        required=True,
        plugin_options=dict(
            add_link='/admin/ralph_assets/warehouse/add/?name=',
        )
    )
    category = CharField(
        widget=HiddenInput(),
        required=False,
    )
    source = ChoiceField(
        required=False,
        choices=[('', '----')] + AssetSource(),
    )
    imei = CharField(
        min_length=15, max_length=18, validators=[validate_imei],
        label=_('IMEI'), required=False,
    )
    user = AutoCompleteSelectField(
        LOOKUPS['asset_user'],
        required=False,
    )
    owner = AutoCompleteSelectField(
        LOOKUPS['asset_user'],
        required=False,
    )
    location = CharField(required=False)
    company = CharField(
        max_length=64,
        required=False,
    )
    employee_id = CharField(
        max_length=64,
        required=False,
    )
    cost_center = CharField(
        max_length=1024,
        required=False,
    )
    profit_center = CharField(
        max_length=1024,
        required=False,
    )
    department = CharField(
        max_length=64,
        required=False,
    )
    manager = CharField(
        max_length=1024,
        required=False,
    )
    supports = AutoCompleteSelectMultipleField(
        LOOKUPS['support'],
        required=False,
    )
    budget_info = AutoCompleteSelectField(
        LOOKUPS['budget_info'],
        required=False,
        plugin_options=dict(
            add_link='/admin/ralph_assets/budgetinfo/add/',
        )
    )

    def __init__(self, *args, **kwargs):
        self.fieldsets = asset_fieldset()
        self.mode = kwargs.pop('mode', None)
        super(BaseEditAssetForm, self).__init__(*args, **kwargs)
        self.customize_fields()
        for readonly_field in (
            'company',
            'employee_id',
            'cost_center',
            'profit_center',
            'department',
            'manager',
        ):
            self.fields[readonly_field].widget = ReadOnlyWidget()

    def clean_sn(self):
        return self.instance.sn

    def clean_category(self):
        data = self.cleaned_data["category"]
        if not data:
            return data
        try:
            category = AssetCategory.objects.get(pk=data)
        except AssetCategory.DoesNotExist:
            raise ValidationError('"{}" is not proper category'.format(data))
        if not category.parent:
            raise ValidationError(
                _("Category must be selected from the subcategory")
            )
        return category

    def clean_imei(self):
        return self.cleaned_data['imei'] or None

    def clean(self):
        self.cleaned_data = super(BaseEditAssetForm, self).clean()
        if self.instance.deleted:
            raise ValidationError(_("Cannot edit deleted asset"))
        cleaned_data = super(BaseEditAssetForm, self).clean()
        return cleaned_data


class MoveAssetPartForm(Form):
    new_asset = AutoCompleteSelectField(
        LOOKUPS['asset_dcdevice'],
    )


class AddPartForm(BaseAddAssetForm, MultivalFieldForm):
    '''
        Add new part for device
    '''

    multival_fields = ['sn']

    sn = MultilineField(
        db_field_path='sn', label=_('SN/SNs'), required=True,
        widget=Textarea(attrs={'rows': 25}),
        validators=[validate_snbcs],
    )

    def __init__(self, *args, **kwargs):
        super(AddPartForm, self).__init__(*args, **kwargs)
        self.fieldsets = asset_fieldset()
        self.fieldsets['Basic Info'].remove('barcode')


class AddDeviceForm(BaseAddAssetForm, MultivalFieldForm):
    '''
        Add new device form
    '''
    multival_fields = ['sn', 'barcode', 'imei']

    sn = MultilineField(
        db_field_path='sn', label=_('SN/SNs'), required=False,
        widget=Textarea(attrs={'rows': 25}), validators=[validate_snbcs]
    )
    barcode = MultilineField(
        db_field_path='barcode', label=_('Barcode/Barcodes'), required=False,
        widget=Textarea(attrs={'rows': 25}),
        validators=[validate_snbcs],
    )
    imei = MultilineField(
        db_field_path='office_info__imei', label=_('IMEI'), required=False,
        widget=Textarea(attrs={'rows': 25}),
        validators=[validate_imeis],
    )

    def __init__(self, *args, **kwargs):
        super(AddDeviceForm, self).__init__(*args, **kwargs)
        self.fields['region'] = ModelChoiceField(queryset=get_actual_regions())

    def clean(self):
        """
        These form requirements:
            1. *barcode* OR *sn* is REQUIRED,
            2. multivalue field value if provided MUST be the same length as
            rest of multivalues.
        """
        cleaned_data = super(AddDeviceForm, self).clean()
        if not (self.data['sn'] or self.data['barcode']):
            msg = _('SN or BARCODE field is required')
            for field in ['sn', 'barcode']:
                self.errors.setdefault(field, []).append(msg)
            self.different_multival_counters(cleaned_data)
        return cleaned_data


class BackOfficeAddDeviceForm(AddDeviceForm):

    class Meta(BaseAddAssetForm.Meta):
        fields = BaseAddAssetForm.Meta.fields + (
            'device_environment', 'service', 'segment',
        )

    device_environment = ModelChoiceField(
        required=False,
        queryset=models_device.DeviceEnvironment.objects.all(),
        label=_('Environment'),
    )
    purpose = ChoiceField(
        choices=[('', '----')] + models_assets.AssetPurpose(),
        label=_('Purpose'),
        required=False,
    )
    segment = CharField(
        max_length=256,
        required=False,
        widget=TextInput(attrs={'readonly': 'readonly'}),
    )
    service = AutoCompleteSelectField(
        LOOKUPS['service'],
        required=False,
        label=_('Service catalog'),
    )

    def __init__(self, *args, **kwargs):
        super(BackOfficeAddDeviceForm, self).__init__(*args, **kwargs)
        for after, field in (
            ('property_of', 'service'),
            ('service', 'device_environment'),
        ):
            self.fieldsets['Basic Info'].append(field)
            move_after(self.fieldsets['Basic Info'], after, field)
        self.fieldsets['User Info'].append('segment')


class DataCenterAddDeviceForm(AddDeviceForm):

    edit_management_ip = True

    class Meta(BaseAddAssetForm.Meta):
        fields = BaseAddAssetForm.Meta.fields + (
            'device_environment', 'service',
        )
    device_environment = ModelChoiceField(
        required=True,
        queryset=models_device.DeviceEnvironment.objects.all(),
        label=_('Environment'),
    )
    service = AutoCompleteSelectField(
        LOOKUPS['service'],
        required=True,
        label=_('Service catalog'),
    )

    def __init__(self, *args, **kwargs):
        super(DataCenterAddDeviceForm, self).__init__(*args, **kwargs)
        for after, field in (
            ('property_of', 'service'),
            ('service', 'device_environment'),
        ):
            self.fieldsets['Basic Info'].append(field)
            move_after(self.fieldsets['Basic Info'], after, field)


class OfficeForm(ModelForm):
    class Meta:
        model = OfficeInfo
        exclude = ('imei', 'purpose', 'created', 'modified')
        widgets = {
            'date_of_last_inventory': DateWidget(),
        }


class EditPartForm(BaseEditAssetForm):
    def __init__(self, *args, **kwargs):
        super(EditPartForm, self).__init__(*args, **kwargs)
        self.fieldsets = asset_fieldset()
        self.fieldsets['Assigned supports info'] = [
            'required_support',
            'supports',
        ]


class EditDeviceForm(BaseEditAssetForm):

    def __init__(self, *args, **kwargs):
        super(EditDeviceForm, self).__init__(*args, **kwargs)
        self.fieldsets['Assigned licenses info'] = ['licences']
        self.fieldsets['Assigned supports info'] = [
            'required_support',
            'supports',
        ]
        self.fields['region'] = ModelChoiceField(queryset=get_actual_regions())

    def clean(self):
        cleaned_data = super(EditDeviceForm, self).clean()
        deleted = cleaned_data.get("deleted")
        if deleted and self.instance.has_parts():
            parts = self.instance.get_parts_info()
            raise ValidationError(
                _(
                    "Cannot remove asset with parts assigned. Please remove "
                    "or unassign them from device first. ".format(
                        ", ".join([part.asset.sn for part in parts])
                    )
                )
            )
        if not cleaned_data.get('sn') and not cleaned_data.get('barcode'):
            raise ValidationError(
                _("If SN is empty - Barcode is required")
            )
        return cleaned_data

    def clean_hostname(self):
        # make field readonly
        return self.instance.hostname or None


class BackOfficeEditDeviceForm(ReadOnlyFieldsMixin, EditDeviceForm):

    fieldsets = OrderedDict([
        ('Basic Info', [
            'type', 'category', 'model', 'niw', 'barcode', 'sn', 'imei',
            'warehouse', 'location', 'status', 'task_url', 'loan_end_date',
            'purpose', 'remarks', 'service_name', 'property_of', 'hostname',
            'created', 'service', 'device_environment', 'region',
        ]),
        ('Financial Info', [
            'order_no', 'invoice_date', 'invoice_no', 'price', 'provider',
            'deprecation_rate', 'source', 'request_date',
            'provider_order_date', 'delivery_date',
            'deprecation_end_date', 'budget_info', 'force_deprecation',
        ]),
        ('User Info', [
            'user', 'owner', 'employee_id', 'company', 'department', 'manager',
            'profit_center', 'cost_center', 'segment',
        ]),
        ('Assigned licenses info', ['licences']),
        ('Assigned supports info', [
            'user', 'owner', 'employee_id', 'company', 'department', 'manager',
            'profit_center', 'cost_center',
        ]),
        ('Assigned supports info', ['required_support', 'supports']),
    ])

    readonly_fields = ('created', 'hostname')

    class Meta(BaseEditAssetForm.Meta):
        fields = BaseEditAssetForm.Meta.fields + (
            'device_environment', 'hostname', 'service', 'created',
            'hostname', 'created', 'segment',
        )

    device_environment = ModelChoiceField(
        required=False,
        queryset=models_device.DeviceEnvironment.objects.all(),
        label=_('Environment'),
    )
    purpose = ChoiceField(
        choices=[('', '----')] + models_assets.AssetPurpose(),
        label=_('Purpose'),
        required=False,
    )
    segment = CharField(
        max_length=256,
        required=False,
        widget=TextInput(attrs={'readonly': 'readonly'}),
    )
    service = AutoCompleteSelectField(
        LOOKUPS['service'],
        required=False,
        label=_('Service catalog'),
    )

    def __init__(self, *args, **kwargs):
        super(BackOfficeEditDeviceForm, self).__init__(*args, **kwargs)
        self.fieldsets = BackOfficeEditDeviceForm.fieldsets


class DataCenterEditDeviceForm(ReadOnlyFieldsMixin, EditDeviceForm):

    fieldsets = OrderedDict([
        ('Basic Info', [
            'type', 'category', 'model', 'niw', 'barcode', 'sn', 'warehouse',
            'location', 'status', 'task_url', 'loan_end_date', 'remarks',
            'service_name', 'property_of', 'hostname', 'service',
            'device_environment', 'region', 'management_ip',
        ]),
        ('Financial Info', [
            'order_no', 'invoice_date', 'invoice_no', 'price', 'provider',
            'deprecation_rate', 'source', 'request_date',
            'provider_order_date', 'delivery_date', 'deprecation_end_date',
            'budget_info', 'force_deprecation',
        ]),
        ('User Info', [
            'user', 'owner', 'employee_id', 'company', 'department', 'manager',
            'profit_center', 'cost_center',
        ]),
        ('Assigned licenses info', ['licences']),
        ('Assigned supports info', [
            'user', 'owner', 'employee_id', 'company', 'department', 'manager',
            'profit_center', 'cost_center',
        ]),
        ('Assigned supports info', ['required_support', 'supports']),
    ])

    readonly_fields = ('hostname',)

    edit_management_ip = True

    class Meta(BaseEditAssetForm.Meta):
        fields = BaseEditAssetForm.Meta.fields + (
            'device_environment', 'service', 'hostname',
        )

    device_environment = ModelChoiceField(
        required=True,
        queryset=models_device.DeviceEnvironment.objects.all(),
        label=_('Environment'),
    )
    service = AutoCompleteSelectField(
        LOOKUPS['service'],
        required=True,
        label=_('Service catalog'),
    )

    def __init__(self, *args, **kwargs):
        super(DataCenterEditDeviceForm, self).__init__(*args, **kwargs)
        self.fieldsets = DataCenterEditDeviceForm.fieldsets
        try:
            device_hostname = kwargs['instance'].linked_device.name
        except AttributeError:
            device_hostname = ''
        self.initial['hostname'] = device_hostname


class SearchAssetForm(Form):
    """returns search asset form for DC and BO.

    :param mode: one of `dc` for DataCenter or `bo` for Back Office
    :returns Form
    """
    manufacturer = AutoCompleteField(
        LOOKUPS['manufacturer'],
        required=False,
        help_text=None,
        plugin_options={'disable_confirm': True}
    )
    invoice_no = CharField(required=False)
    order_no = CharField(required=False)
    provider = CharField(required=False, label=_('Provider'))
    status = ChoiceField(
        required=False, choices=[('', '----')] + AssetStatus(),
        label=_('Status'),
    )
    task_url = CharField(required=False, label=_('Task url'))
    owner = AutoCompleteSelectField(
        LOOKUPS['asset_user'],
        required=False,
        plugin_options={'disable_confirm': True}
    )
    user = AutoCompleteSelectField(
        LOOKUPS['asset_user'],
        required=False,
        plugin_options={'disable_confirm': True}
    )
    location = CharField(required=False, label=_('Location'))
    company = CharField(required=False, label=_('Company'))
    employee_id = CharField(required=False, label=_('Employee id'))
    cost_center = CharField(required=False, label=_('Cost center'))
    profit_center = CharField(required=False, label=_('Profit center'))
    department = CharField(required=False, label=_('Department'))
    part_info = ChoiceField(
        required=False,
        choices=[('', '----'), ('device', 'Device'), ('part', 'Part')],
        label=_('Asset type'),
    )
    source = ChoiceField(
        required=False,
        choices=[('', '----')] + AssetSource(),
    )
    niw = CharField(
        required=False,
        label=_('Inventory number'),
        widget=TextInput(
            attrs={
                'title': _('separate ";" or "|" to search multiple value'),
            },
        )
    )
    sn = CharField(
        required=False,
        label=_('SN'),
        widget=TextInput(
            attrs={
                'title': _('separate ";" or "|" to search multiple value'),
            },
        )
    )
    barcode = CharField(
        required=False,
        label=_('Barcode'),
        widget=TextInput(
            attrs={
                'title': _('separate ";" or "|" to search multiple value'),
            },
        )
    )
    hostname = CharField(
        required=False,
        label=_('hostname'),
        widget=TextInput(
            attrs={
                'title': _('separate ";" or "|" to search multiple value'),
            },
        )
    )
    ralph_device_id = IntegerField(
        required=False,
        label=_('Ralph device id'),
    )
    request_date_from = DateField(
        required=False, widget=DateWidget(attrs={
            'placeholder': _('Start YYYY-MM-DD'),
            'data-collapsed': True,
        }),
        label=_('Request date'),
        input_formats=RALPH_DATE_FORMAT_LIST,
    )
    request_date_to = DateField(
        required=False, widget=DateWidget(attrs={
            'class': 'end-date-field ',
            'placeholder': _('End YYYY-MM-DD'),
            'data-collapsed': True,
        }),
        label='',
        input_formats=RALPH_DATE_FORMAT_LIST,
    )
    provider_order_date_from = DateField(
        required=False, widget=DateWidget(attrs={
            'placeholder': _('Start YYYY-MM-DD'),
            'data-collapsed': True,
        }),
        label=_('Provider order date'),
        input_formats=RALPH_DATE_FORMAT_LIST,
    )
    provider_order_date_to = DateField(
        required=False, widget=DateWidget(attrs={
            'class': 'end-date-field ',
            'placeholder': _('End YYYY-MM-DD'),
            'data-collapsed': True,
        }),
        label='',
        input_formats=RALPH_DATE_FORMAT_LIST,
    )
    delivery_date_from = DateField(
        required=False, widget=DateWidget(attrs={
            'placeholder': _('Start YYYY-MM-DD'),
            'data-collapsed': True,
        }),
        label=_('Delivery date'),
        input_formats=RALPH_DATE_FORMAT_LIST,
    )
    delivery_date_to = DateField(
        required=False, widget=DateWidget(attrs={
            'class': 'end-date-field ',
            'placeholder': _('End YYYY-MM-DD'),
            'data-collapsed': True,
        }),
        label='',
        input_formats=RALPH_DATE_FORMAT_LIST,
    )
    deprecation_rate = ChoiceField(
        required=False, choices=[('', '----'),
                                 ('null', 'None'),
                                 ('48>', '48 <'),
                                 ('48', '24 < * <= 48'),
                                 ('24', '12 < * <= 24'),
                                 ('12', '6 < * <= 12'),
                                 ('6', '* <= 6'),
                                 ('deprecated', 'Deprecated'), ],
        label=_('Deprecation')
    )
    invoice_date_from = DateField(
        required=False, widget=DateWidget(attrs={
            'placeholder': _('Start YYYY-MM-DD'),
            'data-collapsed': True,
        }),
        label=_('Invoice date'),
        input_formats=RALPH_DATE_FORMAT_LIST,
    )
    invoice_date_to = DateField(
        required=False, widget=DateWidget(attrs={
            'class': 'end-date-field ',
            'placeholder': _('End YYYY-MM-DD'),
            'data-collapsed': True,
        }),
        label='',
        input_formats=RALPH_DATE_FORMAT_LIST,
    )
    unlinked = BooleanField(required=False, label=_('Is unlinked'))
    deleted = BooleanField(required=False, label=_('Include deleted'))
    loan_end_date_from = DateField(
        required=False, widget=DateWidget(attrs={
            'placeholder': _('Start YYYY-MM-DD'),
            'data-collapsed': True,
        }),
        label=_('Loan end date'),
        input_formats=RALPH_DATE_FORMAT_LIST,
    )
    loan_end_date_to = DateField(
        required=False, widget=DateWidget(attrs={
            'class': 'end-date-field ',
            'placeholder': _('End YYYY-MM-DD'),
            'data-collapsed': True,
        }),
        label='',
        input_formats=RALPH_DATE_FORMAT_LIST,
    )
    service_name = ModelChoiceField(
        queryset=Service.objects.all(), empty_label='----', required=False,
    )
    warehouse = AutoCompleteSelectField(
        LOOKUPS['asset_warehouse'],
        required=False,
        plugin_options={'disable_confirm': True}
    )
    remarks = CharField(
        required=False,
        label=_('Additional remarks'),
    )
    budget_info = AutoCompleteField(
        LOOKUPS['budget_info'], required=False,
    )
    required_support = ChoiceField(
        required=False,
        choices=[('', '----'), ('yes', 'yes'), ('no', 'no')],
        label=_('Required support'),
    )
    support_assigned = ChoiceField(
        required=False,
        choices=[('', '----'), ('any', 'any'), ('none', 'none')],
        label=_('Assigned supports'),
    )
    service = AutoCompleteField(
        LOOKUPS['service'],
        label=_('Service catalog'),
        required=False,
    )
    device_environment = AutoCompleteField(
        LOOKUPS['device_environment'],
        label=_('Environment'),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        # Ajax sources are different for DC/BO, use mode for distinguish
        self.mode = kwargs.pop('mode', None)
        super(SearchAssetForm, self).__init__(*args, **kwargs)
        self.fields['region'] = ModelChoiceField(
            queryset=get_actual_regions(), required=False,
        )


class DataCenterSearchAssetForm(SearchAssetForm):

    def __init__(self, *args, **kwargs):
        super(DataCenterSearchAssetForm, self).__init__(*args, **kwargs)
        self.fieldsets = asset_search_dc_fieldsets()

    category = TreeNodeChoiceField(
        required=False,
        queryset=AssetCategory.tree.filter(
            type=AssetCategoryType.data_center
        ).all(),
        level_indicator='|---',
        empty_label='---',
    )
    model = AutoCompleteField(
        LOOKUPS['asset_dcmodel'],
        required=False,
        help_text=None,
        plugin_options={'disable_confirm': True}
    )


class BackOfficeSearchAssetForm(SearchAssetForm):
    category = TreeNodeChoiceField(
        required=False,
        queryset=AssetCategory.tree.filter(
            type=AssetCategoryType.back_office
        ).all(),
        level_indicator='|---',
        empty_label='---',
    )

    imei = CharField(required=False, label=_('IMEI'))
    model = AutoCompleteField(
        LOOKUPS['asset_bomodel'],
        required=False,
        help_text=None,
        plugin_options={'disable_confirm': True}
    )
    purpose = ChoiceField(
        choices=[('', '----')] + models_assets.AssetPurpose(),
        label=_('Purpose'),
        required=False,
    )
    segment = CharField(max_length=256, required=False)

    def __init__(self, *args, **kwargs):
        super(BackOfficeSearchAssetForm, self).__init__(*args, **kwargs)
        self.fieldsets = asset_search_back_office_fieldsets()


class DeleteAssetConfirmForm(Form):
    asset_id = IntegerField(widget=HiddenInput())


class SplitDevice(ModelForm):
    class Meta:
        model = Asset
        fields = (
            'id', 'delete', 'model_proposed', 'model_user', 'invoice_no',
            'order_no', 'sn', 'barcode', 'price', 'provider', 'source',
            'status', 'request_date', 'delivery_date', 'invoice_date',
            'provider_order_date', 'warehouse',
        )
        widgets = {
            'request_date': DateWidget(),
            'delivery_date': DateWidget(),
            'invoice_date': DateWidget(),
            'production_use_date': DateWidget(),
            'provider_order_date': DateWidget(),
            'device_info': HiddenInput(),
        }
    delete = BooleanField(required=False)
    model_user = CharField()
    model_proposed = CharField(required=False)

    def __init__(self, *args, **kwargs):
        super(SplitDevice, self).__init__(*args, **kwargs)
        fillable_fields = [
            'model_user', 'device_info', 'invoice_no', 'order_no',
            'request_date', 'delivery_date', 'invoice_date',
            'production_use_date', 'provider_order_date',
            'provider_order_date', 'provider', 'source', 'status', 'warehouse',
        ]
        for field_name in self.fields:
            if field_name in fillable_fields:
                classes = "span12 fillable"
            else:
                classes = "span12"
            self.fields[field_name].widget.attrs = {'class': classes}
        self.fields['model_proposed'].widget = ReadOnlyWidget()

    def clean(self):
        cleaned_data = super(SplitDevice, self).clean()
        sn = cleaned_data.get('sn')
        barcode = cleaned_data.get('barcode')
        price = cleaned_data.get('price', '')
        try:
            float(price)
        except (ValueError, TypeError):
            if 'price' in self.errors:
                self.errors['price'].append(_("Price must be decimal"))
            else:
                self.errors['price'] = [_("Price must be decimal"), ]
        if not sn:
            cleaned_data['sn'] = None
        if not barcode:
            cleaned_data['barcode'] = None
        if not sn and not barcode:
            error_text = [_("SN or Barcode is required"), ]
            self.errors['sn'] = error_text
            self.errors['barcode'] = error_text
        return cleaned_data


class AttachmentForm(ModelForm):
    class Meta:
        model = models_assets.Attachment
        fields = ['file']


class UserRelationForm(Form):
    """A form that allows licence assignment for a user."""

    def __init__(self, user, *args, **kwargs):
        initial = kwargs.setdefault('initial', {})
        initial['licences'] = [
            licence['licence_id']
            for licence in user.licences.values('licence_id')
        ]
        super(UserRelationForm, self).__init__(*args, **kwargs)

    licences = AutoCompleteSelectMultipleField(
        LOOKUPS['free_licences'],
        required=False,
    )


class SearchUserForm(Form):
    """Form for left bar at the user_list view."""

    user = AutoCompleteSelectField(
        LOOKUPS['asset_user'],
        required=False,
    )
