#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Asset management models."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from collections import namedtuple
from dateutil.relativedelta import relativedelta
from itertools import chain
import datetime
import ipaddr
import logging
import os
import re
import urllib

from django.db import models as db
from django.utils.translation import ugettext_lazy as _
from lck.django.common.models import (
    MACAddressField,
    SavePrioritized,
    TimeTrackable,
    WithConcurrentGetOrCreate,
)
from lck.django.choices import Choices
from django.utils.html import escape
from polymorphic import PolymorphicModel

from dj.choices import Country
from django.contrib.auth.models import User
from lck.django.choices import Choices
from lck.django.common import nested_commit_on_success
from lck.django.common.models import (
    EditorTrackable,
    Named,
    SoftDeletable,
    TimeTrackable,
    WithConcurrentGetOrCreate,
    ViewableSoftDeletableManager,
)

from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.template import Context, Template
from django.utils.translation import ugettext_lazy as _


from ralph_assets.history.models import HistoryMixin
from ralph_assets.history.utils import field_changes
from ralph_assets.models_util import (
    Regionalized,
    RegionalizedDBManager,
)
from ralph_assets.utils import iso2_to_iso3
from ralph_assets.models_dc_assets import (  # noqa
    DataCenter,
    Orientation,
    Rack,
    ServerRoom,
    VALID_SLOT_NUMBER_FORMAT
)
from ralph_assets.models_util import SavingUser, LastSeen
from ralph.cmdb.models_ci import CI
from ralph.business.models import PuppetVenture, PuppetVentureRole

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.core.urlresolvers import reverse
from django.core.cache import cache
from django.utils.translation import ugettext_lazy as _
from lck.django.common.models import (
    TimeTrackable, Named, WithConcurrentGetOrCreate, SavePrioritized,
)
import ralph.networks.utils as network

from datetime import datetime
from ralph.scan.models import ScanSummary

logger = logging.getLogger(__name__)


SAVE_PRIORITY = 0
ASSET_HOSTNAME_TEMPLATE = getattr(settings, 'ASSET_HOSTNAME_TEMPLATE', None)
if not ASSET_HOSTNAME_TEMPLATE:
    raise ImproperlyConfigured('"ASSET_HOSTNAME_TEMPLATE" must be specified.')
HOSTNAME_FIELD_HELP_TIP = getattr(settings, 'HOSTNAME_FIELD_HELP_TIP', '')

REPORT_LANGUAGES = getattr(settings, 'REPORT_LANGUAGES', None)

MAC_PREFIX_BLACKLIST = set([
    '505054', '33506F', '009876', '000000', '00000C', '204153', '149120',
    '020054', 'FEFFFF', '1AF920', '020820', 'DEAD2C', 'FEAD4D',
])
CPU_CORES = {
    '5160': 2,
    'E5320': 4,
    'E5430': 4,
    'E5504': 4,
    'E5506': 4,
    'E5520': 4,
    'E5540': 4,
    'E5630': 4,
    'E5620': 4,
    'E5640': 4,
    'E5645': 6,
    'E5649': 6,
    'L5520': 4,
    'L5530': 4,
    'L5420': 4,
    'L5630': 4,
    'X5460': 4,
    'X5560': 4,
    'X5570': 4,
    'X5650': 6,
    'X5660': 6,
    'X5670': 6,
    'E5-2640': 6,
    'E5-2670': 8,
    'E5-2630': 6,
    'E5-2650': 8,
    'E7-8837': 8,
    'E7- 8837': 8,
    'E7-4870': 10,
    'E7- 4870': 10,
    'Processor 275': 2,
    'Processor 8216': 2,
    'Processor 6276': 16,
    'Dual-Core': 2,
    'Quad-Core': 4,
    'Six-Core': 6,
    '2-core': 2,
    '4-core': 4,
    '6-core': 6,
    '8-core': 8,
}
CPU_VIRTUAL_LIST = {
    'bochs',
    'qemu',
    'virtual',
    'vmware',
    'xen',
}


class CreatableFromString(object):
    """Simple objects that can be created from string."""

    @classmethod  # Decided not to play with abstractclassmethods
    def create_from_string(cls, asset_type, string_name):
        raise NotImplementedError


class Service(Named, TimeTrackable, CreatableFromString):
    # Fixme: let's do service catalog replacement from that
    profit_center = models.CharField(max_length=1024, blank=True)
    cost_center = models.CharField(max_length=1024, blank=True)

    @classmethod
    def create_from_string(cls, string_name, *args, **kwargs):
        return cls(name=string_name)


class DeviceEnvironment(Named, TimeTrackable, CreatableFromString):
    service = models.ForeignKey(Service)


# Base object for non-assets models like Databases, and others.
class BaseItem(SavingUser):
    name = models.CharField(verbose_name=_("name"), max_length=255)
    # puppet_venture = models.ForeignKey(
    #     "business.PuppetVenture",
    #     verbose_name=_("venture"),
    #     null=True,
    #     blank=True,
    #     default=None,
    #     on_delete=models.SET_NULL,
    # )
    service = models.ForeignKey(
        Service,
        default=None,
        null=True,
        on_delete=db.PROTECT,
    )
    device_environment = models.ForeignKey(
        DeviceEnvironment,
        default=None,
        null=True,
        on_delete=db.PROTECT,
    )

    class Meta:
        abstract = True
        ordering = ('name',)


def _replace_empty_with_none(obj, fields):
    # XXX: replace '' with None, because null=True on model doesn't work
    for field in fields:
        value = getattr(obj, field, None)
        if value == '':
            setattr(obj, field, None)


def get_user_iso3_country_name(user):
    """
    :param user: instance of django.contrib.auth.models.User which has profile
        with country attribute
    """
    country_name = Country.name_from_id(user.get_profile().country).upper()
    iso3_country_name = iso2_to_iso3[country_name]
    return iso3_country_name


class AttachmentMixin(object):

    def latest_attachments(self):
        attachments = self.attachments.all().order_by('-created')
        for attachment in attachments:
            yield attachment



class Sluggy(models.Model):
    """An object with a unique slug."""

    class Meta:
        abstract = True

    slug = models.SlugField(
        max_length=100,
        unique=True,
        blank=True,
        primary_key=True
    )


class LicenseType(Choices):
    _ = Choices.Choice
    not_applicable = _("not applicable")
    oem = _("oem")
    box = _("box")


class AssetType(Choices):
    _ = Choices.Choice

    DC = Choices.Group(0)
    data_center = _("data center")

    BO = Choices.Group(100)
    back_office = _("back office")
    administration = _("administration")

    OTHER = Choices.Group(200)
    other = _("other")


MODE2ASSET_TYPE = {
    'dc': AssetType.data_center,
    'back_office': AssetType.back_office,
    'administration': AssetType.administration,
    'other': AssetType.other,
}


ASSET_TYPE2MODE = {v: k for k, v in MODE2ASSET_TYPE.items()}


class AssetPurpose(Choices):
    _ = Choices.Choice

    for_contractor = _("for contractor")
    sectional = _("sectional")
    for_dashboards = _("for dashboards")
    for_events = _("for events")
    for_tests = _("for tests")
    others = _("others")


class AssetStatus(Choices):
    _ = Choices.Choice

    HARDWARE = Choices.Group(0)
    new = _("new")
    in_progress = _("in progress")
    waiting_for_release = _("waiting for release")
    used = _("in use")
    loan = _("loan")
    damaged = _("damaged")
    liquidated = _("liquidated")
    in_service = _("in service")
    in_repair = _("in repair")
    ok = _("ok")
    to_deploy = _("to deploy")

    SOFTWARE = Choices.Group(100)
    installed = _("installed")
    free = _("free")
    reserved = _("reserved")

    @classmethod
    def _filter_status(cls, asset_type, required=True):
        """
        Filter choices depending on 2 things:

            1. defined ASSET_STATUSES in settings (if not defined returns all
                statuses)
            2. passed *asset_type* (which is one of keys from ASSET_STATUSES)

        :param required: prepends empty value to choices
        """
        customized = getattr(settings, 'ASSET_STATUSES', None)
        found = [] if required else [('', '----')]
        if not customized:
            found.extend(AssetStatus())
            return found
        for key in customized[asset_type]:
            try:
                choice = getattr(AssetStatus, key)
            except AttributeError:
                msg = ("No such choice {!r} in AssetStatus"
                       " - check settings").format(key)
                raise Exception(msg)
            found.append((choice.id, unicode(choice)))
        return found

    @classmethod
    def data_center(cls, required):
        return AssetStatus._filter_status('data_center', required)

    @classmethod
    def back_office(cls, required):
        return AssetStatus._filter_status('back_office', required)


class AssetSource(Choices):
    _ = Choices.Choice

    shipment = _("shipment")
    salvaged = _("salvaged")


class AssetCategoryType(Choices):
    _ = Choices.Choice

    back_office = _("back office")
    data_center = _("data center")


class ModelVisualizationLayout(Choices):
    _ = Choices.Choice

    na = _('N/A')
    layout_1x2 = _('1x2').extra(css_class='rows-1 cols-2')
    layout_2x8 = _('2x8').extra(css_class='rows-2 cols-8')
    layout_2x8AB = _('2x16 (A/B)').extra(css_class='rows-2 cols-8 half-slots')
    layout_4x2 = _('4x2').extra(css_class='rows-4 cols-2')


class AssetManufacturer(
    CreatableFromString,
    TimeTrackable,
    EditorTrackable,
    Named
):
    def __unicode__(self):
        return self.name

    @classmethod
    def create_from_string(cls, asset_type, string_name):
        return cls(name=string_name)


