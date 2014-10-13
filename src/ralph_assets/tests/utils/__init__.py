# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from functools import partial

from factory import (
    lazy_attribute,
    Sequence,
    SubFactory,
)
from factory.django import DjangoModelFactory, FileField

from django.test.client import Client
from django.template.defaultfilters import slugify

from ralph.ui.tests.global_utils import UserFactory
from ralph_assets.models_assets import Attachment
from ralph_assets.models import ReportOdtSource


class AttachmentFactory(DjangoModelFactory):
    FACTORY_FOR = Attachment

    original_filename = Sequence(lambda n: 'original_filename'.format(n))
    file = FileField(
        data=b'uploaded_file_content', filename='uploaded_filename.txt',
    )
    uploaded_by = SubFactory(UserFactory)


class ReportOdtSourceFactory(DjangoModelFactory):
    FACTORY_FOR = ReportOdtSource
    name = Sequence(lambda n: 'Report ODT #%s' % n)
    template = FileField(
        data=b'uploaded_file_content', filename='uploaded_filename.txt',
    )

    @lazy_attribute
    def slug(self):
        return slugify(self.name)


class AdminFactory(UserFactory):
    is_staff = True
    is_superuser = True


class MessagesTestMixin(object):
    def assertMessageEqual(self, response, text):
        """
        Asserts that the response includes the message text.
        """
        messages = [m.message for m in response.context['messages']]
        if text not in messages:
            self.fail(
                'No message with text "{}", messages were: {}'.format(
                    text, messages,
                )
            )


class AjaxClient(Client):
    """
    Dirty add methods: ajax_get, ajax_post, ajax_put, ajax_delete.
    """
    def __getattribute__(self, name):
        methods = ['get', 'post', 'put', 'delete']
        if name in ['ajax_{}'.format(method) for method in methods]:
            func_name = name.split('_')[1]
            func = super(AjaxClient, self).__getattribute__(func_name)
            return partial(func, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        else:
            return super(AjaxClient, self).__getattribute__(name)


class ClientMixin(object):

    def login_as_user(self, user=None, password='ralph', *args, **kwargs):
        if not user:
            user = UserFactory(*args, **kwargs)
            user.set_password(password)
            user.save()
        self.client.login(username=user.username, password=password)

    def login_as_superuser(self):
        self.login_as_user(AdminFactory())
