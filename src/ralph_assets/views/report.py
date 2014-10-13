# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import uuid

from bob import csvutil
from bob.menu import MenuItem, MenuHeader
from django.core.urlresolvers import reverse
from django.db.models import Count
from django.http import Http404
from django.utils.translation import ugettext_lazy as _

from ralph.util.reports import Report
from ralph.discovery.models_device import Device
from ralph_assets.views.base import AssetsBase
from ralph_assets.others import get_assets_rows, get_licences_rows
from ralph_assets.models_assets import (
    Asset,
    AssetModel,
    AssetStatus,
    DeviceInfo,
    MODE2ASSET_TYPE,
)


logger = logging.getLogger(__name__)


def get_desc(choices_class, key, default='------'):
    return choices_class.from_id(key) if key else default


class ReportNode(object):
    """The basic report node. It is simple object which store name, count,
    parent and children."""
    def __init__(self, name, count=0, parent=None, children=[],
                 link=None, **kwargs):
        self.name = name
        self.count = count
        self.parent = parent
        self.children = []
        self.link = link
        self.uid = uuid.uuid1()

    def add_child(self, child):
        self.children.append(child)
        child.parent = self

    def add_to_count(self, count):
        self.count += count

    def update_count(self):
        map(lambda node: node.add_to_count(self.count), self.ancestors)

    @property
    def ancestors(self):
        parent = self.parent
        while parent:
            yield parent
            parent = parent.parent

    def to_dict(self):
        return {
            'name': self.name,
            'count': self.count,
        }

    def __str__(self):
        return '{} ({})'.format(self.name, self.count)


class ReportContainer(list):
    """Container for nodes. This class provides few helpful methods to
    manipulate on node set."""
    def get(self, name):
        return next((node for node in self if node.name == name), None)

    def get_or_create(self, name):
        node = self.get(name)
        created = False
        if not node:
            node = ReportNode(name)
            self.append(node)
            created = True
        return node, created

    def add(self, name, count=0, parent=None, unique=True, link=None):
        if unique:
            new_node, created = self.get_or_create(name)
        else:
            new_node = ReportNode(name)
            self.append(new_node)
            created = True
        new_node.count = count
        if parent:
            if not isinstance(parent, ReportNode):
                parent, __ = self.get_or_create(parent)
        if created:
            parent.add_child(new_node)
        new_node.link = link
        return new_node, parent

    @property
    def roots(self):
        return [node for node in self if node.parent is None]

    @property
    def leaves(self):
        return [node for node in self if node.children == []]

    def to_dict(self):
        def traverse(node):
            ret = node.to_dict()
            ret['children'] = []
            for child in node.children:
                ret['children'].append(traverse(child))
            return ret
        return [traverse(root) for root in self.roots]


class BaseReport(object):
    """Each report must inherit from this class."""
    with_modes = True
    with_counter = True
    links = False
    template_name = None

    def __init__(self):
        self.report = ReportContainer()

    def execute(self, mode):
        self.mode = mode
        self.prepare(mode)
        map(lambda x: x.update_count(), self.report.leaves)
        return self.report.roots

    def prepare(self, mode):
        raise NotImplemented()

    def is_async(self, request):
        return False


class CategoryModelReport(BaseReport):
    slug = 'category-model'
    name = _('Category - model')

    def prepare(self, mode):
        queryset = Asset.objects
        if mode:
            queryset = queryset.filter(type=mode)
        queryset = queryset.select_related('model', 'category').values(
            'model__category__name',
            'model__name',
        ).annotate(
            num=Count('model')
        ).order_by('model__category__name')

        for item in queryset:
            cat = item['model__category__name'] or 'None'
            self.report.add(
                name=item['model__name'],
                parent=cat,
                count=item['num'],
            )


