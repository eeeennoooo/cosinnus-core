.PHONY: docs test

docs:
	rm -f docs/ref/*
	sphinx-apidoc -o docs/ref -d 1 -f -T cosinnus
	rm -f docs/ref/cosinnus.migrations.rst
	grep -v "    cosinnus.migrations" docs/ref/cosinnus.rst > docs/ref/cosinnus.rst.tmp
	mv docs/ref/cosinnus.rst.tmp docs/ref/cosinnus.rst
	make -C docs clean html

test:
	django-admin.py test --pythonpath=./ --settings=tests.settings.base -v 2
	django-admin.py test --pythonpath=./ --settings=tests.settings.base_swappable -v 2
