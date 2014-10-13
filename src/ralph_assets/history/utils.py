# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from django.core import serializers
from django.db.models.fields import FieldDoesNotExist
from django.db.models.fields.related import RelatedField

from ralph_assets.history.models import History


def field_changes(instance, ignore=('id', 'ralph_device_id')):
    """Yield the name, original value and new value for each changed field.
    Skip all insignificant fields and those passed in ``ignore``.
    When creating asset, the first asset status will be added into the history.
    """
    from ralph_assets.models_assets import Asset
    if isinstance(instance, Asset) and instance.cache_version == 0:
        yield 'status', '–', get_choices(instance, 'status', instance.status)
    for field, orig in instance.dirty_fields.iteritems():
        if field in ignore:
            continue
        if field in instance.insignificant_fields:
            continue
        field_object = None
        try:
            field_object = instance._meta.get_field_by_name(field)[0]
        except FieldDoesNotExist:
            try:
                field = field[:-3]
                field_object = instance._meta.get_field_by_name(field)[0]
            except FieldDoesNotExist:
                continue
        if isinstance(field_object, RelatedField):
            parent_model = field_object.related.parent_model
            try:
                if orig is not None:
                    orig = parent_model.objects.get(pk=orig)
            except parent_model.DoesNotExist:
                orig = None
        try:
            new = getattr(instance, field)
        except AttributeError:
            continue
        if field in ('office_info', 'device_info', 'part_info'):
            continue
        if hasattr(field_object, 'choices') and field_object.choices:
            new = get_choices(instance, field, new)
            orig = get_choices(instance, field, orig)
        if field == 'attachment':
            if str(orig).strip() == str(new).strip():
                continue
        yield field, orig, new


def get_choices(instance, field, id):
    try:
        id = int(id)
    except (TypeError, ValueError):
        return id
    choices = instance._meta.get_field_by_name(field)[0].get_choices()
    for choice_id, value in choices:
        if choice_id == id:
            return value


class DictDiffer(object):
    """Two dicts compared for detect changes."""
    def __init__(self, current_dict, past_dict):
        self.current_dict, self.past_dict = current_dict, past_dict
        self.set_current = set(current_dict.keys())
        self.set_past = set(past_dict.keys())
        self.intersect = self.set_current.intersection(self.set_past)

    def changed(self):
        return set(
            change for change in self.intersect
            if self.past_dict[change] != self.current_dict[change]
        )


class HistoryContext(object):

    def __init__(self):
        self.serializer = serializers.get_serializer("python")()
        self.obj = None

    def get_fields_snapshot(self, objs):
        if not objs:
            return
        kwargs = {}
        fields = self.registry.get(objs[0].__class__, [])
        if fields:
            kwargs.update({'fields': fields})
        return self.serializer.serialize(objs, **kwargs)

    @property
    def registry(self):
        from ralph_assets.history import registry
        return registry

    def pre_save(self):
        self.pre_obj = None
        try:
            self.pre_obj = self.model._default_manager.get(pk=self.obj.pk)
        except self.model.DoesNotExist:
            return
        self.past_snapshot = self.get_fields_snapshot(
            [self.pre_obj]
        )[0]['fields']

    def post_save(self):
        if not self.pre_obj:
            return
        current_snapshot = self.get_fields_snapshot([self.obj])[0]['fields']

        fields_diff = DictDiffer(
            current_snapshot, self.past_snapshot
        ).changed()

        diff_data = []
        for field in fields_diff:
            old_value = self.past_snapshot[field]
            new_value = current_snapshot[field]
            old_field = self.pre_obj._meta.get_field_by_name(field)[0]
            new_field = self.obj._meta.get_field_by_name(field)[0]
            if isinstance(new_field, RelatedField):
                old_value = str(getattr(self.pre_obj, field))
                new_value = str(getattr(self.obj, field))
            elif hasattr(old_field, 'choices') and old_field.choices:
                if int(old_value) == int(new_value):
                    continue
                old_value = get_choices(self.pre_obj, field, old_value)
                new_value = get_choices(self.obj, field, new_value)
            elif hasattr(self.obj, 'get_{}_display'.format(field)):
                old_value = getattr(
                    self.pre_obj, 'get_{}_display'.format(field)
                )()
                new_value = getattr(
                    self.obj, 'get_{}_display'.format(field)
                )()

            if old_value != new_value:
                diff_data.append(
                    {
                        'field': field,
                        'old': old_value,
                        'new': new_value,
                    }
                )
        History.objects.log_changes(self.obj, self.obj.saving_user, diff_data)

    def start(self, sender, obj, m2m=False, pk_set=set(), reverse=False):
        self.obj = obj
        self.model = self.obj.__class__
        self.sender = sender
        self.pre_save()

    def end(self):
        self.post_save()
        self.obj = None
        self.sender = None
        self.reverse = False

context = HistoryContext()
