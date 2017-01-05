from setuptools import setup, find_packages

setup(
    name = 'zoe-lib-python',
    version = '0.1.0',
    description = 'Python library for Zoe assistant',
    author = 'David Muñoz Díaz',
    author_email='david@gul.es',
    license = 'MIT',
    packages = find_packages(),
    keywords = 'guluc3m zoe gul-zoe world-domination',
    install_requires = [
        'pika >= 0.10.0'
    ]
)
