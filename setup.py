from setuptools import setup

def read(file_name):
  with open(file_name) as f:
    return f.read()

setup(
  name='backblazeb2',
  version='0.1.3',
  description='Wrapper around the Backblaze B2 API',
  long_description=read('README.md'),
  url='https://github.com/picklelo/b2py',
  author='Nikhil Rao',
  author_email='nikhil@nikhilrao.me',
  classifiers=[
    'Development Status :: 3 - Alpha',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3'
  ],
  keywords='backblaze b2',
  packages=['b2py'],
  install_requires=['requests']
)
