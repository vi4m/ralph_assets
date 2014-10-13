# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from ralph_assets.forms_support import (
    AddSupportForm,
    EditSupportForm,
    SupportSearchForm,
)
from ralph_assets.models_support import Support
from ralph_assets.views.base import AssetsBase
from ralph_assets.views.search import GenericSearch
from bob.data_table import DataTableColumn
from ralph_assets.models_assets import Asset
from django.utils.translation import ugettext_lazy as _
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from ralph_assets.views.sam import CheckBoxColumn


class SupportLinkColumn(DataTableColumn):
    """A column that links to the edit page of a support simply displaying
    'Support' in a grid"""
    def render_cell_content(self, resource):
        return '<a href="{url}">{support}</a>'.format(
            url=resource.url,
            support=unicode(_('Support')),
        )


class SupportView(AssetsBase):
    """Base view that displays support form."""

    submodule_name = 'supports'
    template_name = 'assets/add_support.html'
    mainmenu_selected = 'supports'
    sidebar_selected = None

    def _get_form(self, data=None, **kwargs):
        self.form = self.form_class(
            data=data, **kwargs
        )

    def get_context_data(self, **kwargs):
        ret = super(SupportView, self).get_context_data(**kwargs)
        ret.update({
            'form': self.form,
            'form_id': 'add_support_form',
            'edit_mode': False,
            'caption': self.caption,
            'support': getattr(self, 'support', None),
        })
        return ret

    def _save(self, request, *args, **kwargs):
        try:
            support = self.form.save(commit=False)
            support.save(user=self.request.user)
            self.form.save_m2m()
            messages.success(self.request, self.message)
            return HttpResponseRedirect(support.url)
        except ValueError:
            return super(SupportView, self).get(request, *args, **kwargs)


class AddSupportView(SupportView):
    """Add a new support"""
    caption = _('Add Support')
    message = _('Support added')
    active_sidebar_item = 'add support'

    def __init__(self, *args, **kwargs):
        self.form_class = AddSupportForm
        super(AddSupportView, self).__init__(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        self._get_form()
        return super(AddSupportView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self._get_form(request.POST)
        if self.form.is_valid():
            self.form.instance.pk = None
            support = self.form.save(commit=False)
            support.save(user=self.request.user)
            messages.success(self.request, self.message)
            return HttpResponseRedirect(reverse('support_list'))
        else:
            return super(AddSupportView, self).get(request, *args, **kwargs)


class SupportList(GenericSearch):
    """The support list."""

    submodule_name = 'supports'
    active_sidebar_item = 'search'
    Form = SupportSearchForm
    Model = Support

    columns = [
        CheckBoxColumn(
            _('Dropdown'),
            selectable=True,
            bob_tag=True,
        ),
        SupportLinkColumn(
            _('Type'),
            bob_tag=True,
        ),
        DataTableColumn(
            _('Contract id'),
            bob_tag=True,
            field='contract_id',
            sort_expression='contract_id',
        ),
        DataTableColumn(
            _('Name'),
            bob_tag=True,
            field='name',
            sort_expression='name',
        ),
        DataTableColumn(
            _('Date from'),
            bob_tag=True,
            field='date_from',
            sort_expression='date_from',
        ),
        DataTableColumn(
            _('Date to'),
            bob_tag=True,
            field='date_to',
            sort_expression='date_to',
        ),
        DataTableColumn(
            _('Price'),
            bob_tag=True,
            field='price',
            sort_expression='price',
        ),
        DataTableColumn(
            _('Created'),
            bob_tag=True,
            field='created',
            sort_expression='created',
        ),
    ]

    def get_context_data(self, *args, **kwargs):
        data = super(SupportList, self).get_context_data(
            *args, **kwargs
        )
        data['supports'] = Support.objects.all()
        return data


class EditSupportView(SupportView):
    """Edit support"""
    caption = _('Edit Support')
    message = _('Support changed')
    submodule_name = 'supports'
    Form = EditSupportForm
    detect_changes = True

    def __init__(self, *args, **kwargs):
        self.form_class = EditSupportForm
        super(EditSupportView, self).__init__(*args, **kwargs)

    def get(self, request, support_id, *args, **kwargs):
        self.support = Support.objects.get(pk=support_id)
        self._get_form(instance=self.support)
        return super(EditSupportView, self).get(request, *args, **kwargs)

    def post(self, request, support_id, *args, **kwargs):
        self.support = Support.objects.get(pk=support_id)
        self._get_form(request.POST, instance=self.support)
        return self._save(request, *args, **kwargs)


class DeleteSupportView(AssetsBase):
    """Delete a support."""
    submodule_name = 'supports'

    def post(self, *args, **kwargs):
        record_id = self.request.POST.get('record_id')
        self.back_to = reverse('support_list')
        try:
            support = Support.objects.get(pk=record_id)
        except Asset.DoesNotExist:
            messages.error(self.request, _("Selected asset doesn't exists."))
            return HttpResponseRedirect(self.back_to)
        support.delete(user=self.request.user)
        return HttpResponseRedirect(self.back_to)
