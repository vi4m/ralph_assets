# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import re

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from lck.django.choices import Choices
from lck.django.common.models import (
    Named,
    SoftDeletable,
    TimeTrackable,
)

from django.db import models
from django.db.models import Sum
from django.db.models.signals import post_save, post_delete
from django.db.utils import DatabaseError
from django.dispatch import receiver

from ralph_assets.history.models import HistoryMixin
from ralph_assets.models_util import SavingUser


logger = logging.getLogger(__name__)

# i.e. number in range 1-16 and optional postfix 'A' or 'B'
VALID_SLOT_NUMBER_FORMAT = re.compile('^([1-9][A,B]?|1[0-6][A,B]?)$')


class Orientation(Choices):
    _ = Choices.Choice

    DEPTH = Choices.Group(0)
    front = _("front")
    back = _("back")
    middle = _("middle")

    WIDTH = Choices.Group(100)
    left = _("left")
    right = _("right")

    @classmethod
    def is_width(cls, orientation):
        is_width = orientation in set(
            [choice.id for choice in cls.WIDTH.choices]
        )
        return is_width

    @classmethod
    def is_depth(cls, orientation):
        is_depth = orientation in set(
            [choice.id for choice in cls.DEPTH.choices]
        )
        return is_depth


class RackOrientation(Choices):
    _ = Choices.Choice

    top = _("top")
    bottom = _("bottom")
    left = _("left")
    right = _("right")


class RequiredModelWithTypeMixin(object):
    """
    Mixin forces a model type in deprecated object (rack, dc).
    """
    _model_type = None

    def __init__(self, *args, **kwargs):
        if not self._model_type:
            raise ValueError('Please provide _model_type')
        super(RequiredModelWithTypeMixin, self).__init__(*args, **kwargs)

    @classmethod
    def create(cls, **kwargs):
        if 'model' not in kwargs.iterkeys():
            raise ValueError('Please provide model.')
        elif kwargs['model'].type != cls._model_type:
            raise ValueError(
                'Model must be a {} type.'.format(cls._model_type.desc)
            )
        return cls(**kwargs)


class DataCenter(Named):

    visualization_cols_num = models.PositiveIntegerField(
        verbose_name=_('visualization grid columns number'),
        default=20,
    )
    visualization_rows_num = models.PositiveIntegerField(
        verbose_name=_('visualization grid rows number'),
        default=20,
    )

    def __unicode__(self):
        return self.name


class ServerRoom(Named.NonUnique):
    data_center = models.ForeignKey(DataCenter, verbose_name=_("data center"))

    def __unicode__(self):
        return '{} ({})'.format(self.name, self.data_center.name)


class Accessory(Named):

    class Meta:
        verbose_name = _('accessory')
        verbose_name_plural = _('accessories')


class RackManager(models.Manager):
    def with_free_u(self):
        racks = self.get_query_set()
        for rack in racks:
            rack.free_u = rack.get_free_u()
        return racks


class Rack(Named.NonUnique):
    class Meta:
        unique_together = ('name', 'data_center')

    data_center = models.ForeignKey(DataCenter, null=False, blank=False)
    server_room = models.ForeignKey(
        ServerRoom, verbose_name=_("server room"),
        null=True,
        blank=True,
    )
    description = models.CharField(
        _('description'), max_length=250, blank=True
    )
    orientation = models.PositiveIntegerField(
        choices=RackOrientation(),
        default=RackOrientation.top.id,
    )
    max_u_height = models.IntegerField(default=48)

    visualization_col = models.PositiveIntegerField(
        verbose_name=_('column number on visualization grid'),
        default=0,
    )
    visualization_row = models.PositiveIntegerField(
        verbose_name=_('row number on visualization grid'),
        default=0,
    )
    accessories = models.ManyToManyField(Accessory, through='RackAccessory')
    objects = RackManager()

    def get_free_u(self):
        assets = self.get_root_assets()
        assets_height = assets.aggregate(
            sum=Sum('model__height_of_device'))['sum'] or 0
        # accesory always has 1U of height
        accessories = RackAccessory.objects.values_list(
            'position', flat=True).filter(rack=self)
        return self.max_u_height - assets_height - len(set(accessories))

    def get_orientation_desc(self):
        return RackOrientation.name_from_id(self.orientation)

    def get_pdus(self):
        from ralph_assets.models_assets import Asset
        return Asset.objects.select_related('model', 'device_info').filter(
            device_info__rack=self,
            device_info__orientation__in=(Orientation.left, Orientation.right),
            device_info__position=0,
        )

    def get_root_assets(self, side=None):
        # FIXME: don't know what this function does.
        from ralph_assets.models_assets import Asset
        filter_kwargs = {
            'device_info__rack': self,
            'device_info__slot_no': '',
        }
        if side:
            filter_kwargs['device_info__orientation'] = side
        return Asset.objects.select_related(
            'model', 'device_info', 'model__category'
        ).filter(**filter_kwargs).exclude(model__category__is_blade=True)

    def __unicode__(self):
        name = self.name
        if self.server_room:
            name = '{} - {}'.format(name, self.server_room)
        elif self.data_center:
            name = '{} - {}'.format(name, self.data_center)
        return name


class RackAccessory(models.Model):
    accessory = models.ForeignKey(Accessory)
    rack = models.ForeignKey(Rack)
    data_center = models.ForeignKey(DataCenter, null=True, blank=False)
    server_room = models.ForeignKey(ServerRoom, null=True, blank=False)
    orientation = models.PositiveIntegerField(
        choices=Orientation(),
        default=Orientation.front.id,
    )
    position = models.IntegerField(null=True, blank=False)
    remarks = models.CharField(
        verbose_name='Additional remarks',
        max_length=1024,
        blank=True,
    )

    def get_orientation_desc(self):
        return Orientation.name_from_id(self.orientation)

    def __unicode__(self):
        rack_name = self.rack.name if self.rack else ''
        accessory_name = self.accessory.name if self.accessory else ''
        return 'RackAccessory: {rack_name} - {accessory_name}'.format(
            rack_name=rack_name, accessory_name=accessory_name,
        )