class CategoryModelStatusReport(BaseReport):
    slug = 'category-model-status'
    name = _('Category - model - status')

    def prepare(self, mode):
        queryset = Asset.objects
        if mode:
            queryset = queryset.filter(type=mode)
        queryset = queryset.select_related('model', 'category').values(
            'model__category__name',
            'model__name',
            'status',
        ).annotate(
            num=Count('status')
        ).order_by('model__category__name')

        for item in queryset:
            parent = item['model__category__name'] or 'Without category'
            name = item['model__name']
            node, __ = self.report.add(
                name=name,
                parent=parent,
            )
            self.report.add(
                name=get_desc(AssetStatus, item['status']),
                parent=node,
                count=item['num'],
                unique=False
            )


class ManufacturerCategoryModelReport(BaseReport):
    slug = 'manufactured-category-model'
    name = _('Manufactured - category - model')

    def prepare(self, mode=None):
        queryset = AssetModel.objects
        if mode:
            queryset = queryset.filter(type=mode)
        queryset = queryset.select_related('manufacturer', 'category').values(
            'manufacturer__name',
            'category__name',
            'name',
        ).annotate(
            num=Count('assets')
        ).order_by('manufacturer__name')

        for item in queryset:
            manufacturer = item['manufacturer__name'] or 'Without manufacturer'
            node, __ = self.report.add(
                name=item['category__name'],
                parent=manufacturer,
            )
            self.report.add(
                name=item['name'],
                parent=node,
                count=item['num'],
            )


class StatusModelReport(BaseReport):
    slug = 'status-model'
    name = _('Status - model')

    def prepare(self, mode=None):
        queryset = Asset.objects
        if mode:
            queryset = queryset.filter(type=mode)
        queryset = queryset.values(
            'status',
            'model__name',
        ).annotate(
            num=Count('model')
        )
        for item in queryset:
            self.report.add(
                name=item['model__name'],
                count=item['num'],
                parent=get_desc(AssetStatus, item['status']),
            )


class LinkedDevicesReport(BaseReport):
    slug = 'asset-device'
    name = _('Asset - device')
    with_modes = False
    links = True

    def prepare(self, mode=None):
        assets = Asset.objects.raw("""
        SELECT a.*
        FROM
            ralph_assets_asset a
        JOIN
            ralph_assets_deviceinfo di ON di.id=a.device_info_id
        JOIN
            discovery_device e on a.sn=e.sn or a.barcode=e.barcode
        WHERE
            di.ralph_device_id IS NULL
            OR di.ralph_device_id=0
            AND a.deleted=0
        """)

        ids = []
        root = None
        for asset in assets:
            ids.append(str(asset.id))
            link = {
                'label': 'go to asset',
                'url': asset.url,
            }

            node, root = self.report.add(
                parent=_('Matched SN or barcode but without linked device'),
                name='SN: %s, barcode: %s' % (asset.sn, asset.barcode),
                count=1,
                link=link,
                unique=False,
            )
        if root:
            root.link = {
                'label': 'go to search',
                'url': '/assets/dc/search?id={}'.format(','.join(ids)),
            }

        assets = Asset.objects.raw("""
        SELECT a.*
        FROM
            ralph_assets_asset a
        JOIN
            ralph_assets_deviceinfo di ON di.id=a.device_info_id
        WHERE
            di.ralph_device_id IS NULL
            AND a.deleted=0
        """)
        ids = []
        for asset in assets:
            ids.append(str(asset.id))
            link = {
                'label': 'go to asset',
                'url': asset.url,
            }
            node, root = self.report.add(
                parent=_('Assets without linked device'),
                name='SN: %s, barcode: %s' % (asset.sn, asset.barcode),
                count=1,
                link=link,
                unique=False,
            )
        if root:
            root.link = {
                'label': 'go to search',
                'url': '/assets/dc/search?id={}'.format(','.join(ids)),
            }

        device_info_ids = DeviceInfo.objects.exclude(
            ralph_device_id=None
        ).values_list(
            'ralph_device_id', flat=True
        )
        devices = Device.objects.exclude(id__in=device_info_ids)
        node, root = self.report.add(
            parent=_('Devices without linked asset'),
            name=str('Total'),
            count=devices.count()
        )
        root.link = {
            'label': 'go to search',
            'url': '/ui/search/info/?without_asset=on'
        }


