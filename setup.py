from setuptools import setup

setup(
    name='callaborate',
    version='0.0.1',
    description='',
    author='',
    author_email='',
    packages=['callaborate'],
    install_requires=[
        'Flask==0.10.1',
        'Flask-Cors==1.8.0',
        'redis==2.8.0',
        'requests==2.13.0',
        'google-api-python-client==1.6.2'
    ],
    entry_points={"console_scripts": ["callaborate=callaborate:main"]}
)
