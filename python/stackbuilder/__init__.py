#!/usr/bin/env python

"""
:author Kier
"""

try:
    from . import holiday
except Exception, e:
    pass
try:
    from . import onnx
except Exception, e:
    pass
try:
    from . import torch
except Exception, e:
    pass
try:
    from . import vvvv
except Exception, e:
    pass
try:
    from . import caffe
except Exception, e:
    pass
try:
    from . import mxnet
except Exception, e:
    pass
# TODO: the follow framework is comming
# from . import tf

__version__ = "0.0.9"
