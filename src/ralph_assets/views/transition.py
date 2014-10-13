# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import logging
import uuid

from dj.choices import Country
from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.db.models import Q, Count
from django.http import Http404, HttpResponseRedirect
from django.template.defaultfilters import slugify
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView
from inkpy.api import generate_pdf
from lck.django.common import nested_commit_on_success

from ralph_assets import signals
from ralph_assets.forms_transitions import TransitionForm
from ralph_assets.models import ReportOdtSource, Transition, TransitionsHistory
from ralph_assets.utils import iso2_to_iso3
from ralph_assets.views.base import (
    ACLGateway,
    ActiveSubmoduleByAssetMixin,
    get_return_link,
)
from ralph_assets.views.invoice_report import generate_pdf_response
from ralph_assets.views.search import _AssetSearch


logger = logging.getLogger(__name__)


class PostTransitionException(Exception):
    """General exception to be thrown in *post_transition* signal receivers.
    Exception message is used to inform user."""


class TransitionDispatcher(object):
    """Handling actions defined in the transition.

    Available actions:
    - assign_user - assign user to assets.
    - change_status - change assets status to definied in Transition.
    - release_report - generate release assets report file.
    - return_report - generate return assets report file.
    """

    def __init__(
        self,
        instance,
        transition,
        assets,
        logged_user,
        affected_user,
        template_file=None,
        warehouse=None,
        loan_end_date=None,
        **kwargs
    ):
        self.instance = instance
        self.transition = transition
        self.assets = assets
        self.logged_user = logged_user
        self.affected_user = affected_user
        self.template_file = template_file
        self.warehouse = warehouse
        self.loan_end_date = loan_end_date
        self.report_file_patch = None
        self.uid = None
        self.kwargs = kwargs

    def _action_assign_user(self):
        for asset in self.assets:
            asset.user = self.affected_user
            asset.save(user=self.logged_user)

    def _action_assign_owner(self):
        for asset in self.assets:
            if not asset.owner:
                asset.owner = self.affected_user
            asset.save(user=self.logged_user)

    def _action_unassign_user(self):
        for asset in self.assets:
            asset.user = None
            asset.save(user=self.logged_user)

    def _action_assign_loan_end_date(self):
        for asset in self.assets:
            asset.loan_end_date = self.loan_end_date
            asset.save(user=self.logged_user)

    def _action_unassign_loan_end_date(self):
        for asset in self.assets:
            asset.loan_end_date = None
            asset.save(user=self.logged_user)

    def _action_unassign_owner(self):
        for asset in self.assets:
            asset.owner = None
            asset.save(user=self.logged_user)

    def _action_assign_warehouse(self):
        for asset in self.assets:
            asset.warehouse = self.warehouse
            asset.save(user=self.logged_user)

    def _action_change_status(self):
        for asset in self.assets:
            asset.status = self.transition.to_status
            asset.save(user=self.logged_user)

    def _action_unassign_licences(self):
        for asset in self.assets:
            asset.licence_set.clear()
            asset.save(user=self.logged_user)

    def _get_report_data(self):
        uid = uuid.uuid4()
        data = {
            'assets': self.assets,
            'logged_user': self.logged_user,
            'affected_user': self.affected_user,
            'datetime': datetime.datetime.now(),
            'id': uid,
        }
        return data, uid

    def _generate_report(self):
        data, self.uid = self._get_report_data()
        self.file_name = '{}-{}.pdf'.format(
            self.template_file.slug,
            data['id'],
        )
        output_path = '{}{}'.format(
            settings.ASSETS_REPORTS['TEMP_STORAGE_PATH'],
            self.file_name,
        )
        generate_pdf(
            self.template_file.template.path, output_path, data,
            settings.GENERATED_DOCS_LOCALE,
        )
        self.report_file_patch = output_path

    def _action_release_report(self):
        self._generate_report()

    def _action_return_report(self):
        self._generate_report()

    def _save_history(self):
        self.transition_history = TransitionsHistory.create(
            transition=self.transition,
            assets=self.assets,
            logged_user=self.logged_user,
            affected_user=self.affected_user,
            report_filename=self.file_name,
            uid=self.uid,
            report_file_path=self.report_file_patch,
        )

    def _action_change_hostname(self):
        for asset in self.assets:
            country_id = self.kwargs['request'].POST.get('country')
            country_name = Country.name_from_id(int(country_id)).upper()
            iso3_country_name = iso2_to_iso3[country_name]
            template_vars = {
                'code': asset.model.category.code,
                'country_code': iso3_country_name,
            }
            asset.generate_hostname(template_vars=template_vars)
            asset.save(user=self.logged_user)

    def get_transition_history_object(self):
        return self.transition_history

    def get_report_file_patch(self):
        return self.report_file_patch

    def get_report_file_name(self):
        return self.file_name

    @nested_commit_on_success
    def run(self):
        self.file_name = None
        actions = self.transition.actions_names
        if 'change_status' in actions:
            self._action_change_status()
        if 'assign_owner' in actions:
            self._action_assign_owner()
        elif 'unassign_owner' in actions:
            self._action_unassign_owner()
        if 'assign_user' in actions:
            self._action_assign_user()
        elif 'unassign_user' in actions:
            self._action_unassign_user()
        if 'assign_loan_end_date' in actions:
            self._action_assign_loan_end_date()
        elif 'unassign_loan_end_date' in actions:
            self._action_unassign_loan_end_date()
        if 'assign_warehouse' in actions:
            self._action_assign_warehouse()
        if 'unassign_licences' in actions:
            self._action_unassign_licences()
        if 'release_report' in actions:
            self._action_release_report()
        elif 'return_report' in actions:
            self._action_return_report()
        elif 'change_hostname' in actions:
            self._action_change_hostname()
        self._save_history()
        signals.post_transition.send(
            sender=self,
            user=self.logged_user,
            assets=self.assets,
            transition=self.instance.transition_object,
        )


