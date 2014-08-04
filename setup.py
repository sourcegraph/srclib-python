from setuptools import setup

setup(
    name='grapher',
    version='0.0',
    url='http://sourcegraph.com/sourcegraph/srclib-python',
    packages=['grapher'],
    author='Beyang Liu',
    description='Generate the graph for a Python code rooted at a directory'
    'Help: graph.py -h',
    zip_safe=False,
    install_requires=['jedi'],
)
