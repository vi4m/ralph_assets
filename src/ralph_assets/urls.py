# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from django.conf.urls.defaults import include, patterns, url
from django.contrib.auth.decorators import login_required
from django.views.generic import RedirectView
from tastypie.api import Api

from ralph_assets.api import (
    AssetManufacturerResource,
    AssetModelResource,
    AssetOwnerResource,
    AssetsResource,
    LicenceResource,
    LicenceTypeResource,
    ServiceResource,
    SoftwareCategoryResource,
    UserAssignmentsResource,
    UserResource,
    WarehouseResource,
)
from ralph_assets.views.attachment import AddAttachment, DeleteAttachment
from ralph_assets.views.device import AddDevice, EditDevice, SplitDeviceView
from ralph_assets.views.user import EditUser, UserDetails, UserList
from ralph_assets.views.part import AddPart, EditPart
from ralph_assets.views.asset import (
    AssetSearch,
    AssetBulkEdit,
    DeleteAsset,
)
from ralph_assets.views.ajax import CategoryDependencyView, ModelDependencyView
from ralph_assets.views.data_import import XlsUploadView
from ralph_assets.views.sam import (
    AddLicence,
    CountLicence,
    DeleteLicence,
    EditLicence,
    LicenceList,
    LicenceBulkEdit,
    SoftwareCategoryList,
)
from ralph_assets.views.support import (
    SupportList,
    AddSupportView,
    EditSupportView,
    DeleteSupportView,
)
from ralph_assets.views.invoice_report import (
    AssetInvoiceReport,
    LicenceInvoiceReport,
)
from ralph_assets.forms_import import XLS_UPLOAD_FORMS
from ralph_assets.views.transition import (
    TransitionView,
    TransitionHistoryFileHandler,
)
from ralph_assets.views.report import ReportsList, ReportDetail

v09_api = Api(api_name='v0.9')
for r in (
    AssetManufacturerResource,
    AssetModelResource,
    AssetOwnerResource,
    AssetsResource,
    LicenceResource,
    LicenceTypeResource,
    ServiceResource,
    SoftwareCategoryResource,
    UserAssignmentsResource,
    UserResource,
    WarehouseResource,
):
    v09_api.register(r())


def normalize_asset_mode(mode):
    modes = {
        'data_center': 'dc',
    }
    normalized_mode = modes.get(mode, mode)
    return normalized_mode


urlpatterns = patterns(
    '',
    url(r'^api/', include(v09_api.urls)),
    url(r'^$',
        RedirectView.as_view(url='/assets/dc/search'),
        name='dc'),
    url(r'dc/$', RedirectView.as_view(url='/assets/dc/search'),
        name='dc'),
    url(r'back_office/$',
        RedirectView.as_view(url='/assets/back_office/search'),
        name='bo'),

    url(r'(?P<mode>(back_office|dc))/search',
        login_required(AssetSearch.as_view()),
        name='asset_search'),
    url(r'(?P<mode>(back_office|dc))/add/device/',
        login_required(AddDevice.as_view()),
        name='add_device'),
    url(r'(?P<mode>(back_office|dc))/add/part/',
        login_required(AddPart.as_view()),
        name='add_part'),
    url(r'(?P<mode>(back_office|dc))/edit/device/(?P<asset_id>[0-9]+)/$',
        login_required(EditDevice.as_view()),
        name='device_edit'),
    url(r'(?P<mode>(back_office|dc))/edit/part/(?P<asset_id>[0-9]+)/$',
        login_required(EditPart.as_view()),
        name='part_edit'),
    url(r'ajax/dependencies/category/$',
        CategoryDependencyView.as_view(),
        name='category_dependency_view'),
    url(r'ajax/dependencies/model/$',
        ModelDependencyView.as_view(),
        name='model_dependency_view'),
    url(r'(?P<mode>(back_office|dc))/bulkedit/$',
        login_required(AssetBulkEdit.as_view()),
        name='bulkedit'),
    url(r'(?P<mode>(back_office|dc))/delete/asset/$',
        login_required(DeleteAsset.as_view()),
        name='dc'),
    url(r'(?P<mode>(back_office|dc))/split/asset/(?P<asset_id>[0-9]+)/$',
        login_required(SplitDeviceView.as_view()),
        name='device_split'),
    url(
        r'(?P<mode>(back_office|dc))/invoice_report/$',
        login_required(AssetInvoiceReport.as_view()),
        name='assets_invoice_report',
    ),
    url(
        r'sam/licences/invoice_report/$',
        login_required(LicenceInvoiceReport.as_view()),
        name='sam_invoice_report',
    ),
    url(
        r'(?P<mode>(back_office|dc))/transition/$',
        login_required(TransitionView.as_view()),
        name='transition',
    ),
    url(
        r'add_attachment/(?P<parent>(asset|license|support))/$',
        login_required(AddAttachment.as_view()),
        name='add_attachment'
    ),
    url(
        r'xls/$',
        login_required(XlsUploadView.as_view(XLS_UPLOAD_FORMS)),
        name='xls_upload',
    ),
    url(
        r'sam/categories/$',
        login_required(SoftwareCategoryList.as_view()),
        name='software_categories',
    ),
    url(
        r'sam/licences/$',
        login_required(LicenceList.as_view()),
        name='licence_list',
    ),
    url(
        r'sam/licences/bulkedit/',
        login_required(LicenceBulkEdit.as_view()),
        name='licence_bulkedit',
    ),
    url(
        r'sam/add_licence/$',
        login_required(AddLicence.as_view()),
        name='add_licence',
    ),
    url(
        r'sam/edit_licence/(?P<licence_id>[0-9]+)$',
        login_required(EditLicence.as_view()),
        name='edit_licence',
    ),
    url(
        r'sam/count_licences/$',
        login_required(CountLicence.as_view()),
        name='count_licences',
    ),
    url(
        r'support/$',
        login_required(SupportList.as_view()),
        name='support_list',
    ),
    url(
        r'support/add/$',
        login_required(AddSupportView.as_view()),
        name='add_support',
    ),
    url(
        r'support/edit/(?P<support_id>[0-9]+)$',
        login_required(EditSupportView.as_view()),
        name='edit_support',
    ),
    url(
        r'support/delete/$',
        login_required(DeleteSupportView.as_view()),
        name='delete_support',
    ),
    url(
        r'(?P<mode>(back_office|dc))/sam/delete/$',
        login_required(DeleteLicence.as_view()),
        name='delete_licence',
    ),
    url(
        r'delete/(?P<parent>(asset|license|support))/attachment/$',
        login_required(DeleteAttachment.as_view()),
        name='delete_attachment',
    ),
    url(
        r'users/$',
        login_required(UserList.as_view()),
        name='user_list',
    ),
    url(
        r'user/relations/(?P<username>[^\/]+)/$',
        login_required(EditUser.as_view()),
        name='edit_user_relations',
    ),
    url(
        r'user/details/(?P<username>[^\/]+)/$',
        login_required(UserDetails.as_view()),
        name='user_view',
    ),
    url(
        r'transition-history-file/(?P<history_id>[0-9]+)$',
        login_required(TransitionHistoryFileHandler.as_view()),
        name='transition_history_file',
    ),
    url(
        r'reports/$',
        login_required(ReportsList.as_view()),
        name='assets_reports',
    ),
    url(
        r'reports/(?P<mode>\S+)/(?P<slug>\S+)$',
        login_required(ReportDetail.as_view()),
        name='report_detail',
    ),
    url(
        r'^history/',
        include('ralph_assets.history.urls', app_name='history'),
    ),
)
