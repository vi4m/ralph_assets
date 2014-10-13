# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import itertools
import random

import factory

from factory import (
    fuzzy,
    lazy_attribute,
    Sequence,
    SubFactory,
)
from factory.django import DjangoModelFactory
from uuid import uuid1

from django.template.defaultfilters import slugify

from ralph.cmdb.tests.utils import (
    CIRelationFactory,
    DeviceEnvironmentFactory,
    ServiceCatalogFactory,
)
from ralph_assets import models_assets
from ralph_assets.models_assets import (
    Asset,
    AssetCategory,
    AssetCategoryType,
    AssetManufacturer,
    AssetModel,
    AssetOwner,
    AssetPurpose,
    AssetStatus,
    AssetSource,
    AssetType,
    CoaOemOs,
    DeviceInfo,
    OfficeInfo,
    Service,
    Warehouse,
)
from ralph_assets.tests.utils import UserFactory

category_code_set = 'ABCDEFGHIJKLMNOPRSTUVWXYZ1234567890'
category_code_combinations = itertools.product(category_code_set, repeat=2)


def generate_sn():
    return str(uuid1())


def generate_barcode():
    return str(uuid1())


def generate_imei(n):
    """Random IMEI generator. This function return random but not unique
    IMEI number. Based on code from http://stackoverflow.com/a/20733310
    """
    def luhn_residue(digits):
        """Luhn algorithm"""
        return sum(sum(divmod(int(d) * (1 + i % 2), 10))
                   for i, d in enumerate(digits[::-1])) % 10

    part = ''.join(str(random.randrange(0, 9)) for _ in range(n - 1))
    res = luhn_residue('{}{}'.format(part, 0))
    return '{}{}'.format(part, -res % 10)


class CoaOemOsFactory(DjangoModelFactory):
    FACTORY_FOR = CoaOemOs

    name = Sequence(lambda n: 'COA OEM OS #%s' % n)


class OfficeInfoFactory(DjangoModelFactory):
    FACTORY_FOR = OfficeInfo

    coa_oem_os = SubFactory(CoaOemOsFactory)
    purpose = AssetPurpose.others

    @lazy_attribute
    def imei(self):
        return generate_imei(15)

    @lazy_attribute
    def license_key(self):
        return str(uuid1())

    @lazy_attribute
    def coa_number(self):
        return str(uuid1())


class ServiceFactory(DjangoModelFactory):
    FACTORY_FOR = Service

    name = Sequence(lambda n: 'Service #%s' % n)


class AssetOwnerFactory(DjangoModelFactory):
    FACTORY_FOR = AssetOwner

    name = Sequence(lambda n: 'Asset owner #%s' % n)


class AssetCategoryFactory(DjangoModelFactory):
    FACTORY_FOR = AssetCategory

    name = Sequence(lambda n: 'Asset category #%s' % n)
    type = AssetCategoryType.back_office

    @lazy_attribute
    def slug(self):
        return slugify(str(self.type) + self.name)

    @lazy_attribute
    def code(self):
        return ''.join(category_code_combinations.next())


class AssetSubCategoryFactory(AssetCategoryFactory):
    parent = SubFactory(AssetCategoryFactory)

    @lazy_attribute
    def slug(self):
        return slugify(str(self.type) + self.name + self.parent.name)


class AssetManufacturerFactory(DjangoModelFactory):
    FACTORY_FOR = AssetManufacturer

    name = Sequence(lambda n: 'Manufacturer #%s' % n)


class AssetModelFactory(DjangoModelFactory):
    FACTORY_FOR = AssetModel

    name = Sequence(lambda n: 'Model #%s' % n)
    type = AssetCategoryType.back_office
    manufacturer = SubFactory(AssetManufacturerFactory)
    category = SubFactory(AssetCategoryFactory)


class WarehouseFactory(DjangoModelFactory):
    FACTORY_FOR = Warehouse

    name = Sequence(lambda n: 'Warehouse #%s' % n)


