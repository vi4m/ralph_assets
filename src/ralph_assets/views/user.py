# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from bob.data_table import DataTableMixin

from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _

from ralph.util.reports import Report
from ralph_assets.models import Asset, TransitionsHistory
from ralph_assets.views.base import AssetsBase, DataTableColumnAssets
from ralph_assets.forms import UserRelationForm, SearchUserForm


MAX_PAGE_SIZE = 65535
HISTORY_PAGE_SIZE = 25

logger = logging.getLogger(__name__)


class UserDetails(AssetsBase):
    """Detail user profile, relations with assets and licences"""
    template_name = 'assets/user_details.html'
    sidebar_selected = None
    submodule_name = 'users'

    def get(self, request, username, *args, **kwargs):
        try:
            self.user = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(request, _('User {} not found'.format(username)))
            return HttpResponseRedirect(reverse('user_list'))
        self.assigned_assets = Asset.objects.filter(user=self.user)
        self.assigned_licences = self.user.licence_set.all()
        self.transitions_history = TransitionsHistory.objects.filter(
            affected_user=self.user,
        )
        return super(UserDetails, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ret = super(UserDetails, self).get_context_data(**kwargs)
        ret.update({
            'user_object': self.user,
            'assigned_assets': self.assigned_assets,
            'assigned_licences': self.assigned_licences,
            'transitions_history': self.transitions_history,
        })
        return ret


class UserList(Report, AssetsBase, DataTableMixin):
    """List of users in system."""

    template_name = 'assets/user_list.html'
    csv_file_name = 'users'
    sort_variable_name = 'sort'
    submodule_name = 'users'
    _ = DataTableColumnAssets
    columns = [
        _(
            'Username',
            bob_tag=True,
            field='username',
            sort_expression='username',
        ),
        _(
            'Edit relations',
            bob_tag=True
        ),
    ]
    sort_expression = 'user__username'

    def get_context_data(self, *args, **kwargs):
        ret = super(UserList, self).get_context_data(*args, **kwargs)
        ret.update(
            super(UserList, self).get_context_data_paginator(
                *args,
                **kwargs
            )
        )
        ret.update({
            'sort_variable_name': self.sort_variable_name,
            'url_query': self.request.GET,
            'sort': self.sort,
            'columns': self.columns,
            'form': SearchUserForm(self.request.GET),
        })
        return ret

    def get(self, *args, **kwargs):
        users = self.handle_search_data(*args, **kwargs)
        self.data_table_query(users)
        if self.export_requested():
            return self.response
        return super(UserList, self).get(*args, **kwargs)

    def handle_search_data(self, *args, **kwargs):
        q = Q()
        if self.request.GET.get('user'):
            q &= Q(id=self.request.GET['user'])
        if self.request.GET.get('user_text'):
            q &= Q(username__contains=self.request.GET['user_text'])
        return User.objects.filter(q).all()


class EditUser(AssetsBase):
    """An assets-specific user view."""

    template_name = 'assets/user_edit.html'
    caption = _('Edit user relations')
    message = _('Licence changed')
    submodule_name = 'users'

    def prepare(self, username):
        self.user = User.objects.get(username=username)

    def get(self, request, username, *args, **kwargs):
        self.prepare(username)
        self.form = UserRelationForm(user=self.user)
        return super(EditUser, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ret = super(EditUser, self).get_context_data(**kwargs)
        ret.update({
            'form': self.form,
            'form_id': 'user_relation_form',
            'caption': self.caption,
            'edited_user': self.user,
        })
        return ret

    def post(self, request, username, *args, **kwargs):
        self.prepare(username)
        self.form = UserRelationForm(data=request.POST, user=self.user)
        if self.form.is_valid():
            self.user.licence_set.clear()
            for licence in self.form.cleaned_data.get('licences'):
                self.user.licence_set.add(licence)
            messages.success(request, _('User relations updated'))
            return HttpResponseRedirect(
                reverse(
                    'edit_user_relations',
                    kwargs={'username': self.user.username}
                )
            )
        else:
            return super(EditUser, self).get(request, *args, **kwargs)
