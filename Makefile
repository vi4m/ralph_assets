quicktest:
	DJANGO_SETTINGS_PROFILE=test-assets ralph test ralph_assets
	
install:
	pip install -e .

test-unittests:
	DJANGO_SETTINGS_PROFILE=test-assets coverage run --source=ralph_assets --omit='*migrations*,*tests*,*__init__*' '$(VIRTUAL_ENV)/bin/ralph' test ralph_assets

test-doc:
	cd ./doc && make html

coverage:
	make test-with-coveralls
	coverage html
	coverage report

flake:
	flake8 --exclude="migrations" --statistics src/ralph_assets

runserver:
	ralph runserver

test-with-coveralls: test-doc test-unittests
