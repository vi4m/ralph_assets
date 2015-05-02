#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Model utilities and mixins."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.db import models
from lck.django.choices import Choices

from ralph.account.models import Region
from ralph import middleware
from datetime import datetime
from django.utils.translation import ugettext_lazy as _

class LastSeen(models.Model):
    last_seen = models.DateTimeField(verbose_name=_("last seen"),
                                 default=datetime.now)

    class Meta:
        abstract = True

    def save(self, update_last_seen=False, *args, **kwargs):
        if update_last_seen:
            self.last_seen = datetime.now()
        super(LastSeen, self).save(*args, **kwargs)


class SavingUser(models.Model):

    class Meta:
        abstract = True

    def save(self, user=None, *args, **kwargs):
        self.saving_user = user
        return super(SavingUser, self).save(user=user, *args, **kwargs)


class ProblemSeverity(Choices):
    _ = Choices.Choice
    warning = _("Warning")
    correct_me = _("Correct me")
    error = _("Error")


class ImportProblem(models.Model):
    """Any problem with importing the resource from XLS/CSV."""

    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    resource = generic.GenericForeignKey('content_type', 'object_id')
    severity = models.PositiveSmallIntegerField(choices=ProblemSeverity())
    message = models.TextField()

    def __str__(self):
        return self.message


def add_problem(resource, severity, message):
    """Add a problem to the resource
    :param resource: Any django model instance
    :param severity: An instance of `ralph_assets.models.util.ProblemSeverity`
    :param message: A string describing the problem"""
    problem = ImportProblem(
        severity=severity,
        message=message,
    )
    problem.resource = resource
    problem.save()


class RegionalizedDBManager(models.Manager):

    def get_query_set(self):
        query_set = super(RegionalizedDBManager, self).get_query_set()
        regions = middleware.get_actual_regions()
        query_set = query_set.filter(region__in=regions)
        return query_set


class Regionalized(models.Model):
    """Describes an abstract model with region definition in ``region`` field
    defined in ralph.accounts.models.Region"""

    objects = RegionalizedDBManager()
    admin_objects = models.Manager()

    region = models.ForeignKey(Region)

    class Meta:
        abstract = True

    def __unicode__(self):
        return self.region.name
