from setuptools import setup, find_packages

setup(
    name='juliaproject',
    version='0.0.1',
    description='Manage a Julia project inside a Python package',
    # url='https://github.com/mypackage.git',
    author='John Lapeyre',
    # author_email='author@gmail.com',
    packages=find_packages(),
    py_modules=["juliaproject", ],
    install_requires=['julia', ] # numpy >= 1.11.1', 'matplotlib >= 1.5.1'],
)
