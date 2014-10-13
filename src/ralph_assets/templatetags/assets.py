# -*- coding: utf-8 -*-
"""Templatetags specific for ralph_assets"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from django import template
from django.core.urlresolvers import reverse

from ralph_assets.models import get_edit_url
from ralph_assets.models_support import Support
from ralph_assets.models_assets import ASSET_TYPE2MODE


register = template.Library()


@register.simple_tag
def edit_url(object_):
    """Returns the url of edit page for a given object (currently implemented
    for Users, expand if needed)
    """
    return get_edit_url(object_)


@register.inclusion_tag('assets/templatetags/transition_history.html')
def transition_history(asset):
    transitions_history = None
    if hasattr(asset, 'transitionshistory_set'):
        transitions_history = asset.transitionshistory_set.all()
    return {'transitions_history': transitions_history}


@register.inclusion_tag('assets/templatetags/collapsed_form.html')
def collapsed_form(form):
    """Render a collapsed form."""
    return {'form': form}


@register.inclusion_tag('assets/templatetags/object_list_search.html')
def object_list_search(object_instance, field):
    """Generate link to search releated fields objects. Currently work only
    with Support.
    """
    if isinstance(object_instance, Support):
        params = None
        mode = ASSET_TYPE2MODE.get(object_instance.asset_type)
        base_url = reverse('asset_search', args=(mode,))
        ids = getattr(object_instance, field).values_list('id', flat=True)
        if ids:
            params = ','.join(map(str, ids))
        url = '{}?id={}'.format(base_url, params)
    else:
        raise ValueError('%s is not supported' % object_instance)
    return {'url': url, 'field': field, 'show': params}


@register.inclusion_tag(
    'assets/templatetags/mode_switch.html',
    takes_context=True,
)
def mode_switch(context):
    return {'mode': context['mode']}
