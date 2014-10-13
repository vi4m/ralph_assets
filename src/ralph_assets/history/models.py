# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
from collections import namedtuple

from datetime import datetime

from django.db import models
from django.core import serializers
from django.core.urlresolvers import reverse
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.generic import GenericForeignKey
from django.utils.translation import ugettext_lazy as _


DEFAULT_HISTORY_FIELD_EXCLUDE = ('created', 'modified', 'invoice_date',
                                 'cache_version', 'rght', 'level', 'lft',
                                 'tree_id', 'loan_end_date')

serializer = serializers.get_serializer("python")()

Snapshot = namedtuple(
    'Snapshot',
    ['current', 'previous', 'added', 'deleted', 'changed', 'obj', 'field_name'],  # noqa
)


class HistoryManager(models.Manager):
    def get_history_for_this_object(self, obj, field_name=None):
        if not obj:
            return
        content_type = ContentType.objects.get_for_model(obj.__class__)
        kwargs = {
            'content_type': content_type,
            'object_id': obj.id,
        }
        if field_name:
            kwargs.update({
                'field_name': field_name
            })
        return self.get_history_for_this_content_type(**kwargs)

    def get_history_for_this_content_type(
        self, content_type, object_id, **kwargs
    ):
        return self.model.objects.filter(
            content_type=content_type,
            object_id=object_id,
            **kwargs
        )

    def log_changes(self, obj, user, diff_data):
        if not obj:
            return
        content_type = ContentType.objects.get_for_model(obj.__class__)
        changed_items = []

        for data in diff_data:
            changed_items.append(
                self.model(
                    user=user,
                    content_type=content_type,
                    object_id=obj.id,
                    field_name=data['field'],
                    old_value=data['old'] if data['old'] else '-',
                    new_value=data['new'] if data['new'] else '-',
                )
            )
        self.model.objects.bulk_create(changed_items)


class History(models.Model):
    date = models.DateTimeField(verbose_name=_('date'), default=datetime.now)
    user = models.ForeignKey(
        'auth.User', verbose_name=_('user'), null=True,
        blank=True, default=None, on_delete=models.SET_NULL
    )
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    field_name = models.CharField(max_length=64, default='')
    old_value = models.TextField(default='')
    new_value = models.TextField(default='')
    objects = HistoryManager()

    class Meta:
        app_label = 'ralph_assets'
        verbose_name = _('history change')
        verbose_name_plural = _('history changes')
        ordering = ('-date',)

    def __unicode__(self):
        return 'in {} (id: {}) change {}: {} -> {}'.format(
            self.content_type,
            self.object_id,
            self.field_name,
            self.old_value,
            self.new_value
        )

    @classmethod
    def get_history_url_for_object(cls, obj):
        content_type = ContentType.objects.get_for_model(obj.__class__)
        return reverse('history_for_model', kwargs={
            'content_type': content_type.id,
            'object_id': obj.id,
        })


class HistoryMixin(object):
    """Django's raw m2m_change signal sucks when working with forms."""

    def __init__(self, *args, **kwargs):
        super(HistoryMixin, self).__init__(*args, **kwargs)
        from ralph_assets.history import registry, register
        if not registry.get(self.__class__, None):
            exclude = getattr(
                self,
                'exclude_fields_from_history',
                DEFAULT_HISTORY_FIELD_EXCLUDE
            )
            register(self.__class__, exclude=exclude)
            for field in self._meta.get_all_related_many_to_many_objects():
                register(field.field.rel.through, m2m=True)

    def get_history(self, field_name=None):
        return History.objects.get_history_for_this_object(
            obj=self,
            field_name=field_name,
        )

    def get_snapshot(self, obj, manager, field_name):
        """Method returns snapshot from current state of object."""
        snapshot = serializer.serialize(manager.all(), fields=())
        try:
            history = obj.get_history(field_name=field_name)[0]
        except (IndexError, AttributeError):
            history = None
        previous = getattr(history, 'new_value', None)
        previous = previous and json.loads(previous) or []
        current = [s['pk'] for s in snapshot]
        deleted = set(previous) - set(current)
        added = set(current) - set(previous)
        changed = not set(current) == set(previous)
        return Snapshot(
            current, previous, added, deleted, changed, obj, field_name
        )

    def save_history_from_snapshot(self, snapshot):
        if snapshot.changed:
            History.objects.log_changes(
                snapshot.obj,
                self.saving_user,
                [{
                    'field': snapshot.field_name,
                    'old': json.dumps(snapshot.previous),
                    'new': json.dumps(snapshot.current),
                }]
            )

    def _save_related_objects_history(self, manager, related_pks, field_name):
        for obj in manager.filter(pk__in=related_pks):
            manager = getattr(obj, field_name)
            snapshot = self.get_snapshot(obj, manager, field_name)
            self.save_history_from_snapshot(snapshot)

    def save_reverse_relation_history(self):
        """Save history to related objects reverse."""
        for field in self._meta.get_all_related_many_to_many_objects():
            field_name = field.get_accessor_name()
            reverse_manager = getattr(self, field_name)
            snapshot = self.get_snapshot(self, reverse_manager, field_name)
            self._save_related_objects_history(
                reverse_manager, snapshot.added, field.field.name
            )
            self.save_history_from_snapshot(snapshot)

    def save_m2m_history(self):
        """Save history to related objects."""
        for field in self._meta.get_m2m_with_model():
            field_name = field[0].name
            manager = getattr(self, field_name)
            snapshot = self.get_snapshot(self, manager, field_name)
            self.save_history_from_snapshot(snapshot)
