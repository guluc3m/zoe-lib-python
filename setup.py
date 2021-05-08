from setuptools import setup, find_packages

setup(
    name = 'zoe-lib-python',
    version = '0.1.1',
    description = 'Python library for Zoe assistant',
    url = 'https://github.com/guluc3m/zoe-lib-python',
    author = 'David Muñoz Díaz',
    author_email = 'david@gul.es',
    license = 'MIT',
    packages = find_packages(),
    keywords = 'guluc3m zoe gul-zoe world-domination',
    install_requires = [
        'kafka-python >= 1.3.5'
    ],
    test_suite = 'nose.collector',
    tests_require = [
        'nose'
    ]
)
