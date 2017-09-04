#######################################
### Dev targets
#######################################
dev-dep:
	sudo apt-get install python3-virtualenv python3-pil.imagetk python3-tk libspeex-dev swig libpulse-dev libspeexdsp-dev portaudio19-dev

dev-pyenv:
	virtualenv -p /usr/bin/python3 env
	env/bin/pip3 install -r requirements.txt --upgrade --force-reinstall
	env/bin/python setup.py develop

#######################################
### Documentation
#######################################
doc-update-refs:
	rm -rf doc/source/refs/
	sphinx-apidoc -M -f -e -o doc/source/refs/ tuxeatpi/

doc-generate:
	cd doc && make html
	touch doc/build/html/.nojekyll


#######################################
### Test targets
#######################################

test-run: test-syntax test-pytest

test-syntax:
	env/bin/pycodestyle --max-line-length=100 tuxeatpi_nlu_nuance
	env/bin/pylint --rcfile=.pylintrc -r no tuxeatpi_nlu_nuance

test-pytest:
	rm -rf .coverage nosetest.xml nosetests.html htmlcov
	env/bin/pytest --html=pytest/report.html --self-contained-html --junit-xml=pytest/junit.xml --cov=tuxeatpi_nlu_nuance/ --cov-report=term --cov-report=html:pytest/coverage/html --cov-report=xml:pytest/coverage/coverage.xml tests 
	coverage combine || true
	coverage report --include='*/tuxeatpi_nlu_nuance/*'
	# CODECLIMATE_REPO_TOKEN=${CODECLIMATE_REPO_TOKEN} codeclimate-test-reporter
