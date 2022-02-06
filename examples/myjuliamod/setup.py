from setuptools import setup, find_packages

setup(
    name='myjuliamod',
    version='0.0.1',
    description='myjuliamod example',
    author='John Lapeyre',
    packages=find_packages(),
    install_requires=['julia>=0.2',
                      'julia_project>=0.0.23'
                      ],
    include_package_data=True
)
