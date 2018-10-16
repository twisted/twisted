$PYTHON --version
$PYTHON -m pip --version
$PYTHON -m pip install -q --user --ignore-installed --upgrade virtualenv
$PYTHON -m virtualenv -p $PYTHON venv
venv/bin/pip install -U pip
venv/bin/python -m pip install tox
venv/bin/python -m pip freeze
venv/bin/python --version