class AssetModel(
    CreatableFromString,
    TimeTrackable,
    EditorTrackable,
    Named.NonUnique,
    WithConcurrentGetOrCreate
):
    '''
    Asset models describing hardware and contain standard information like
    created at
    '''
    manufacturer = models.ForeignKey(
        AssetManufacturer, on_delete=db.PROTECT, blank=True, null=True)
    category = models.ForeignKey(
        'AssetCategory', null=True, related_name='models'
    )
    power_consumption = models.IntegerField(
        verbose_name=_("Power consumption"),
        blank=True,
        default=0,
    )
    height_of_device = models.FloatField(
        verbose_name=_("Height of device"),
        blank=True,
        default=0,
    )
    cores_count = models.IntegerField(
        verbose_name=_("Cores count"),
        blank=True,
        default=0,
    )
    visualization_layout_front = models.PositiveIntegerField(
        verbose_name=_("visualization layout of front side"),
        choices=ModelVisualizationLayout(),
        default=ModelVisualizationLayout().na.id,
        blank=True,
    )
    visualization_layout_back = models.PositiveIntegerField(
        verbose_name=_("visualization layout of back side"),
        choices=ModelVisualizationLayout(),
        default=ModelVisualizationLayout().na.id,
        blank=True,
    )
    type = models.PositiveIntegerField(choices=AssetType(), null=True)

    def __unicode__(self):
        return "%s %s" % (self.manufacturer, self.name)

    @classmethod
    def create_from_string(cls, asset_type, string_name):
        return cls(type=asset_type, name=string_name)

    def _get_layout_class(self, field):
        item = ModelVisualizationLayout.from_id(field)
        return getattr(item, 'css_class', '')

    def get_front_layout_class(self):
        return self._get_layout_class(self.visualization_layout_front)

    def get_back_layout_class(self):
        return self._get_layout_class(self.visualization_layout_back)


class AssetOwner(
    TimeTrackable, Named, WithConcurrentGetOrCreate, CreatableFromString,
):
    """The company or other entity that are owners of assets."""

    @classmethod
    def create_from_string(cls, string_name, *args, **kwargs):
        return cls(name=string_name)


class AssetCategory(
    MPTTModel,
    TimeTrackable,
    EditorTrackable,
    WithConcurrentGetOrCreate,
    Sluggy,
):
    name = models.CharField(max_length=50, unique=False)
    type = models.PositiveIntegerField(
        verbose_name=_("type"), choices=AssetCategoryType(),
    )
    code = models.CharField(max_length=4, blank=True, default='')
    is_blade = models.BooleanField()
    parent = TreeForeignKey(
        'self',
        null=True,
        blank=True,
        related_name='children',
    )

    class MPTTMeta:
        order_insertion_by = ['name']

    class Meta:
        verbose_name = _("Asset category")
        verbose_name_plural = _("Asset categories")

    def __unicode__(self):
        return self.name


class Warehouse(
    TimeTrackable,
    EditorTrackable,
    Named,
    WithConcurrentGetOrCreate,
    CreatableFromString,
):
    def __unicode__(self):
        return self.name

    @classmethod
    def create_from_string(cls, asset_type, string_name):
        return cls(name=string_name)


def _get_file_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = "%s.%s" % (uuid4(), ext)
    return os.path.join('assets', filename)


# class BOAdminManager(models.Manager):
#     def get_query_set(self):
#         return super(BOAdminManager, self).get_query_set().filter(
#             type__in=(AssetType.BO.choices)
#         )


# class DCAdminManager(models.Manager):
#     def get_query_set(self):
#         return super(DCAdminManager, self).get_query_set().filter(
#             type__in=(AssetType.DC.choices)
#         )


class AssetAdminManager(RegionalizedDBManager):
    pass


# class BOManager(
#     BOAdminManager, ViewableSoftDeletableManager, RegionalizedDBManager
# ):
#     pass


# class DCManager(
#     DCAdminManager, ViewableSoftDeletableManager, RegionalizedDBManager
# ):
#     pass


class Attachment(SavingUser, TimeTrackable):
    original_filename = models.CharField(max_length=255, unique=False)
    file = models.FileField(upload_to=_get_file_path, blank=False, null=True)
    uploaded_by = models.ForeignKey(User, null=True, blank=True)

    def save(self, *args, **kwargs):
        filename = getattr(self.file, 'name') or 'unknown'
        self.original_filename = filename
        super(Attachment, self).save(*args, **kwargs)



class BudgetInfo(
    TimeTrackable,
    EditorTrackable,
    Named,
    WithConcurrentGetOrCreate,
    CreatableFromString,
):
    """
    Info pointing source of money (budget) for *assets* and *licenses*.
    """
    def __unicode__(self):
        return self.name

    @classmethod
    def create_from_string(cls, asset_type, string_name):
        return cls(name=string_name)


class AssetLastHostname(models.Model):
    prefix = models.CharField(max_length=8, db_index=True)
    counter = models.PositiveIntegerField(default=1)
    postfix = models.CharField(max_length=8, db_index=True)

    class Meta:
        unique_together = ('prefix', 'postfix')

    def __unicode__(self):
        return self.formatted_hostname()

    def formatted_hostname(self, fill=5):
        return '{prefix}{counter:0{fill}}{postfix}'.format(
            prefix=self.prefix,
            counter=int(self.counter),
            fill=fill,
            postfix=self.postfix,
        )

    @classmethod
    def increment_hostname(cls, prefix, postfix=''):
        obj, created = cls.objects.get_or_create(
            prefix=prefix,
            postfix=postfix,
        )
        if not created:
            # F() avoid race condition problem
            obj.counter = models.F('counter') + 1
            obj.save()
            return cls.objects.get(pk=obj.pk)
        else:
            return obj


class Gap(object):
    """A placeholder that represents a gap in a blade chassis"""

    id = 0
    barcode = '-'
    sn = '-'
    service = namedtuple('Service', ['name'])('-')
    model = namedtuple('Model', ['name'])('-')
    linked_device = None

    def __init__(self, slot_no, orientation):
        self.slot_no = slot_no
        self.orientation = orientation

    def get_absolute_url(self):
        return ''

    # @property
    # def device_info(self):
    #     return namedtuple('DeviceInfo', [
    #         'slot_no', 'get_orientation_desc'
    #     ])(
    #         self.slot_no, None, lambda: self.orientation
    #     )

    @classmethod
    def generate_gaps(cls, items):
        def get_number(slot_no):
            """Returns the integer part of slot number"""
            m = re.match('(\d+)', slot_no)
            return (m and int(m.group(0))) or 0
        if not items:
            return []
        max_slot_no = max([
            get_number(asset.device_info.slot_no)
            for asset in items
        ])
        first_asset_slot_no = items[0].device_info.slot_no
        ab = first_asset_slot_no and first_asset_slot_no[-1] in {'A', 'B'}
        slot_nos = {asset.device_info.slot_no for asset in items}

        def handle_missing(slot_no):
            if slot_no not in slot_nos:
                items.append(Gap(slot_no, items[0].get_orientation_desc()))

        for slot_no in xrange(1, max_slot_no + 1):
            if ab:
                for letter in ['A', 'B']:
                    handle_missing(str(slot_no) + letter)
            else:
                handle_missing(str(slot_no))
        return items



# class Service(db.Object):
#     """
#     """
#     name = db.CharField()

#     def __unicode__(self):
#         return self.name

#     def get_environments(self):
#         env_ids_from_service = CIRelation.objects.filter(
#             parent=self.id,
#         ).values('child__id')
#         envs = DeviceEnvironment.objects.filter(id__in=env_ids_from_service)
#         return envs


# class Environment(db.Object):
#     pass


