#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Model utilities and mixins."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.db import models
from lck.django.choices import Choices


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


class WithForm(object):
    """A generic resource that has an edit form and can tell you what is its
    URL."""

    @abc.abstractproperty
    def url(self):
        """Return the url of edit for for this resource."""