class BaseRelationsReport(BaseReport):
    template_name = 'assets/report_relations.html'
    with_modes = True
    links = False

    def prepare(self, *args, **kwargs):
        pass

    def is_async(self, request):
        self.export = request.GET.get('csv')
        return self.export == 'on'

    def get_response(self, request, result):
        return csvutil.make_csv_response(data=result, filename=self.filename)


class AssetRelationsReport(BaseRelationsReport):
    slug = 'asset-relations'
    name = _('Asset - relations')
    filename = 'asset_relations.csv'

    def get_result(self, *args, **kwargs):
        filter_type = kwargs.get('mode')
        return list(get_assets_rows(filter_type=filter_type))


class LicenceRelationsReport(BaseRelationsReport):
    slug = 'licence-relations'
    name = _('Licence - relations')
    filename = 'licence_relations.csv'

    def get_result(self, *args, **kwargs):
        filter_type = kwargs.get('mode')
        data = []
        for row in get_licences_rows(filter_type, True):
            data.append([item.decode('utf-8') for item in row])
        return data


class ReportViewBase(AssetsBase):
    submodule_name = 'assets_reports'
    reports = [
        CategoryModelReport,
        CategoryModelStatusReport,
        ManufacturerCategoryModelReport,
        StatusModelReport,
        LinkedDevicesReport,
        AssetRelationsReport,
        LicenceRelationsReport,
    ]
    modes = [
        {
            'name': 'all',
            'verbose_name': 'All',
        },
        {
            'name': 'dc',
            'verbose_name': 'Only data center',
        },
        {
            'name': 'back_office',
            'verbose_name': 'Only back office',
        },
    ]

    def get_sidebar_items(self, base_sidebar_caption):
        sidebar_menu = []
        sidebar_menu += [MenuHeader(_('Reports'))]
        sidebar_menu += [
            MenuItem(
                label=report.name, href=reverse('report_detail', kwargs={
                    'mode': 'all',
                    'slug': report.slug,
                })
            )
            for report in self.reports
        ]
        sidebar_menu.extend(super(ReportViewBase, self).get_sidebar_items(
            base_sidebar_caption
        ))
        return sidebar_menu


class ReportsList(ReportViewBase):
    template_name = 'assets/report_list.html'


class ReportDetail(Report, ReportViewBase):
    template_name = 'assets/report_detail.html'

    @property
    def active_sidebar_item(self):
        return self.report.name

    def get_report(self, slug):
        for report in self.reports:
            if report.slug == slug:
                return report()
        return None

    def get_template_names(self, *args, **kwargs):
        return [self.report.template_name or self.template_name]

    def is_async(self, request, *args, **kwargs):
        return self.report.is_async(request)

    def get_result(self, request, *args, **kwargs):
        report = self.get_report(kwargs.get('slug'))
        return report.get_result(*args, **kwargs)

    def get_response(self, request, result):
        return self.report.get_response(request, result)

    def dispatch(self, request, *args, **kwargs):
        self.slug = kwargs.pop('slug')
        self.asset_type = MODE2ASSET_TYPE.get(kwargs.get('mode'), None)
        self.report = self.get_report(self.slug)
        if not self.report:
            raise Http404
        return super(ReportDetail, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context_data = super(ReportDetail, self).get_context_data(**kwargs)
        context_data.update({
            'report': self.report,
            'subsection': self.report.name,
            'result': self.report.execute(self.asset_type),
            'cache_key': (str(self.asset_type) or 'all') + self.slug,
            'modes': self.modes,
            'slug': self.slug,
        })
        return context_data
