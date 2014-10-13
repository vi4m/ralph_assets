# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from django.db.models import signals

from ralph_assets.history.receivers import m2m_changed, post_save, pre_save


registry = {}
registry_m2m = {}


def register(model, exclude=None, m2m=False):
    """Register model to history observer."""
    if exclude is None and not m2m:
        raise TypeError('Please specified exclude argument.')

    if (not m2m and model in registry) or (m2m and model in registry_m2m):
        raise Exception('{} is arleady registered.'.format(model))

    if not m2m:
        fields = set([field.name for field in model._meta.fields])
        fields.difference_update(set(exclude))
        registry[model] = fields
        signals.pre_save.connect(pre_save, sender=model)
        signals.post_save.connect(post_save, sender=model)
    else:
        registry_m2m[model] = True
        signals.m2m_changed.connect(m2m_changed, sender=model)
