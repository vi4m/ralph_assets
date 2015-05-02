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
from ralph_assets.views.device import AddDevice, EditDevice, SplitDeviceView, EditDeviceComponents
from ralph_assets.views.user import EditUser, UserDetails, UserList
from ralph_assets.views.part import AddPart, EditPart
from ralph_assets.views.asset import (
    AssetSearch,
    AssetBulkEdit,
    DeleteAsset,
    ChassisBulkEdit,
)
from ralph_assets.views.ajax import (
    CategoryDependencyView,
    ModelDependencyView,
)
from ralph_assets.views.data_import import XlsUploadView
from ralph_assets.views.support import (
    SupportList,
    AddSupportView,
    EditSupportView,
    DeleteSupportView,
)
from ralph_assets.views.invoice_report import AssetInvoiceReport
from ralph_assets.forms_import import XLS_UPLOAD_FORMS
from ralph_assets.views.transition import (
    TransitionView,
    TransitionHistoryFileHandler,
)
from ralph_assets.views.report import ReportsList, ReportDetail
from ralph_assets.rest.urls import urlpatterns as rest_urlpatterns


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
    url(r'^api/', include(v09_api.urls + rest_urlpatterns)),
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
    url(r'(?P<mode>(back_office|dc))/edit/device/(?P<asset_id>[0-9]+)/components/$',
        login_required(EditDeviceComponents.as_view()),
        name='device_components_edit'),
    url(r'(?P<mode>(back_office|dc))/edit/part/(?P<asset_id>[0-9]+)/$',
        login_required(EditPart.as_view()),
        name='part_edit'),


    url(r'(?P<mode>(dc))/edit_location_data/$',
        login_required(ChassisBulkEdit.as_view()),
        name='edit_location_data'),


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
        r'delete/(?P<parent>(asset|license|support))/attachment/$',
        login_required(DeleteAttachment.as_view()),
        name='delete_attachment',
    ),
    url(
        r'^users/$',
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
        r'reports/(?P<mode>\S+)/(?P<dc>\S+)/(?P<slug>\S+)$',
        login_required(ReportDetail.as_view()),
        name='report_detail',
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
    url(
        r'^licences/',
        include('ralph_assets.licences.urls', app_name='licences'),
    ),
)