class TransitionView(ActiveSubmoduleByAssetMixin, _AssetSearch):
    template_name = 'assets/transitions.html'
    report_file_path = None
    transition_history = None
    transition_ended = None

    def get_object_class(self):
        return self.get_assets()[0].__class__

    def get_return_link(self, *args, **kwargs):
        if self.ids:
            url = "{}search?id={}".format(
                get_return_link(self.mode), ",".join(self.ids),
            )
        else:
            url = "{}search?{}".format(
                get_return_link(self.mode), self.request.GET.urlencode(),
            )
        return url

    def get_transition_object(self, *args, **kwargs):
        try:
            transition = Transition.objects.get(
                slug=settings.ASSETS_TRANSITIONS['SLUGS'][
                    self.transition_type.upper()
                ]
            )
        except Transition.DoesNotExist:
            transition = None
        return transition

    def get_transition_form(self, *args, **kwargs):
        form = TransitionForm(self.request.POST)
        if not self.assign_user:
            form.fields.pop('user')
        if not self.assign_warehouse:
            form.fields.pop('warehouse')
        if not self.assign_loan_end_date:
            form.fields.pop('loan_end_date')
        if not self.change_hostname:
            form.fields.pop('country')
        return form

    def get_assets(self, *args, **kwargs):
        if self.request.GET.get('from_query'):
            all_q = super(
                TransitionView, self,
            ).handle_search_data(*args, **kwargs)
            self.ids = None
        else:
            self.ids = self.request.GET.getlist('select')
            all_q = Q(pk__in=self.ids)
        return self.get_all_items(all_q)

    def get_warehouse(self, *args, **kwargs):
        if 'assign_warehouse' in self.transition_object.actions_names:
            return self.form.cleaned_data.get('warehouse')

    def get_affected_user(self, *args, **kwargs):
        affected_user = self.form.cleaned_data.get('user')
        if not affected_user:
            affected_user = self.assets[0].user
        return affected_user

    def get_report_file_link(self, *args, **kwargs):
        if self.transition_history and self.transition_history.report_file:
            return reverse(
                'transition_history_file',
                kwargs={'history_id': self.transition_history.id},
            )

    def check_reports_template_exists(self, *args, **kwargs):
        error = False
        self.template_file = None
        if self.transition_object.required_report:
            try:
                self.template_file = ReportOdtSource.objects.get(
                    slug=settings.ASSETS_REPORTS[self.transition_type.upper()][
                        'SLUG'
                    ],
                )
                error = False
            except ReportOdtSource.DoesNotExist:
                messages.error(self.request, _("Odt template does not exist!"))
                error = True
        return error

    def base_error_handler(self, *args, **kwargs):
        not_required_user_transitions = ['change-hostname']
        required_user_transitions = ['return-asset']
        error = False
        self.assign_user = None
        if not settings.ASSETS_TRANSITIONS['ENABLE']:
            messages.error(self.request, _("Assets transitions is disabled"))
            error = True
        self.transition_type = self.request.GET.get('transition_type')
        if self.transition_type not in [
            'release-asset', 'return-asset', 'loan-asset', 'change-hostname',
        ]:
            messages.error(self.request, _("Unsupported transition type"))
            error = True
        self.transition_object = self.get_transition_object()
        if not self.transition_object:
            messages.error(self.request, _("Transition object not found"))
            error = True
        else:
            self.assign_user = (
                'assign_user' in self.transition_object.actions_names
            )
            self.assign_warehouse = (
                'assign_warehouse' in self.transition_object.actions_names
            )
            self.assign_loan_end_date = (
                'assign_loan_end_date' in self.transition_object.actions_names
            )
            self.change_hostname = (
                'change_hostname' in self.transition_object.actions_names
            )

        if (
            self.change_hostname
            and self.assets.filter(model__category__code='').count() > 0
        ):
            messages.error(
                self.request, _("Asset has no assigned category with code"),
            )
            error = True
        # check assets has assigned user
        if (
            self.transition_type in required_user_transitions
            or (
                not self.assign_user
                and self.transition_type not in not_required_user_transitions
            )
        ):
            assets = self.assets.values('user__username').distinct()
            assets_count = assets.annotate(cnt=Count('user')).count()
            if assets_count not in (0, 1):
                messages.error(
                    self.request,
                    _(
                        'Asset has different user: {}'.format(
                            ", ".join(
                                asset['user__username'] or 'unassigned'
                                for asset in assets,
                            )
                        )
                    ),
                )
                error = True
            elif not assets[0]['user__username']:
                messages.error(
                    self.request, _('Asset has no assigned user'),
                )
                error = True
        return error

    def post_error_handler(self, *args, **kwargs):
        error = self.base_error_handler()
        if not error:
            error = self.check_reports_template_exists()
        return error

    def get(self, *args, **kwargs):
        self.report_file_name = None
        self.assets = self.get_assets()
        errors = self.base_error_handler()
        if errors:
            return HttpResponseRedirect(self.get_return_link())
        self.form = self.get_transition_form()
        return super(TransitionView, self).get(*args, **kwargs)

    def post(self, *args, **kwargs):
        self.report_file_name = None
        self.assets = self.get_assets()
        errors = self.post_error_handler()
        self.form = self.get_transition_form()
        if self.form.is_valid() and not errors:
            dispatcher = TransitionDispatcher(
                self,
                self.transition_object,
                self.assets,
                self.request.user,
                self.get_affected_user(),
                self.template_file,
                self.get_warehouse(),
                loan_end_date=self.request.POST.get('loan_end_date'),
                request=self.request,
            )
            try:
                dispatcher.run()
            except PostTransitionException as e:
                self.transition_ended = False
                messages.error(self.request, _(e.message))
            else:
                self.report_file_path = dispatcher.report_file_patch
                self.report_file_name = dispatcher.get_report_file_name
                self.transition_history = dispatcher.get_transition_history_object()  # noqa
                messages.success(
                    self.request,
                    _("Transitions performed successfully"),
                )
                self.transition_ended = True
            finally:
                return super(TransitionView, self).get(*args, **kwargs)
        messages.error(self.request, _('Please correct errors.'))
        return super(TransitionView, self).get(*args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        ret = super(TransitionView, self).get_context_data(**kwargs)
        ret.update({
            'report_link': self.get_report_file_link(),
            'assets': self.assets,
            'transition_form': self.form,
            'transition_type': self.transition_type.replace('-', ' ').title(),
            'actions_names': self.transition_object.actions_names,
            'required_report': self.transition_object.required_report,
            'transition_ended': self.transition_ended,
        })
        return ret


class TransitionHistoryFileHandler(ACLGateway, TemplateView):
    def get_context_data(self, **kwargs):
        # we don't need data from TemplateView...
        return {}

    def raise_404_error(self):
        raise Http404(_("Transition history file not found"))

    def render_to_response(self, context, **response_kwargs):
        try:
            history_object = TransitionsHistory.objects.get(
                id=self.kwargs.get('history_id'),
            )
        except TransitionsHistory.DoesNotExist:
            self.raise_404_error()
        file_name = self.generate_file_name(history_object)
        pdf_data, error = self.get_file_content_from_history(history_object)
        if pdf_data and not error:
            return generate_pdf_response(pdf_data, file_name)
        self.raise_404_error()

    def get_file_content_from_history(self, history_object):
        try:
            content = history_object.report_file.read()
        except (IOError, ValueError) as e:
            logger.error(
                "Can not read transition history file: {} ({})".format(
                    history_object.id, e,
                )
            )
            return None, True
        return content, False

    def generate_file_name(self, history_object):
        name = "{}_{}_{}".format(
            history_object.created.date(),
            history_object.affected_user.get_full_name(),
            history_object.transition.name,
        )
        return slugify(name) + '.pdf'
