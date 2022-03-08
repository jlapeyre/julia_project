import setuptools

version = {}
with open("./julia_project/_version.py") as fp:
    exec(fp.read(), version)

setuptools.setup(
    name='julia_project',
    version=version['__version__'],
    description='Manage a Julia project inside a Python package',
    url='https://github.com/jlapeyre/julia_project.git',
    author='John Lapeyre',
    license = 'MIT',
    packages=setuptools.find_packages(),
    py_modules=["julia_project"],
    install_requires=['julia>=0.2',
                      'juliacall>=0.6.1',
                      'find_julia>=0.2.1',
                      'find_libpython',
                      'tomli'
                      ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
    extras_require={
        "test": [
            "pytest",
            "mock",
        ],
    },
)
