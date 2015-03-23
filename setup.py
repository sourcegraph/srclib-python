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
    # MaikuMori(23/03/2015)
    # Don't declare dependency here because pip will just pull jedi from pip repository instead of
    # git+https://github.com/beyang/jedi.git@c4a51cba12bc4849e19c4aa25aeb30d66e5fd238
    # install_requires=['jedi'],
)
