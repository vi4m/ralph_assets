# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import logging

from inkpy.api import generate_pdf

from django.db.models import Sum, Q
from django.contrib import messages
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.template.defaultfilters import slugify
from django.utils.translation import ugettext_lazy as _

from ralph_assets.forms_sam import LicenceSearchForm
from ralph_assets.models import (
    Asset,
    Licence,
    ReportOdtSource,
)
from ralph_assets.views.base import get_return_link
from ralph_assets.views.sam import LicenseSelectedMixin
from ralph_assets.views.search import AssetsSearchQueryableMixin, GenericSearch


logger = logging.getLogger(__name__)

# ugly hack to mock it in tests
generate_pdf = generate_pdf


def generate_pdf_response(pdf_data, file_name):
    response = HttpResponse(
        content=pdf_data, content_type='application/pdf',
    )
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(
        file_name,
    )
    return response


class BaseInvoiceReport(GenericSearch):
    submodule_name = 'unknown'

    def show_unique_error_message(self, *args, **kwargs):
        non_unique = {}
        for name in ['invoice_no', 'invoice_date', 'provider']:
            items = self.items.values(name).distinct()
            if items.count() != 1:
                if name == 'invoice_date':
                    data = ", ".join(
                        item[name].strftime(
                            "%d-%m-%Y"
                        ) for item in items if item[name]
                    )
                else:
                    data = ", ".join(
                        item[name] for item in items if item[name]
                    )
                non_unique[name] = data
        non_unique_items = " ".join(
            [
                "{}: {}".format(
                    key, value,
                ) for key, value in non_unique.iteritems() if value
            ]
        )
        messages.error(
            self.request,
            "{}: {}".format(
                _("Selected items has different"),
                non_unique_items,
            )
        )

    def valid(self, *args, **kwargs):
        error = False
        try:
            self.template_file = ReportOdtSource.objects.get(
                slug=settings.ASSETS_REPORTS['INVOICE_REPORT']['SLUG'],
            )
        except ReportOdtSource.DoesNotExist:
            messages.error(self.request, _("Odt template does not exist!"))
            error = True
        self.ids = self.request.GET.getlist('select')
        self.items = self.get_all_items()
        item_distinct = self.items.values(
            'invoice_no', 'invoice_date', 'provider',
        ).distinct()
        if item_distinct.count() != 1:
            self.show_unique_error_message()
            error = True
        if not all(item_distinct[0].viewvalues()):
            messages.error(self.request, _(
                "Invoice number, invoice date or provider can't be empty"
            ))
            error = True
        return error

    def get(self, *args, **kwargs):
        if not settings.ASSETS_REPORTS['ENABLE']:
            messages.error(self.request, _("Assets reports is disabled"))
            return HttpResponseRedirect(get_return_link(self.mode))
        if self.valid():
            return HttpResponseRedirect(self.get_return_link())
        # generate invoice report
        pdf_data, file_name = self.get_pdf_content()
        if not all((pdf_data, file_name)):
            return HttpResponseRedirect(self.get_return_link())
        return generate_pdf_response(pdf_data, file_name)

    def get_pdf_content(self, *args, **kwargs):
        content = None
        data = self.get_report_data()
        file_name = '{}-{}.pdf'.format(
            self.template_file.slug, data['id'],
        )
        output_path = '{}{}'.format(
            settings.ASSETS_REPORTS['TEMP_STORAGE_PATH'], file_name,
        )
        generate_pdf(
            self.template_file.template.path, output_path, data,
            settings.GENERATED_DOCS_LOCALE,
        )
        try:
            with open(output_path, 'rb') as f:
                content = f.read()
                f.close()
        except IOError as e:
            logger.error(
                "Can not read report for items ids: {} ({})".format(
                    ",".join(id for id in self.ids), e,
                )
            )
            messages.error(self.request, _(
                "The error occurred, was not possible to read generated file."
            ))
        return content, file_name

    def get_report_data(self, *args, **kwargs):
        first_item = self.items[0]
        data = {
            "id": slugify(first_item.invoice_no),
            "base_info": {
                "invoice_no": first_item.invoice_no,
                "invoice_date": first_item.invoice_date,
                "provider": first_item.provider,
                "datetime": datetime.datetime.now(),
            },
            "items": self.items,
            "sum_price": self.items.aggregate(Sum('price')).get('price__sum')
        }
        return data


class AssetInvoiceReport(AssetsSearchQueryableMixin, BaseInvoiceReport):
    submodule_name = 'unknown'

    def get_all_items(self, *args, **kwargs):
        if self.request.GET.get('from_query'):
            query = super(
                AssetInvoiceReport, self,
            ).handle_search_data(*args, **kwargs)
        else:
            query = Q(pk__in=self.ids)
        return Asset.objects.filter(query)

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


class LicenceInvoiceReport(LicenseSelectedMixin, BaseInvoiceReport):
    submodule_name = 'unknown'

    def get_all_items(self, *args, **kwargs):
        if self.request.GET.get('from_query'):
            form = LicenceSearchForm(self.request.GET)
            query = form.get_query()
        else:
            query = Q(pk__in=self.ids)
        return Licence.objects.filter(query)

    def get_return_link(self, *args, **kwargs):
        if self.ids:
            url = "{}?id={}".format(
                reverse('licence_list'), ",".join(self.ids),
            )
        else:
            url = "{}?{}".format(
                reverse('licence_list'), self.request.GET.urlencode(),
            )
        return url
