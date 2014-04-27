from distutils.core import setup

#with open("README.rst", "r") as f:
#    readme = f.read()

setup(name='astsearch',
      version='0.1',
      description='Intelligently search Python source code',
#      long_description = readme,
      author='Thomas Kluyver',
      author_email='thomas@kluyver.me.uk',
      url='https://github.com/takluyver/astsearch',
      py_modules=['astsearch'],
      scripts=['astsearch'],
      classifiers=[
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3',
          'Topic :: Software Development :: Libraries :: Python Modules',
      ]
)