class Asset(
    AttachmentMixin,
    Regionalized,
    HistoryMixin,
    TimeTrackable,
    EditorTrackable,
    SavingUser,
    SoftDeletable,
    LastSeen,
    PolymorphicModel
):
    '''
    Asset model contain fields with basic information about single asset
    '''
    # device_info = models.OneToOneField(
        # 'DeviceInfo', null=True, blank=True, on_delete=models.CASCADE,
    # )
    # part_info = models.OneToOneField(
        # 'PartInfo', null=True, blank=True, on_delete=models.CASCADE,
    # )
    # office_info = models.OneToOneField(
        # 'OfficeInfo', null=True, blank=True, on_delete=models.CASCADE,
    # )
    # type = models.PositiveSmallIntegerField(choices=AssetType())
    model = models.ForeignKey(
        'AssetModel', on_delete=db.PROTECT, related_name='assets',
    )
    source = models.PositiveIntegerField(
        verbose_name=_("source"), choices=AssetSource(), db_index=True,
        null=True, blank=True,
    )
    invoice_no = models.CharField(
        max_length=128, db_index=True, null=True, blank=True,
    )
    order_no = models.CharField(max_length=50, null=True, blank=True)
    purchase_order = models.CharField(max_length=50, null=True, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    sn = models.CharField(max_length=200, null=True, blank=True, unique=True)
    barcode = models.CharField(
        max_length=200, null=True, blank=True, unique=True, default=None,
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, blank=True, null=True,
    )
    support_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    support_period = models.PositiveSmallIntegerField(
        blank=True,
        default=0,
        null=True,
        verbose_name="support period in months"
    )
    support_type = models.CharField(max_length=150, blank=True)
    support_void_reporting = models.BooleanField(default=True, db_index=True)
    provider = models.CharField(max_length=100, null=True, blank=True)
    status = models.PositiveSmallIntegerField(
        default=AssetStatus.new.id,
        verbose_name=_("status"),
        choices=AssetStatus(),
        null=True,
        blank=True,
    )
    remarks = models.CharField(
        verbose_name='Additional remarks',
        max_length=1024,
        blank=True,
    )
    niw = models.CharField(
        max_length=200, null=True, blank=True, default=None,
        verbose_name='Inventory number',
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=db.PROTECT)
    location = models.CharField(max_length=128, null=True, blank=True)
    request_date = models.DateField(null=True, blank=True)
    delivery_date = models.DateField(null=True, blank=True)
    production_use_date = models.DateField(null=True, blank=True)
    provider_order_date = models.DateField(null=True, blank=True)
    deprecation_rate = models.DecimalField(
        decimal_places=2,
        max_digits=5,
        blank=True,
        default=settings.DEFAULT_DEPRECATION_RATE,
        help_text=_(
            'This value is in percentage.'
            ' For example value: "100" means it depreciates during a year.'
            ' Value: "25" means it depreciates during 4 years, and so on... .'
        ),
    )
    force_deprecation = models.BooleanField(help_text=(
        'Check if you no longer want to bill for this asset'
    ))
    deprecation_end_date = models.DateField(null=True, blank=True)
    production_year = models.PositiveSmallIntegerField(null=True, blank=True)
    slots = models.FloatField(
        verbose_name='Slots',
        help_text=('For blade centers: the number of slots available in this '
                   'device. For blade devices: the number of slots occupied.'),
        max_length=64,
        default=0,
    )
    #service_name = models.ForeignKey(Service, null=True, blank=True)
    admin_objects = AssetAdminManager()
    # admin_objects_dc = DCAdminManager()
    # admin_objects_bo = BOAdminManager()
    # objects_dc = DCManager()
    # objects_bo = BOManager()
    task_url = models.URLField(
        max_length=2048, null=True, blank=True, unique=False,
        help_text=('External workflow system URL'),
    )
    property_of = models.ForeignKey(
        AssetOwner,
        on_delete=db.PROTECT,
        null=True,
        blank=True,
    )
    owner = models.ForeignKey(
        User, null=True, blank=True, related_name="owner",
    )
    user = models.ForeignKey(
        User, null=True, blank=True, related_name="user",
    )
    attachments = models.ManyToManyField(
        Attachment,
        null=True,
        blank=True,
        related_name='parents',
    )
    loan_end_date = models.DateField(
        null=True, blank=True, default=None, verbose_name=_('Loan end date'),
    )
    note = models.CharField(
        verbose_name=_('Note'),
        max_length=1024,
        blank=True,
    )
    budget_info = models.ForeignKey(
        BudgetInfo,
        blank=True,
        default=None,
        null=True,
        on_delete=db.PROTECT,
    )
    hostname = models.CharField(
        blank=True,
        default=None,
        max_length=16,
        null=True,
        unique=True,
        help_text=HOSTNAME_FIELD_HELP_TIP,
    )
    required_support = models.BooleanField(default=False)
    service = models.ForeignKey(
        Service,
        default=None,
        null=True,
        on_delete=db.PROTECT,
    )
    device_environment = models.ForeignKey(
        DeviceEnvironment,
        default=None,
        null=True,
        on_delete=db.PROTECT,
    )

    #class Meta:
        # it can't be abstract, since Component(both DC and BO) has foreign key to Asset
        # but it doesn't matter.

    def __unicode__(self):
        return "{} - {} - {}".format(self.model, self.sn, self.barcode)

    # @property
    # def linked_device(self):
    #     try:
    #         device = self.device_info.get_ralph_device()
    #     except AttributeError:
    #         device = None
    #     return device

    @property
    def venture(self):
        return None
        # try:
        #     return self.get_ralph_device().venture
        # except AttributeError:
        #     return None

    @property
    def cores_count(self):
        """Returns cores count assigned to device in Ralph"""
        asset_cores_count = self.model.cores_count if self.model else 0
        # if settings.SHOW_RALPH_CORES_DIFF:
            # device_cores_count = None
            # try:
                # if self.device_info and self.device_info.ralph_device_id:
                    # device_cores_count = Device.objects.get(
                        # pk=self.device_info.ralph_device_id,
                    # ).get_core_count()
            # except Device.DoesNotExist:
                # pass
            # if (device_cores_count is not None and
            #    asset_cores_count != device_cores_count):
            #     logger.warning(
            #         ('Cores count for <{}> different in ralph than '
            #          'in assets ({} vs {})').format(
            #             self,
            #             device_cores_count,
            #             asset_cores_count,
            #         )
            #     )
        return asset_cores_count

    # @classmethod
    # def create(cls, base_args, device_info_args=None, part_info_args=None):
    #     asset = Asset(**base_args)
    #     if device_info_args:
    #         d = DeviceInfo(**device_info_args)
    #         d.save()
    #         asset.device_info = d
    #     elif part_info_args:
    #         d = PartInfo(**part_info_args)
    #         d.save()
    #         asset.part_info = d
    #     asset.save()
    #     return asset

    def get_data_type(self):
        # FIXME - merge part management
        return 'device'
    #     if self.part_info:
    #         return 'part'
    #     else:
    #         return 'device'

    def _try_assign_hostname(self, commit):
        if self.owner and self.model.category and self.model.category.code:
            template_vars = {
                'code': self.model.category.code,
                'country_code': self.country_code,
            }
            if not self.hostname:
                self.generate_hostname(commit, template_vars)
            else:
                user_country = get_user_iso3_country_name(self.owner)
                different_country = user_country not in self.hostname
                if different_country:
                    self.generate_hostname(commit, template_vars)

    # def get_ralph_device(self):
    #     if not self.device_info or not self.device_info.ralph_device_id:
    #         return None
    #     try:
    #         return Device.objects.get(
    #             pk=self.device_info.ralph_device_id,
    #         )
    #     except Device.DoesNotExist:
    #         return None

    @property
    def exists(self):
        """Check if object is a new db record"""
        return self.pk is not None

    # def handle_device_linkage(self, force_unlink):
    #     """When try to match it with an existing device or create a dummy
    #     (stock) device and then match with it instead.
    #     Note: it does not apply to assets created with 'add part' button.

    #     Cases:
    #     when adding asset:
    #         no barcode -> add asset + create dummy device
    #         set barcode from unlinked device -> add asset + link device
    #         set barcode from linked device -> error
    #         set barcode from linked device + force unlink -> add + relink

    #     when editing asset:
    #         do nothing
    #     """
    #     try:
    #         ralph_device_id = self.device_info.ralph_device_id
    #     except AttributeError:
    #         # asset created with 'add part'
    #         pass
    #     else:
    #         if not self.exists:
    #             if not ralph_device_id:
    #                 device = self.find_device_to_link()
    #                 if device:
    #                     if force_unlink:
    #                         asset = device.get_asset()
    #                         asset.device_info.ralph_device_id = None
    #                         asset.device_info.save()
    #                     self.device_info.ralph_device_id = device.id
    #                     self.device_info.save()
    #                 else:
    #                     self.create_stock_device()

    def save(self, commit=True, force_unlink=False, *args, **kwargs):
        _replace_empty_with_none(self, ['source', 'hostname'])
        # self.handle_device_linkage(force_unlink)
        return super(Asset, self).save(commit=commit, *args, **kwargs)

    def get_data_icon(self):
        # FIXME:
        return 'fugue-computer'
        # if self.get_data_type() == 'device':
            # return 'fugue-computer'
        # elif self.get_data_type() == 'part':
            # return 'fugue-box'
        # else:
            # raise UserWarning('Unknown asset data type!')

    # @property
    # def type_is_data_center(self):
        # return self.type == AssetType.data_center

    # def find_device_to_link(self):
    #     if not self.type_is_data_center or (not self.barcode and not self.sn):
    #         return None
    #     device = None
    #     if self.barcode:
    #         try:
    #             device = Device.objects.get(barcode=self.barcode)
    #         except Device.DoesNotExist:
    #             pass
    #     if not device and self.sn:
    #         try:
    #             device = Device.objects.get(sn=self.sn)
    #         except Device.DoesNotExist:
    #             device = None
    #     return device

    # def create_stock_device(self):
    #     if not self.type_is_data_center:
    #         return
    #     if not self.device_info.ralph_device_id:
    #         try:
    #             venture = Venture.objects.get(name='Stock')
    #         except Venture.DoesNotExist:
    #             venture = Venture(name='Stock', symbol='stock')
    #             venture.save()
    #         device = Device.create(
    #             sn=self.sn or 'bc-' + self.barcode,
    #             barcode=self.barcode,
    #             model_name='Unknown',
    #             model_type=DeviceType.unknown,
    #             priority=SAVE_PRIORITY,
    #             venture=venture,
    #         )
    #         device.name = getattr(self.model, 'name', 'Unknown')
    #         device.remarks = self.order_no or ''
    #         device.dc = getattr(self.warehouse, 'name', '')
    #         device.save()
    #         self.device_info.ralph_device_id = device.id
    #         self.device_info.save()

    def get_parts_info(self):
        return PartInfo.objects.filter(device=self)

    def get_parts(self):
        return Asset.objects.filter(part_info__device=self)

    def has_parts(self):
        return PartInfo.objects.filter(device=self).exists()

    def __init__(self, *args, **kwargs):
        self.save_comment = None
        self.saving_user = None
        super(Asset, self).__init__(*args, **kwargs)

    def get_deprecation_months(self):
        return int(
            (1 / (self.deprecation_rate / 100) * 12)
            if self.deprecation_rate else 0
        )

    def is_deprecated(self, date=None):
        date = date or datetime.date.today()
        if self.force_deprecation or not self.invoice_date:
            return True
        if self.deprecation_end_date:
            deprecation_date = self.deprecation_end_date
        else:
            deprecation_date = self.invoice_date + relativedelta(
                months=self.get_deprecation_months(),
            )
        return deprecation_date < date

    def is_liquidated(self, date=None):
        date = date or datetime.date.today()
        # check if asset has status 'liquidated' and if yes, check if it has
        # this status on given date
        if self.status == AssetStatus.liquidated and self._liquidated_at(date):
            return True
        return False

    def _liquidated_at(self, date):
        liquidated_history = self.get_history().filter(
            new_value='liquidated',
            field_name='status',
        ).order_by('-date')[:1]
        return liquidated_history and liquidated_history[0].date.date() <= date

    def delete_with_info(self, *args, **kwargs):
        """
        Remove Asset with linked info-tables alltogether, because cascade
        works bottom-up only.
        """
        if self.part_info:
            self.part_info.delete()
        elif self.office_info:
            self.office_info.delete()
        elif self.device_info:
            self.device_info.delete()
        return super(Asset, self).delete(*args, **kwargs)

    @property
    def is_discovered(self):
        return True
        # if self.part_info:
        #     if self.part_info.device:
        #         return self.part_info.device.is_discovered()
        #     return False
        # try:
        #     dev = self.device_info.get_ralph_device()
        # except AttributeError:
        #     return False
        # else:
        #     if not dev or not dev.model:
        #         return False
        #     return dev.model.type != DeviceType.unknown.id

    def get_absolute_url(self):
        return reverse('device_edit', kwargs={
            'mode': 'dc',
            'asset_id': self.id,
        })

    @property
    def country_code(self):
        iso2 = Country.name_from_id(self.owner.profile.country).upper()
        return iso2_to_iso3.get(iso2, 'POL')

    @nested_commit_on_success
    def generate_hostname(self, commit=True, template_vars={}):
        def render_template(template):
            template = Template(template)
            context = Context(template_vars)
            return template.render(context)
        prefix = render_template(
            ASSET_HOSTNAME_TEMPLATE.get('prefix', ''),
        )
        postfix = render_template(
            ASSET_HOSTNAME_TEMPLATE.get('postfix', ''),
        )
        counter_length = ASSET_HOSTNAME_TEMPLATE.get('counter_length', 5)
        last_hostname = AssetLastHostname.increment_hostname(prefix, postfix)
        self.hostname = last_hostname.formatted_hostname(fill=counter_length)
        if commit:
            self.save()

    def get_related_assets(self):
        """Returns the children of a blade chassis"""
        orientations = [Orientation.front, Orientation.back]
        assets_by_orientation = []
        for orientation in orientations:
            assets_by_orientation.append(list(
                Asset.objects.select_related('device_info', 'model').filter(
                    device_info__position=self.device_info.position,
                    device_info__rack=self.device_info.rack,
                    device_info__orientation=orientation,
                ).exclude(id=self.id)
            ))
        assets = [
            Gap.generate_gaps(assets) for assets in assets_by_orientation
        ]
        return chain(*assets)

    def get_orientation_desc(self):
        return self.device_info.get_orientation_desc()

    def get_configuration_url(self):
        # FIXME: what is purpose of this?
        # device = self.get_ralph_device()
        # configuration_url = self.url if device else None
        # return configuration_url
        return ''#self.url

    def get_vizualization_url(self):
        try:
            rack_id, data_center_id = (
                self.device_info.rack.id, self.device_info.rack.data_center.id,
            )
        except AttributeError:
            visualization_url = None
        else:
            prefix = reverse('dc_view')
            postfix = '/dc/{data_center_id}/rack/{rack_id}'.format(
                data_center_id=data_center_id, rack_id=rack_id,
            )
            visualization_url = '#'.join([prefix, postfix])
        return visualization_url


class DCAsset(Asset):
    #, HistoryMixin, TimeTrackable, SavingUser, SoftDeletable):
    # ralph_device_id = models.IntegerField(
    #     verbose_name=_("Ralph device id"),
    #     null=True,
    #     blank=True,
    #     unique=True,
    #     default=None,
    # )
    u_level = models.CharField(max_length=10, null=True, blank=True)
    u_height = models.CharField(max_length=10, null=True, blank=True)
    rack = models.ForeignKey(Rack, null=True, blank=True)
    # deperecated field, use rack instead
    # rack_old = models.CharField(max_length=10, null=True, blank=True)
    slot_no = models.CharField(
        verbose_name=_("slot number"), max_length=3, null=True, blank=True,
        help_text=_('Fill it if asset is blade server'),
    )
    position = models.IntegerField(null=True)
    orientation = models.PositiveIntegerField(
        choices=Orientation(),
        default=Orientation.front.id,
    )

    # Ralph 3.0 --  new fields

    # server blade -> chassis blade
    # virtual -> hypervisor
    # 2 switches -> stacked switch
    # database -> db server - to be discussed
    parent = models.ForeignKey(
        'self',
        verbose_name=_("physical parent device"),
        on_delete=db.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="child_set",
    )
    # logical parent not needed, since rack location the same
    # logical_parent = models.ForeignKey(
    #     'self',
    #     verbose_name=_("logical parent device"),
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     default=None,
    #     related_name="logicalchild_set",
    # )
    connections = models.ManyToManyField(
        'DCAsset',
        through='Connection',
        symmetrical=False,
    )
    # boot_firmware = models.CharField(
    #     verbose_name=_("boot firmware"),
    #     null=True,
    #     blank=True,
    #     max_length=255,
    # )
    # hard_firmware = models.CharField(
    #     verbose_name=_("hardware firmware"),
    #     null=True,
    #     blank=True,
    #     max_length=255,
    # )
    # diag_firmware = models.CharField(
    #     verbose_name=_("diagnostics firmware"),
    #     null=True,
    #     blank=True,
    #     max_length=255,
    # )
    # mgmt_firmware = models.CharField(
    #     verbose_name=_("management firmware"),
    #     null=True,
    #     blank=True,
    #     max_length=255,
    # )

    # Configuration path

    # configuration_path = models.CharField(max_length=10, null=True, blank=True)

    puppet_venture = models.ForeignKey(
        PuppetVenture,
        verbose_name=_("puppet venture"),
        null=True,
        blank=True,
        default=None,
        on_delete=db.SET_NULL,
    )

    puppet_venture_role = models.ForeignKey(
        PuppetVentureRole,
        on_delete=db.SET_NULL,
        verbose_name=_("puppet venture role"),
        null=True,
        blank=True,
        default=None,
    )

    management = models.ForeignKey(
        'IPAddress',
        related_name="managed_set",
        verbose_name=_("management address"),
        null=True,
        blank=True,
        default=None,
        on_delete=db.SET_NULL,
    )

    # verified = models.BooleanField(verbose_name=_("verified"), default=False)


    @property
    def asset_type(self):
        return AssetType.data_center

    def get_absolute_url(self):
        return reverse('device_edit', kwargs={
            'mode': 'dc',
            'asset_id': self.id,
        })

    def clean_fields(self, exclude=None):
        """
        Constraints:
        - picked rack is from picked server-room
        - picked server-room is from picked data-center
        - postion = 0: orientation(left, right)
        - postion > 0: orientation(front, middle, back)
        - position <= rack.max_u_height
        - slot_no: asset is_blade=True
        """
        if self.rack and self.server_room:
            if self.rack.server_room != self.server_room:
                msg = 'This rack is not from picked server room'
                raise ValidationError({'rack': [msg]})
        if self.server_room and self.data_center:
            if self.server_room.data_center != self.data_center:
                msg = 'This server room is not from picked data center'
                raise ValidationError({'server_room': [msg]})
        if self.position == 0 and not Orientation.is_width(self.orientation):
            msg = 'Valid orientations for picked position are: {}'.format(
                ', '.join(
                    choice.desc for choice in Orientation.WIDTH.choices
                )
            )
            raise ValidationError({'orientation': [msg]})
        if self.position > 0 and not Orientation.is_depth(self.orientation):
            msg = 'Valid orientations for picked position are: {}'.format(
                ', '.join(
                    choice.desc for choice in Orientation.DEPTH.choices
                )
            )
            raise ValidationError({'orientation': [msg]})
        if self.rack and self.position > self.rack.max_u_height:
            msg = 'Position is higher than "max u height" = {}'.format(
                self.rack.max_u_height,
            )
            raise ValidationError({'position': [msg]})
        if self.slot_no and not VALID_SLOT_NUMBER_FORMAT.search(self.slot_no):
            msg = ("Slot number should be a number from range 1-16 with "
                   "an optional postfix 'A' or 'B' (e.g. '16A')")
            raise ValidationError({'slot_no': [msg]})

    @property
    def size(self):
        """Deprecated. Kept for backwards compatibility."""
        return 0

    # def __unicode__(self):
    #     return "{} - {}".format(
    #         # self.ralph_device_id,
    #         self.size,
    #     )

    # def get_ralph_device(self):
    #     if not self.ralph_device_id:
    #         return None
    #     try:
    #         dev = Device.objects.get(id=self.ralph_device_id)
    #         return dev
    #     except Device.DoesNotExist:
    #         return None

    def get_orientation_desc(self):
        return Orientation.name_from_id(self.orientation)

    def __init__(self, *args, **kwargs):
        self.save_comment = None
        self.saving_user = None
        super(DCAsset, self).__init__(*args, **kwargs)




class ConnectionType(Choices):
    _ = Choices.Choice

    network = _("network connection")



class UptimeSupport(models.Model):

    """Adds an `uptime` attribute to the model. This attribute is shifted
    by the current time on each get. Returns a timedelta object, accepts
    None, timedelta and int values on set."""

    uptime_seconds = models.PositiveIntegerField(
        verbose_name=_("uptime in seconds"),
        default=0,
    )
    uptime_timestamp = models.DateTimeField(
        verbose_name=_("uptime timestamp"),
        null=True,
        blank=True,
        help_text=_("moment of the last uptime update"),
    )

    class Meta:
        abstract = True

    @property
    def uptime(self):
        if not self.uptime_seconds or not self.uptime_timestamp:
            return None
        return (datetime.datetime.now() - self.uptime_timestamp +
                datetime.timedelta(seconds=self.uptime_seconds))

    @uptime.setter
    def uptime(self, value):
        if not value:
            del self.uptime
            return
        if isinstance(value, datetime.timedelta):
            value = abs(int(value.total_seconds()))
        self.uptime_seconds = value
        self.uptime_timestamp = datetime.datetime.now()

    @uptime.deleter
    def uptime(self):
        self.uptime_seconds = 0
        self.uptime_timestamp = None

    def get_uptime_display(self):
        u = self.uptime
        if not u:
            return _("unknown")
        if u.days == 1:
            msg = _("1 day")
        else:
            msg = _("%d days") % u.days
        hours = int(u.seconds / 60 / 60)
        minutes = int(u.seconds / 60) - 60 * hours
        seconds = int(u.seconds) - 3600 * hours - 60 * minutes
        return "%s, %02d:%02d:%02d" % (msg, hours, minutes, seconds)

class Connection(models.Model):

    outbound = models.ForeignKey(
        DCAsset,
        verbose_name=_("connected to device"),
        on_delete=db.PROTECT,
        related_name='outbound_connections',
    )
    inbound = models.ForeignKey(
        DCAsset,
        verbose_name=_("connected device"),
        on_delete=db.PROTECT,
        related_name='inbound_connections',
    )
    connection_type = models.PositiveIntegerField(
        verbose_name=_("connection type"),
        choices=ConnectionType()
    )

    def __unicode__(self):
        return "%s -> %s (%s)" % (
            self.outbound,
            self.inbound,
            self.connection_type
        )


class NetworkConnection(models.Model):

    connection = models.OneToOneField(
        Connection,
        on_delete=db.CASCADE,
    )
    outbound_port = models.CharField(
        verbose_name=_("outbound port"),
        max_length=100
    )
    inbound_port = models.CharField(
        verbose_name=_("inbound port"),
        max_length=100
    )

    def __unicode__(self):
        return "connection from %s on %s to %s on %s" % (
            self.connection.outbound,
            self.outbound_port,
            self.connection.inbound,
            self.inbound_port
        )


class CoaOemOs(Named):
    """Define oem installed operating system"""


class VirtualAsset(Asset):
    """VMWare virtual system"""
    pass


class BOAsset(Asset):
    #, TimeTrackable, SavingUser, SoftDeletable):
    license_key = models.TextField(null=True, blank=True,)
    coa_number = models.CharField(
        max_length=256, verbose_name="COA number", null=True, blank=True,
    )
    coa_oem_os = models.ForeignKey(
        CoaOemOs, verbose_name="COA oem os", null=True, blank=True,
    )
    imei = models.CharField(
        max_length=18, null=True, blank=True, unique=True
    )
    purpose = models.PositiveSmallIntegerField(
        verbose_name=_("purpose"), choices=AssetPurpose(), null=True,
        blank=True, default=None
    )

    def get_purpose(self):
        return AssetPurpose.from_id(self.purpose).raw if self.purpose else None

    def save(self, commit=True, *args, **kwargs):
        _replace_empty_with_none(self, ['purpose'])
        instance = super(BOAsset, self).save(commit=commit, *args, **kwargs)
        return instance

    def __unicode__(self):
        return "{} - {} - {}".format(
            self.coa_oem_os,
            self.coa_number,
            self.purpose,
            self.imei,
        )

    def __init__(self, *args, **kwargs):
        self.save_comment = None
        self.saving_user = None
        super(BOAsset, self).__init__(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('device_edit', kwargs={
            'mode': 'dc',
            'asset_id': self.id,
        })

    @property
    def asset_type(self):
        return AssetType.back_office


class PartInfo(TimeTrackable, SavingUser, SoftDeletable):
    barcode_salvaged = models.CharField(max_length=200, null=True, blank=True)
    source_device = models.ForeignKey(
        Asset, null=True, blank=True, related_name='source_device'
    )
    device = models.ForeignKey(
        Asset, null=True, blank=True, related_name='device'
    )

    def __unicode__(self):
        return "{} - {}".format(self.device, self.barcode_salvaged)

    def __init__(self, *args, **kwargs):
        self.save_comment = None
        self.saving_user = None
        super(PartInfo, self).__init__(*args, **kwargs)


class ReportOdtSource(Named, SavingUser, TimeTrackable):
    slug = models.SlugField(max_length=100, unique=True, blank=False)

    @property
    def template(self):
        "Return first template - it's only for backward compatibility."
        return self.templates[0].template

    @property
    def templates(self):
        return self.odt_templates.all() if self.odt_templates.count() else []


class ReportOdtSourceLanguage(SavingUser, TimeTrackable):
    template = models.FileField(upload_to=_get_file_path, blank=False)
    language = models.CharField(max_length=3, **REPORT_LANGUAGES)
    report_odt_source = models.ForeignKey(
        ReportOdtSource,
        related_name='odt_templates',
    )

    class Meta:
        unique_together = ('language', 'report_odt_source')

    @property
    def slug(self):
        return self.report_odt_source.slug


@receiver(pre_save, sender=Asset, dispatch_uid='ralph_assets.views.device')
def device_hostname_assigning(sender, instance, raw, using, **kwargs):
    """A hook for assigning ``hostname`` value when an asset is edited."""
    if getattr(settings, 'ASSETS_AUTO_ASSIGN_HOSTNAME', None):
        for field, orig, new in field_changes(instance):
            status_desc = AssetStatus.in_progress.desc
            if all((
                field == 'status', orig != status_desc, new == status_desc
            )):
                instance._try_assign_hostname(commit=False)





def cores_from_model(model_name):
    for name, cores in CPU_CORES.iteritems():
        if name in model_name:
            return cores
    return 0


def is_mac_valid(eth):
    try:
        mac = MACAddressField.normalize(eth.mac)
        if not mac:
            return False
        for black in MAC_PREFIX_BLACKLIST:
            if mac.startswith(black):
                return False
        return True
    except ValueError:
        return False


def is_virtual_cpu(family):
    family = family.lower()
    return any(virtual in family for virtual in CPU_VIRTUAL_LIST)


class EthernetSpeed(Choices):
    _ = Choices.Choice

    s10mbit = _("10 Mbps")
    s100mbit = _("100 Mbps")
    s1gbit = _("1 Gbps")
    s10gbit = _("10 Gbps")

    UNKNOWN_GROUP = Choices.Group(10)
    unknown = _("unknown speed")


class ComponentType(Choices):
    _ = Choices.Choice

    processor = _("processor")
    memory = _("memory")
    disk = _("disk drive")
    ethernet = _("ethernet card")
    expansion = _("expansion card")
    fibre = _("fibre channel card")
    share = _("disk share")
    unknown = _("unknown")
    management = _("management")
    power = _("power module")
    cooling = _("cooling device")
    media = _("media tray")
    chassis = _("chassis")
    backup = _("backup")
    software = _("software")
    os = _('operating system')


class ComponentModel(SavePrioritized, WithConcurrentGetOrCreate, SavingUser):
    name = db.CharField(verbose_name=_("name"), max_length=255)
    speed = db.PositiveIntegerField(
        verbose_name=_("speed (MHz)"),
        default=0,
        blank=True,
    )
    cores = db.PositiveIntegerField(
        verbose_name=_("number of cores"),
        default=0,
        blank=True,
    )
    size = db.PositiveIntegerField(
        verbose_name=_("size (MiB)"),
        default=0,
        blank=True,
    )
    type = db.PositiveIntegerField(
        verbose_name=_("component type"),
        choices=ComponentType(),
        default=ComponentType.unknown.id,
    )
    family = db.CharField(blank=True, default='', max_length=128)

    class Meta:
        unique_together = ('speed', 'cores', 'size', 'type', 'family')
        verbose_name = _("component model")
        verbose_name_plural = _("component models")

    def __unicode__(self):
        return self.name

    @classmethod
    def concurrent_get_or_create(cls, *args, **kwargs):
        raise AssertionError(
            "Direct usage of this method on ComponentModel is forbidden."
        )

    @classmethod
    def create(cls, type, priority, **kwargs):
        """More robust API for concurrent_get_or_create. All arguments should
        be given flat.

        Required arguments: type; priority; family (for processors and disks)

        Forbidden arguments: name (for memory and disks)

        All other arguments are optional and sensible defaults are given. For
        each ComponentModel type a minimal sensible set of arguments should be
        given.

        name is truncated to 50 characters.
        """

        # sanitize None, 0 and empty strings
        kwargs = {
            name: kwargs[name]
            for name in ('speed', 'cores', 'size', 'family', 'name')
            if name in kwargs and kwargs[name]
        }
        # put sensible empty values
        kwargs.setdefault('speed', 0)
        kwargs.setdefault('cores', 0)
        kwargs.setdefault('size', 0)
        kwargs['type'] = type or ComponentType.unknown
        family = kwargs.setdefault('family', '')
        if kwargs['type'] == ComponentType.memory:
            assert 'name' not in kwargs, "Custom `name` forbidden for memory."
            name = ' '.join(['RAM', family])
            if kwargs['size']:
                name += ' %dMiB' % int(kwargs['size'])
            if kwargs['speed']:
                name += ', %dMHz' % int(kwargs['speed'])
        elif kwargs['type'] == ComponentType.disk:
            assert 'name' not in kwargs, "Custom `name` forbidden for disks."
            assert family, "`family` not given (required for disks)."
            name = family
            if kwargs['size']:
                name += ' %dMiB' % int(kwargs['size'])
            if kwargs['speed']:
                name += ', %dRPM' % int(kwargs['speed'])
        else:
            name = kwargs.pop('name', family)
        kwargs.update({
            'name': name[:50],
        })
        if kwargs['type'] == ComponentType.processor:
            assert family, "`family` not given (required for CPUs)."
            kwargs['cores'] = max(
                1,
                kwargs['cores'],
                cores_from_model(name) if not is_virtual_cpu(family) else 1,
            )
            kwargs['size'] = kwargs['cores']
        try:
            unique_args = {
                name: kwargs[name]
                for name in ('speed', 'cores', 'size', 'type', 'family')
            }
            obj = cls.objects.get(**unique_args)
            return obj, False
        except cls.DoesNotExist:
            obj = cls(**kwargs)
            obj.save(priority=priority)
            return obj, True

    def get_count(self):
        return sum([
            self.storage_set.count(),
            self.memory_set.count(),
            self.processor_set.count(),
            self.diskshare_set.count(),
            self.fibrechannel_set.count(),
            self.genericcomponent_set.count(),
            self.software_set.count(),
            self.operatingsystem_set.count(),
        ])

    def get_json(self):
        return {
            'id': 'C%d' % self.id,
            'name': escape(self.name or ''),
            'family': escape(self.family or ''),
            'speed': self.speed,
            'size': self.size,
            'cores': self.cores,
            'count': self.get_count()
        }

    def is_software(self):
        return True if self.type == ComponentType.software else False


class Component(SavePrioritized, WithConcurrentGetOrCreate):
    asset = db.ForeignKey('Asset', verbose_name=_("asset"))
    model = db.ForeignKey(
        ComponentModel,
        verbose_name=_("model"),
        null=True,
        blank=True,
        default=None,
        on_delete=db.SET_NULL,
    )

    class Meta:
        abstract = True

    def get_size(self):
        if self.model and self.model.size:
            return self.model.size
        return getattr(self, 'size', 0) or 0


class GenericComponent(Component):
    label = db.CharField(
        verbose_name=_("name"), max_length=255, blank=True,
        null=True, default=None,
    )
    sn = db.CharField(
        verbose_name=_("vendor SN"), max_length=255, unique=True, null=True,
        blank=True, default=None,
    )
    # boot_firmware = db.CharField(
    #     verbose_name=_("boot firmware"), null=True, blank=True, max_length=255,
    # )
    # hard_firmware = db.CharField(
    #     verbose_name=_("hardware firmware"), null=True, blank=True,
    #     max_length=255,
    # )
    # diag_firmware = db.CharField(
    #     verbose_name=_("diagnostics firmware"), null=True, blank=True,
    #     max_length=255,
    # )
    # mgmt_firmware = db.CharField(
    #     verbose_name=_("management firmware"), null=True, blank=True,
    #     max_length=255,
    # )

    class Meta:
        verbose_name = _("generic component")
        verbose_name_plural = _("generic components")

    def __unicode__(self):
        if self.model:
            return "{} ({}): {} {}".format(
                self.label, self.sn, self.model, self.model.get_type_display(),
            )
        return "{} ({})".format(self.label, self.sn)


class DiskShare(Component):
    share_id = db.PositiveIntegerField(
        verbose_name=_("share identifier"), null=True, blank=True,
    )
    label = db.CharField(
        verbose_name=_("name"), max_length=255, blank=True, null=True,
        default=None,
    )
    size = db.PositiveIntegerField(
        verbose_name=_("size (MiB)"), null=True, blank=True,
    )
    snapshot_size = db.PositiveIntegerField(
        verbose_name=_("size for snapshots (MiB)"), null=True, blank=True,
    )
    wwn = db.CharField(
        verbose_name=_("Volume serial"), max_length=33, unique=True,
    )
    full = db.BooleanField(default=True)

    class Meta:
        verbose_name = _("disk share")
        verbose_name_plural = _("disk shares")

    def __unicode__(self):
        return '%s (%s)' % (self.label, self.wwn)

    def get_total_size(self):
        return (self.size or 0) + (self.snapshot_size or 0)


class DiskShareMount(TimeTrackable, WithConcurrentGetOrCreate):
    share = db.ForeignKey(DiskShare, verbose_name=_("share"))
    asset = db.ForeignKey('Asset', verbose_name=_("asset"), null=True,
                           blank=True, default=None, on_delete=db.SET_NULL)
    volume = db.CharField(verbose_name=_("volume"),
                          max_length=255, blank=True,
                          null=True, default=None)
    # server = db.ForeignKey(
    #     'Asset', verbose_name=_("server"), null=True, blank=True,
    #     default=None, related_name='servermount_set',
    # )
    size = db.PositiveIntegerField(
        verbose_name=_("size (MiB)"), null=True, blank=True,
    )
    # address = db.ForeignKey('IPAddress', null=True, blank=True, default=None)
    # is_virtual = db.BooleanField(
    #     verbose_name=_("is that a virtual server mount?"), default=False,
    # )

    class Meta:
        unique_together = ('share', 'asset')
        verbose_name = _("disk share mount")
        verbose_name_plural = _("disk share mounts")

    def __unicode__(self):
        return '%s@%r' % (self.volume, self.asset)

    def get_total_mounts(self):
        return self.share.disksharemount_set.exclude(
            device=None
        ).filter(
            is_virtual=False
        ).count()

    def get_size(self):
        return self.size or self.share.get_total_size()


class Processor(Component):
    label = db.CharField(verbose_name=_("name"), max_length=255)
    speed = db.PositiveIntegerField(
        verbose_name=_("speed (MHz)"), null=True, blank=True,
    )
    cores = db.PositiveIntegerField(
        verbose_name=_("number of cores"), null=True, blank=True,
    )
    index = db.PositiveIntegerField(
        verbose_name=_("slot number"), null=True, blank=True,
    )

    class Meta:
        verbose_name = _("processor")
        verbose_name_plural = _("processors")
        ordering = ('asset', 'index')
        unique_together = ('asset', 'index')

    def __init__(self, *args, **kwargs):
        super(Processor, self).__init__(*args, **kwargs)
        self.cores = self.guess_core_count()

    def __unicode__(self):
        return '#{}: {} ({})'.format(self.index, self.label, self.model)

    def get_cores(self):
        if self.model and self.model.cores:
            return self.model.cores
        return self.cores or 1

    def guess_core_count(self):
        """Guess the number of cores for a CPU model."""
        if self.model:
            return max(
                1,
                self.model.cores,
                self.cores,
                self.model.size,
                cores_from_model(
                    self.model.name
                ) if not is_virtual_cpu(self.model.name) else 1,
            )
        return max(1, self.cores)

    def save(self, *args, **kwargs):
        if self.model:
            self.cores = self.model.cores
        return super(Processor, self).save(*args, **kwargs)

    @property
    def size(self):
        return self.get_cores()


class Memory(Component):
    label = db.CharField(verbose_name=_("name"), max_length=255)
    size = db.PositiveIntegerField(
        verbose_name=_("size (MiB)"), null=True, blank=True,
    )
    speed = db.PositiveIntegerField(
        verbose_name=_("speed (MHz)"), null=True, blank=True,
    )
    index = db.PositiveIntegerField(
        verbose_name=_("slot number"), null=True, blank=True,
    )

    class Meta:
        verbose_name = _("memory")
        verbose_name_plural = _("memories")
        ordering = ('asset', 'index')
        unique_together = ('asset', 'index')

    def __unicode__(self):
        return '#{}: {} ({})'.format(self.index, self.label, self.model)


class Storage(Component):
    sn = db.CharField(
        verbose_name=_("vendor SN"), max_length=255, unique=True, null=True,
        blank=True, default=None,
    )
    label = db.CharField(verbose_name=_("name"), max_length=255)
    mount_point = db.CharField(
        verbose_name=_("mount point"), max_length=255, null=True, blank=True,
        default=None,
    )
    size = db.PositiveIntegerField(
        verbose_name=_("size (MiB)"), null=True, blank=True,
    )

    class Meta:
        verbose_name = _("storage")
        verbose_name_plural = _("storages")
        ordering = ('asset', 'sn', 'mount_point')
        unique_together = ('asset', 'mount_point')

    def __unicode__(self):
        if not self.mount_point:
            return '{} ({})'.format(self.label, self.model)
        return '{} at {} ({})'.format(self.label, self.mount_point, self.model)

    def get_size(self):
        if self.model and self.model.size:
            return self.model.size
        return self.size or 0


class FibreChannel(Component):
    physical_id = db.CharField(verbose_name=_("name"), max_length=32)
    label = db.CharField(verbose_name=_("name"), max_length=255)

    class Meta:
        verbose_name = _("fibre channel")
        verbose_name_plural = _("fibre channels")
        ordering = ('asset', 'physical_id')
        unique_together = ('asset', 'physical_id')

    def __unicode__(self):
        return '{} ({})'.format(self.label, self.physical_id)


class Ethernet(Component):
    label = db.CharField(verbose_name=_("name"), max_length=255)
    mac = MACAddressField(verbose_name=_("MAC address"), unique=True)
    speed = db.PositiveIntegerField(
        verbose_name=_("speed"), choices=EthernetSpeed(),
        default=EthernetSpeed.unknown.id,
    )

    class Meta:
        verbose_name = _("ethernet")
        verbose_name_plural = _("ethernets")
        ordering = ('asset', 'mac')

    def __unicode__(self):
        return '{} ({})'.format(self.label, self.mac)


class Software(Component):
    sn = db.CharField(
        verbose_name=_("vendor SN"), max_length=255, unique=True, null=True,
        blank=True, default=None,
    )
    label = db.CharField(verbose_name=_("name"), max_length=255)
    # bash and widnows have a limit on the path length
    path = db.CharField(
        verbose_name=_("path"), max_length=255, null=True, blank=True,
        default=None,
    )
    version = db.CharField(verbose_name=_("version"), max_length=255,
                           null=True, blank=True, default=None)

    class Meta:
        verbose_name = _("software")
        verbose_name_plural = _("software")
        ordering = ('asset', 'sn', 'path')
        unique_together = ('asset', 'path')

    def __unicode__(self):
        return '%r' % self.label

    @classmethod
    def create(cls, dev, path, model_name, priority, label=None, sn=None,
               family=None, version=None):
        model, created = ComponentModel.create(
            ComponentType.software,
            family=family,
            name=model_name,
            priority=priority,
        )
        software, created = cls.concurrent_get_or_create(
            asset=dev,
            path=path,
            defaults={
                'model': model,
                'label': label or model_name,
                'sn': sn,
                'version': version,
            }
        )
        if created:
            software.mark_dirty(
                'asset',
                'path',
                'model',
                'label',
                'sn',
                'version',
            )
            software.save(priority=priority)
        # FIXME: should model, label, sn and version be updated for
        #        existing objects?
        return software


class SplunkUsage(Component):
    day = db.DateField(verbose_name=_("day"), auto_now_add=True)
    size = db.PositiveIntegerField(
        verbose_name=_("size (MiB)"), null=True, blank=True,
    )

    class Meta:
        verbose_name = _("Splunk usage")
        verbose_name_plural = _("Splunk usages")
        ordering = ('asset', 'day')
        unique_together = ('asset', 'day')

    def __unicode__(self):
        return '#{}: {}'.format(self.day, self.model)


class OperatingSystem(Component):
    label = db.CharField(verbose_name=_("name"), max_length=255)
    memory = db.PositiveIntegerField(
        verbose_name=_("memory"), help_text=_("in MiB"), null=True, blank=True,
    )
    storage = db.PositiveIntegerField(
        verbose_name=_("storage"), help_text=_("in MiB"), null=True,
        blank=True,
    )
    cores_count = db.PositiveIntegerField(
        verbose_name=_("cores count"), null=True, blank=True,
    )

    class Meta:
        verbose_name = _("operating system")
        verbose_name_plural = _("operating systems")
        ordering = ('label',)
        unique_together = ('asset',)

    def __unicode__(self):
        return self.label

    @classmethod
    def create(cls, dev, os_name, priority, version='', memory=None,
               storage=None, cores_count=None, family=None):
        model, created = ComponentModel.create(
            ComponentType.os,
            family=family,
            name=os_name,
            priority=priority,
        )
        operating_system, created = cls.concurrent_get_or_create(
            asset=dev,
            defaults={
                'model': model,
            }
        )
        operating_system.label = '%s %s' % (os_name, version)
        operating_system.memory = memory
        operating_system.storage = storage
        operating_system.cores_count = cores_count
        operating_system.save(priority=priority)
        return operating_system


def get_network_tree(qs=None):
    """
    Returns tree of networks based on L3 containment.
    """
    if not qs:
        qs = Network.objects.all()
    tree = []
    all_networks = [
        (net.max_ip, net.min_ip, net)
        for net in qs.order_by("min_ip", "-max_ip")
    ]

    def get_subnetworks_qs(network):
        for net in all_networks:
            if net[0] == network.max_ip and net[1] == network.min_ip:
                continue
            if net[0] <= network.max_ip and net[1] >= network.min_ip:
                yield net[2]

    def recursive_tree(network):
        subs = []
        sub_qs = get_subnetworks_qs(network)
        subnetworks = network.get_subnetworks(networks=sub_qs)
        subs = [
            {
                'network': sub,
                'subnetworks': recursive_tree(sub)
            } for sub in subnetworks
        ]
        for i, net in enumerate(all_networks):
            if net[0] == network.max_ip and net[1] == network.min_ip:
                all_networks.pop(i)
                break
        return subs

    while True:
        try:
            tree.append({
                'network': all_networks[0][2],
                'subnetworks': recursive_tree(all_networks[0][2])
            })
        except IndexError:
            # recursive tree uses pop, so at some point all_networks[0]
            # will rise IndexError, therefore algorithm is finished
            break
    return tree

# This is scan environment, not Service Env.
class Environment(Named):
    data_center = db.ForeignKey("DataCenter", verbose_name=_("data center"))
    queue = db.ForeignKey(
        "DiscoveryQueue",
        verbose_name=_("discovery queue"),
        null=True,
        blank=True,
        on_delete=db.SET_NULL,
    )
    hosts_naming_template = db.CharField(
        max_length=30,
        help_text=_(
            "E.g. h<200,299>.dc|h<400,499>.dc will produce: h200.dc "
            "h201.dc ... h299.dc h400.dc h401.dc"
        ),
    )
    next_server = db.CharField(
        max_length=32,
        blank=True,
        default='',
        help_text=_("The address for a TFTP server for DHCP."),
    )
    domain = db.CharField(
        _('domain'),
        max_length=255,
        blank=True,
        null=True,
    )
    remarks = db.TextField(
        verbose_name=_("remarks"),
        help_text=_("Additional information."),
        blank=True,
        null=True,
    )

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ('name',)


class NetworkKind(Named):
    icon = db.CharField(
        _("icon"), max_length=32, null=True, blank=True, default=None,
    )

    class Meta:
        verbose_name = _("network kind")
        verbose_name_plural = _("network kinds")
        ordering = ('name',)


class AbstractNetwork(db.Model):
    address = db.CharField(
        _("network address"),
        help_text=_("Presented as string (e.g. 192.168.0.0/24)"),
        max_length=len("xxx.xxx.xxx.xxx/xx"), unique=True,
    )
    gateway = db.IPAddressField(
        _("gateway address"), help_text=_("Presented as string."), blank=True,
        null=True, default=None,
    )
    gateway_as_int = db.PositiveIntegerField(
        _("gateway as int"), null=True, blank=True, default=None,
        editable=False,
    )
    reserved = db.PositiveIntegerField(
        _("reserved"), default=10,
        help_text=_("Number of addresses to be omitted in the automatic "
                    "determination process, counted from the first in range.")
    )
    reserved_top_margin = db.PositiveIntegerField(
        _("reserved (top margin)"), default=0,
        help_text=_("Number of addresses to be omitted in the automatic "
                    "determination process, counted from the last in range.")
    )
    remarks = db.TextField(
        _("remarks"), help_text=_("Additional information."), blank=True,
        default="",
    )
    terminators = db.ManyToManyField(
        "NetworkTerminator", verbose_name=_("network terminators"),
    )
    vlan = db.PositiveIntegerField(
        _("VLAN number"), null=True, blank=True, default=None,
    )
    data_center = db.ForeignKey(
        "DataCenter",
        verbose_name=_("data center"),
        null=True,
        blank=True,
    )
    environment = db.ForeignKey(
        "Environment",
        verbose_name=_("environment"),
        null=True,
        blank=True,
        on_delete=db.SET_NULL,
    )
    min_ip = db.PositiveIntegerField(
        _("smallest IP number"), null=True, blank=True, default=None,
        editable=False,
    )
    max_ip = db.PositiveIntegerField(
        _("largest IP number"), null=True, blank=True, default=None,
        editable=False,
    )
    kind = db.ForeignKey(
        NetworkKind, verbose_name=_("network kind"), on_delete=db.SET_NULL,
        null=True, blank=True, default=None,
    )
    racks = db.ManyToManyField(
        'Rack', verbose_name=_("racks"),
        # We can't import DeviceType in here, so we use an integer.
        # limit_choices_to={
            # 'model__type': 1,
            # 'deleted': False,
        # },  # DeviceType.rack.id
    )
    ignore_addresses = db.BooleanField(
        _("Ignore addresses from this network"),
        default=False,
        help_text=_(
            "Addresses from this network should never be assigned "
            "to any device, because they are not unique."
        ),
    )
    # TODO: po co to?
    # custom_dns_servers = db.ManyToManyField(
    #     'dnsedit.DNSServer',
    #     verbose_name=_('custom DNS servers'),
    #     null=True,
    #     blank=True,
    # )
    dhcp_broadcast = db.BooleanField(
        _("Broadcast in DHCP configuration"),
        default=False,
        db_index=True,
    )
    dhcp_config = db.TextField(
        _("DHCP additional configuration"),
        blank=True,
        default='',
    )
    last_scan = db.DateTimeField(
        _("last scan"),
        null=True,
        blank=True,
        default=None,
        editable=False,
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        net = ipaddr.IPNetwork(self.address)
        self.min_ip = int(net.network)
        self.max_ip = int(net.broadcast)
        if self.gateway:
            self.gateway_as_int = int(ipaddr.IPv4Address(self.gateway))
        super(AbstractNetwork, self).save(*args, **kwargs)

    def __contains__(self, what):
        if isinstance(what, AbstractNetwork):
            return what.min_ip >= self.min_ip and what.max_ip <= self.max_ip
        elif isinstance(what, IPAddress):
            ip = what.number
        else:
            ip = int(ipaddr.IPAddress(what))
        return self.min_ip <= ip <= self.max_ip

    def is_private(self):
        ip = ipaddr.IPAddress(self.address.split('/')[0])
        return (
            ip in ipaddr.IPNetwork('10.0.0.0/8') or
            ip in ipaddr.IPNetwork('172.16.0.0/12') or
            ip in ipaddr.IPNetwork('192.168.0.0/16')
        )

    def get_subnetworks(self, networks=None):
        """
        Return list of all L3 subnetworks this network contains.
        Only first level of children networks are returned.
        """
        if not networks:
            networks = Network.objects.filter(
                data_center=self.data_center,
                min_ip__gte=self.min_ip,
                max_ip__lte=self.max_ip,
            ).exclude(
                pk=self.id,
            ).order_by('-min_ip', 'max_ip')
        subnets = sorted(list(networks), key=lambda net: net.get_netmask())
        new_subnets = list(subnets)
        for net, netw in enumerate(subnets):
            net_address = ipaddr.IPNetwork(netw.address)
            for i, sub in enumerate(subnets):
                sub_addr = ipaddr.IPNetwork(sub.address)
                if sub_addr != net_address and sub_addr in net_address:
                    if sub in new_subnets:
                        new_subnets.remove(sub)
        new_subnets = sorted(new_subnets, key=lambda net: net.min_ip)
        return new_subnets

    @classmethod
    def from_ip(cls, ip):
        """Find the smallest network containing that IP."""

        return cls.all_from_ip(ip)[0]

    @classmethod
    def all_from_ip(cls, ip):
        """Find all networks for this IP."""

        ip_int = int(ipaddr.IPAddress(ip))
        nets = cls.objects.filter(
            min_ip__lte=ip_int,
            max_ip__gte=ip_int
        ).order_by('-min_ip', 'max_ip')
        return nets

    @property
    def network(self):
        return ipaddr.IPNetwork(self.address)

    def get_total_ips(self):
        """
        Get total amount of addresses in this network.
        """
        return self.max_ip - self.min_ip

    def get_subaddresses(self):
        subnetworks = self.get_subnetworks()
        addresses = list(IPAddress.objects.filter(
            number__gte=self.min_ip,
            number__lte=self.max_ip,
        ).order_by("number"))
        new_addresses = list(addresses)
        for addr in addresses:
            for subnet in subnetworks:
                if addr in subnet and addr in new_addresses:
                    new_addresses.remove(addr)
        return new_addresses

    def get_free_ips(self):
        """
        Get number of free addresses in network.
        """
        subnetworks = self.get_subnetworks()
        total_ips = self.get_total_ips()
        for subnet in subnetworks:
            total_ips -= subnet.get_total_ips()
        addresses = self.get_subaddresses()
        total_ips -= len(addresses)
        total_ips -= self.reserved_top_margin + self.reserved
        return total_ips

    def get_ip_usage_range(self):
        """
        Returns list of entities this network contains (addresses and subnets)
        ordered by its address or address range.
        """
        contained = []
        contained.extend(self.get_subnetworks())
        contained.extend(self.get_subaddresses())

        def sorting_key(obj):
            if isinstance(obj, Network):
                return obj.min_ip
            elif isinstance(obj, IPAddress):
                return obj.number
            else:
                raise TypeError("Type not supported")

        return sorted(contained, key=sorting_key)

    def get_ip_usage_aggegated(self):
        """
        Aggregates network usage range - combines neighboring addresses to
        a single entitiy and appends blocks of free addressations.
        """
        address_range = self.get_ip_usage_range()
        ranges_and_networks = []
        ip_range = []
        for addr in address_range:
            if isinstance(addr, IPAddress):
                if ip_range and not addr.number - 1 in ip_range:
                    ranges_and_networks.append((ip_range[0], ip_range[-1], 1))
                    ip_range = []
                ip_range.append(addr.number)
            else:
                if ip_range:
                    ranges_and_networks.append((ip_range[0], ip_range[-1], 1))
                    ip_range = []
                ranges_and_networks.append((addr.min_ip, addr.max_ip, addr))

        def f(a):
            if a[2] == 0:
                range_type = "free"
            elif a[2] == 1:
                range_type = "addr"
            else:
                range_type = a[2]
            return {
                'range_start': str(ipaddr.IPAddress(a[0])),
                'range_end': str(ipaddr.IPAddress(a[1])),
                'type': range_type,
                'amount': a[1] - a[0] + 1,
            }

        min_ip = self.min_ip
        parsed = []
        for i, range_or_net in enumerate(ranges_and_networks):
            if range_or_net[0] != min_ip:
                parsed.append(f((min_ip, range_or_net[0] - 1, 0)))
            parsed.append(f(range_or_net))
            min_ip = range_or_net[1] + 1
        if ranges_and_networks and ranges_and_networks[-1][1] < self.max_ip:
            parsed.append(f((ranges_and_networks[-1][1] + 1, self.max_ip, 0)))
        if not ranges_and_networks:
            # this network is empty, lets append big, free block
            parsed.append(f((self.min_ip, self.max_ip, 0)))
        return parsed

    def get_netmask(self):
        try:
            mask = self.address.split("/")[1]
            return int(mask)
        except (ValueError, IndexError):
            return None

    def clean(self, *args, **kwargs):
        super(AbstractNetwork, self).clean(*args, **kwargs)
        try:
            ipaddr.IPNetwork(self.address)
        except ValueError:
            raise ValidationError(_("The address value specified is not a "
                                    "valid network."))


class Network(Named, AbstractNetwork, TimeTrackable,
              WithConcurrentGetOrCreate):

    class Meta:
        verbose_name = _("network")
        verbose_name_plural = _("networks")
        ordering = ('vlan',)

    def __unicode__(self):
        return "{} ({})".format(self.name, self.address)

    def get_absolute_url(self):
        args = [urllib.quote(self.name.encode('utf-8'), ''), 'info']
        return reverse("networks", args=args)


class NetworkTerminator(Named):

    class Meta:
        verbose_name = _("network terminator")
        verbose_name_plural = _("network terminators")
        ordering = ('name',)


# class DataCenter(Named):
#     def __unicode__(self):
#         return self.name
#     class Meta:
#         verbose_name = _("data center")
#         verbose_name_plural = _("data centers")
#         ordering = ('name',)


class DiscoveryQueue(Named):
    class Meta:
        verbose_name = _("discovery queue")
        verbose_name_plural = _("discovery queues")
        ordering = ('name',)


def validate_network_address(sender, instance, **kwargs):
    instance.full_clean()
    return

#     # clearing cache items for networks sidebar(24 hour cache)
#     ns_items_key = 'cache_network_sidebar_items'
#     if ns_items_key in cache:
#         cache.delete(ns_items_key)

# db.signals.pre_save.connect(validate_network_address, sender=Network)


class IPAddress(LastSeen, TimeTrackable, WithConcurrentGetOrCreate):
    address = db.IPAddressField(
        _("IP address"), help_text=_("Presented as string."), unique=True,
        blank=True, null=True, default=None,
    )
    number = db.BigIntegerField(
        _("IP address"), help_text=_("Presented as int."), editable=False,
        unique=True,
    )
    hostname = db.CharField(
        _("hostname"), max_length=255, null=True, blank=True, default=None,
    )
    # hostname.max_length vide /usr/include/bits/posix1_lim.h
    snmp_name = db.TextField(
        _("name from SNMP"), null=True, blank=True, default=None,
    )
    snmp_community = db.CharField(
        _("SNMP community"), max_length=64, null=True, blank=True,
        default=None,
    )
    snmp_version = db.CharField(
        _("SNMP version"),
        max_length=5,
        null=True,
        blank=True,
        default=None,
    )
    asset = db.ForeignKey(
        Asset, verbose_name=_("asset"), null=True, blank=True,
        default=None, on_delete=db.SET_NULL,
    )
    http_family = db.TextField(
        _('family from HTTP'), null=True, blank=True, default=None,
        max_length=64,
    )
    is_management = db.BooleanField(
        _("This is a management address"),
        default=False,
    )
    dns_info = db.TextField(
        _('information from DNS TXT fields'), null=True, blank=True,
        default=None,
    )
    last_puppet = db.DateTimeField(
        _("last puppet check"), null=True, blank=True, default=None,
    )
    network = db.ForeignKey(
        Network, verbose_name=_("network"), null=True, blank=True,
        default=None,
    )
    last_plugins = db.TextField(_("last plugins"), blank=True)
    dead_ping_count = db.IntegerField(_("dead ping count"), default=0)
    is_buried = db.BooleanField(_("Buried from autoscan"), default=False)
    #TODO: scan
    scan_summary = db.ForeignKey(
        ScanSummary,
        on_delete=db.SET_NULL,
        null=True,
        blank=True,
    )
    is_public = db.BooleanField(
        _("This is a public address"),
        default=False,
        editable=False,
    )
    puppet_venture = db.ForeignKey(
        'business.PuppetVenture',
        verbose_name=_("puppet venture"),
        null=True,
        blank=True,
        default=None,
        on_delete=db.SET_NULL,
    )

    class Meta:
        verbose_name = _("IP address")
        verbose_name_plural = _("IP addresses")

    def __unicode__(self):
        return "{} ({})".format(self.hostname, self.address)

    def save(self, allow_device_change=True, *args, **kwargs):
        if not allow_device_change:
            self.assert_same_device()
        if not self.address:
            self.address = network.hostname(self.hostname, reverse=True)
        if not self.hostname:
            self.hostname = network.hostname(self.address)
        self.number = int(ipaddr.IPAddress(self.address))
        try:
            self.network = Network.from_ip(self.address)
        except IndexError:
            self.network = None
        if self.network and self.network.ignore_addresses:
            self.device = None
        ip = ipaddr.IPAddress(self.address)
        self.is_public = not ip.is_private
        super(IPAddress, self).save(*args, **kwargs)

    def assert_same_device(self):
        if not self.id or 'device_id' not in self.dirty_fields:
            return
        dirty_devid = self.dirty_fields['device_id']
        if not dirty_devid or dirty_devid == self.device_id:
            return
        # The addresses from outside of our defined networks can change freely
        if self.network is None:
            try:
                self.network = Network.from_ip(self.address)
            except IndexError:
                return
        raise IntegrityError(
            "Trying to assign device ID #{} for IP {} but device ID #{} "
            "already assigned.".format(self.device_id, self, dirty_devid),
        )

    # We overwrite the following method. If the address is not bound to
    # any device or venture, we can delete it and create new.
    def _perform_unique_checks(self, *args, **kwargs):
        try:
            existing = type(self).objects.get(address=self.address)
        except type(self).DoesNotExist:
            return
        if existing == self:
            return
        elif existing.device:
            return {'address': [_('There exists a device with this address')]}
        elif existing.venture:
            return {'address': [_('This address is a public one')]}

    def as_tuple(self):
        """Returns a tuple usable to initialize the field"""
        return self.hostname, self.address


class IPAlias(SavePrioritized, WithConcurrentGetOrCreate):
    address = db.ForeignKey("IPAddress", related_name="+")
    hostname = db.CharField(_("hostname"), max_length=255)
    # hostname.max_length vide /usr/include/bits/posix1_lim.h

    class Meta:
        verbose_name = _("IP alias")
        verbose_name_plural = _("IP aliases")


# FIXME:
# map it with categories from assets
# class DeviceType(Choices):
#     _ = Choices.Choice

#     INFRASTRUCTURE = Choices.Group(0)
#     rack = _("rack")
#     blade_system = _("blade system")
#     management = _("management")
#     power_distribution_unit = _("power distribution unit")
#     data_center = _("data center")

#     NETWORK_EQUIPMENT = Choices.Group(100)
#     switch = _("switch")
#     router = _("router")
#     load_balancer = _("load balancer")
#     firewall = _("firewall")
#     smtp_gateway = _("SMTP gateway")
#     appliance = _("Appliance")
#     switch_stack = _("switch stack")

#     SERVERS = Choices.Group(200)
#     rack_server = _("rack server")
#     blade_server = _("blade server") << {'matches': BLADE_SERVERS_RE.match}
#     virtual_server = _("virtual server")
#     cloud_server = _("cloud server")

#     STORAGE = Choices.Group(300)
#     storage = _("storage")
#     fibre_channel_switch = _("fibre channel switch")
#     mogilefs_storage = _("MogileFS storage")

#     UNKNOWN = Choices.Group(400)
#     unknown = _("unknown")


class LoadBalancerType(SavingUser):
    name = db.CharField(
        verbose_name=_("name"),
        max_length=255,
        unique=True,
    )

    class Meta:
        verbose_name = _("load balancer type")
        verbose_name_plural = _("load balancer types")
        ordering = ('name',)

    def __unicode__(self):
        return self.name

    def get_count(self):
        return self.loadbalancervirtualserver_set.count()


class LoadBalancerPool(Named, WithConcurrentGetOrCreate):

    class Meta:
        verbose_name = _("load balancer pool")
        verbose_name_plural = _("load balancer pools")


class LoadBalancerVirtualServer(BaseItem):
    load_balancer_type = db.ForeignKey(LoadBalancerType, verbose_name=_('load balancer type'))
    asset = db.ForeignKey(DCAsset, verbose_name=_("load balancer asset"))
    default_pool = db.ForeignKey(LoadBalancerPool, null=True)
    address = db.ForeignKey("IPAddress", verbose_name=_("address"))
    port = db.PositiveIntegerField(verbose_name=_("port"))

    class Meta:
        verbose_name = _("load balancer virtual server")
        verbose_name_plural = _("load balancer virtual servers")
        unique_together = ('address', 'port')

    def __unicode__(self):
        return "{} ({})".format(self.name, self.id)


class LoadBalancerMember(SavePrioritized, WithConcurrentGetOrCreate):
    address = db.ForeignKey("IPAddress", verbose_name=_("address"))
    port = db.PositiveIntegerField(verbose_name=_("port"))
    pool = db.ForeignKey(LoadBalancerPool)
    asset = db.ForeignKey(DCAsset, verbose_name=_("load balancer asset"))
    enabled = db.BooleanField(verbose_name=_("enabled state"))

    class Meta:
        verbose_name = _("load balancer pool membership")
        verbose_name_plural = _("load balancer pool memberships")
        unique_together = ('pool', 'address', 'port', 'asset')

    def __unicode__(self):
        return "{}:{}@{}({})".format(
            self.address.address, self.port, self.pool.name, self.id)


class DatabaseType(SavingUser):
    name = db.CharField(
        verbose_name=_("name"),
        max_length=255,
        unique=True,
    )

    class Meta:
        verbose_name = _("database type")
        verbose_name_plural = _("database types")
        ordering = ('name',)

    def __unicode__(self):
        return self.name

    def get_count(self):
        return self.database_set.count()


class Database(BaseItem):
    parent_asset = db.ForeignKey(
        Asset,
        verbose_name=_("database server"),
    )
    database_type = db.ForeignKey(
        DatabaseType,
        verbose_name=_("database type"),
        related_name='databases',
    )

    class Meta:
        verbose_name = _("database")
        verbose_name_plural = _("databases")

    def __unicode__(self):
        return "{} ({})".format(self.name, self.id)
