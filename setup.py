import setuptools

setuptools.setup(
    name='julia_project',
    version='0.0.2',
    description='Manage a Julia project inside a Python package',
    url='https://github.com/jlapeyre/julia_project.git',
    author='John Lapeyre',
    packages=setuptools.find_packages(),
    py_modules=["julia_project", ],
    install_requires=['julia', ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
)
