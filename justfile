setup:
    pip install -r requirements-dev.txt
    pre-commit install

build:
    python3 -m build

release: build
    python3 -m twine upload --skip-existing --repository pypi dist/*