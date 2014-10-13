Change Log
----------


2.3.0
~~~~~
Released on October 2, 2014

* Added new fields service & environment to asset; both fields are synchronised with linked device from Ralph,
* Improved API Scrooge,
* Refactored history mechanism with many improvements (detect many-to-many & foreign-key changes),
* Redesigned navigation, added mode switch in assets view,
* Added new fields in search,
* Added confirmation on leaving unsaved form,,
* Redesigned report views & added new ones,
* Changes in Ralph device linking algorithm,
* Bugfixes.


2.2.0
~~~~~
Released on August 19, 2014

* Assets in license forms are autocompleted by device's hostname,
* Added *additional notes* field to supports search,
* Added popup with information about unsaved changes on the form,
* UI improvement in reports,


2.1.0
~~~~~
Released on August 1, 2014

* Added new reports feature,
* New change-hostname transition,
* Transitions send signals,
* Updated documentation,
* Updated api_ralph (assigned supports),
* Expired information in support lookup,
* Removed useless fields from BackOffice edit form,
* Bugfix - wrong order in exported CSV in Assets,


2.0.2-rc3
~~~~~~~~~
Released on July 9, 2014

* Added supports submodule
* Added generate hostname feature
* Added bulkedit in licences
* Minor bugfixes


2.0.2-rc2
~~~~~~~~~
Released on June 13, 2014

* Added asset id column to asset report


2.0.1-rc2
~~~~~~~~~

Released on June 6, 2014

* Bugfix - slots field is not shown when model category is blade


2.0.0-rc2
~~~~~~~~~

Released on June 3, 2014

* Bugfixes in API,
* Bugfixes in MANIFEST.in,
* Minor improvements in admin - Assets count column in model,
* Minor improvement in API - full model resource,
* Minor changes in model fields,
* Minor field changes in forms,
* Minor JS fixes,
* Unittests improvements - use ``factory_boy``


2.0.0-rc1
~~~~~~~~~

* Preparing to release a stable version
* New Licence module
* Improvement in asset fields
* Simple transitions
* Bug fixes


1.4.3
~~~~~

* Added warning logger with cores count from ralph and assets


1.4.2
~~~~~

* Changed AssetModel schema. Now height_of_device is a float field

* Added to AssetModel column named cores_count

* Changed in api_pricing conditions for getting assets


1.4.1
~~~~~

* Added Warehouse column to template bulk_edit file


1.4.0
~~~~~

* Changed limit in sn field when add/edit new device

* Visual grouping fields invoice_date and invoice_report when bulk edit assets

* Added deprecation rate field to bulk edit assets

* Added warehouse field to bulk edit assets


1.3.2
~~~~~

* cores_count from Asset returns 0 instead of None


1.3.1
~~~~~

* Add invoice date column to search table


1.3.0
~~~~~

* Fix bulk edit autocomplete

* Added 25 as default value of deprecation_rate

* Created a method in API to retrieve warehouses

* Added fields like venture_id, is_blade, cores_count, power_consumption, height_of_device and warehouse_id to get_assets API

* Added fields like power_consumption and height_of_device to AssetModel model

* Moved category from Asset model to AssetModel model

* Added cores_count method as property to Asset model


1.2.13
~~~~~~

* fixes of Discovered column. Also it shows now on csv reports.


1.2.12
~~~~~~

* Improved the csv exporting system


1.2.11
~~~~~~

* Basing deprecation on invoice date instead of delivery date


1.2.10
~~~~~~

* Pricing api uses only devices that existed on given date

* Pricing api can use forced deprecation


1.2.9
~~~~~

* Merged the u_height and size attributes

* Dynamically requiring 'slots' for blade categories

* Fixed unit tests


1.2.7
~~~~~
Released on October 03, 2013

* Added API for Ralph.

* Required form fields are now labelled accordingly.

* ``ralph_device_id`` get automatically cleaned when when Device linked to it gets deleted.

* Added partial and exact searches to assets.

* Unlinking assets from devices (and searching for unlinked assets) is now
  possible.

* Added searching assets by ``ralph_device_id``. Added option to create stock
  devices for unlinked assets.

* Fixed creating assets with ``add part`` button.

* Column ``department`` added to csv report in ``search DC assets``.



1.2.6
~~~~~

Released on August 08, 2013

* Added ajax autocomlation for Asset by barcode and/or sn.

* Disabled admin deletetion for Assets.

* Added link to the Pricing App.

* Added field: last modification, asset_id to csv file.



1.0.0
~~~~~

* initial release
