import os
from setuptools import setup

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname), "r").read()

def get_version():
    g = {}
    exec(open(os.path.join("webpie", "Version.py"), "r").read(), g)
    return g["Version"]


setup(
    name = "webpie",
    version = get_version(),
    author = "Igor Mandrichenko",
    author_email = "igorvm@gmail.com",
    description = ("A set of useful tools built on top of standard Python threading module"),
    license = "BSD 3-clause",
    keywords = "web service, wsgi, web application",
    url = "https://webpie.github.io/",
    packages=['webpie', 'samples', 'webpie/webob'],
    long_description=read('README.rst'),
    install_requires=["pythreader"],
    zip_safe = False,
    classifiers=[
        "Operating System :: POSIX",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Server",
        "Programming Language :: Python",
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: BSD License",
        'Intended Audience :: Developers',
        'Natural Language :: English',
    ],
    entry_points = {
            "console_scripts": [
                "multiserver = bin.multiserver_ui:main",
            ]
        }
    
)