class DeviceInfoFactory(DjangoModelFactory):
    FACTORY_FOR = DeviceInfo

    u_level = random.randint(0, 100)
    u_height = random.randint(0, 100)
    rack = Sequence(lambda n: 'Rack #%s' % n)


class BudgetInfoFactory(DjangoModelFactory):
    FACTORY_FOR = models_assets.BudgetInfo

    name = Sequence(lambda n: 'Budget info #{}'.format(n))


class OwnerFactory(DjangoModelFactory):
    FACTORY_FOR = models_assets.User

    name = Sequence(lambda n: 'Owner #{}'.format(n))


class AssetFactory(DjangoModelFactory):
    # XXX: DEPRECATED, use: DCAssetFactory, BOAssetFactory
    FACTORY_FOR = Asset

    type = AssetType.data_center
    model = SubFactory(AssetModelFactory)
    status = AssetStatus.new
    source = AssetSource.shipment
    warehouse = SubFactory(WarehouseFactory)
    device_info = SubFactory(DeviceInfoFactory)
    provider = Sequence(lambda n: 'Provider #%s' % n)
    support_period = 24
    support_type = 'standard'

    @lazy_attribute
    def sn(self):
        return generate_sn()


class BaseAssetFactory(DjangoModelFactory):
    FACTORY_FOR = Asset

    budget_info = SubFactory(BudgetInfoFactory)
    created = fuzzy.FuzzyNaiveDateTime(
        datetime.datetime(2008, 1, 1),
        force_microsecond=0,
    )
    delivery_date = fuzzy.FuzzyDate(datetime.date(2008, 1, 1))
    deprecation_end_date = fuzzy.FuzzyDate(datetime.date(2008, 1, 1))
    deprecation_rate = fuzzy.FuzzyInteger(0, 100)
    device_environment = SubFactory(DeviceEnvironmentFactory)
    invoice_date = fuzzy.FuzzyDate(datetime.date(2008, 1, 1))
    invoice_no = Sequence(lambda n: 'Invoice no #{}'.format(n))
    location = Sequence(lambda n: 'location #{}'.format(n))
    model = SubFactory(AssetModelFactory)
    niw = Sequence(lambda n: 'Inventory number #{}'.format(n))
    order_no = Sequence(lambda n: 'Order no #{}'.format(n))
    owner = SubFactory(UserFactory)
    price = fuzzy.FuzzyDecimal(0, 100)
    property_of = SubFactory(AssetOwnerFactory)
    provider = Sequence(lambda n: 'Provider #%s' % n)
    provider_order_date = fuzzy.FuzzyDate(datetime.date(2008, 1, 1))
    remarks = Sequence(lambda n: 'Remarks #{}'.format(n))
    request_date = fuzzy.FuzzyDate(datetime.date(2008, 1, 1))
    service = SubFactory(ServiceCatalogFactory)
    service_name = SubFactory(ServiceFactory)
    # sn exists below, as a lazy_attribute
    source = AssetSource.shipment
    status = AssetStatus.new
    task_url = Sequence(lambda n: 'http://www.url-{}.com/'.format(n))
    user = SubFactory(UserFactory)
    warehouse = SubFactory(WarehouseFactory)

    @lazy_attribute
    def barcode(self):
        return generate_barcode()

    @lazy_attribute
    def sn(self):
        return generate_sn()

    @factory.post_generation
    def device_environment(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing.
            return

        if extracted:
            self.device_environment = extracted
        else:
            if self.service:
                ci_relation = CIRelationFactory(parent=self.service)
                self.device_environment = ci_relation.child

    @factory.post_generation
    def supports(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing.
            return

        if extracted:
            # A list of supports were passed in, use them
            for support in extracted:
                self.supports.add(support)


class DCAssetFactory(BaseAssetFactory):
    type = AssetType.data_center
    device_info = SubFactory(DeviceInfoFactory)


class BOAssetFactory(BaseAssetFactory):
    type = AssetType.back_office
    hostname = Sequence(lambda n: 'XXXYY{:05}'.format(n))
    office_info = SubFactory(OfficeInfoFactory)
