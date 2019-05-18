#!/usr/bin/env python

import stackbuilder as sb
import tensorstack as ts

import os
import sys
sys.path.append(
    os.path.join(os.path.abspath(os.path.dirname(__file__)), "."))

import maskrcnn

from stackbuilder.torch.module import convert_module as ts_convert_module

from maskrcnn_benchmark.modeling.detector.generalized_rcnn import GeneralizedRCNN
from maskrcnn_benchmark.modeling.backbone.resnet import ResNet
from maskrcnn_benchmark.modeling.backbone.resnet import StemWithFixedBatchNorm
from maskrcnn_benchmark.layers.misc import Conv2d
from maskrcnn_benchmark.layers.batch_norm import FrozenBatchNorm2d
from maskrcnn_benchmark.modeling.backbone.resnet import BottleneckWithFixedBatchNorm
from maskrcnn_benchmark.modeling.backbone.fpn import FPN
from maskrcnn_benchmark.modeling.backbone.fpn import LastLevelMaxPool
from maskrcnn_benchmark.modeling.rpn.rpn import RPNModule
from maskrcnn_benchmark.modeling.rpn.rpn import RPNHead
from maskrcnn_benchmark.modeling.rpn.anchor_generator import AnchorGenerator
from maskrcnn_benchmark.modeling.rpn.inference import RPNPostProcessor

try:
    from maskrcnn_benchmark.modeling.backbone.resnet import BottleneckWithFixedBatchNormDeformable
except:
    BottleneckWithFixedBatchNormDeformable = None
try:
    from dcn_v2 import DCN
except:
    DCN = None

import torch

import numpy


def convert_grcnn(m, x, scope=None):
    return None


def convert_resnet(m, x, scope=None):
    if isinstance(x, (tuple, list)):
        x = x[0]
    if scope is None:
        scope = ''
    assert isinstance(x, ts.Node)
    assert isinstance(m, ResNet)

    stem = m.stem
    stages = m.stages

    x = sb.torch.module.convert_module(stem, x, scope=scope + "/stem")

    outputs = []

    for stage_name in stages:
        x = sb.torch.module.convert_module(getattr(m, stage_name), x, scope=scope + "/" + stage_name)
        if m.return_features[stage_name]:
            outputs.append(x)

    return outputs


def convert_stem(m, x, scope=None):
    if isinstance(x, (tuple, list)):
        x = x[0]
    if scope is None:
        scope = ''
    assert isinstance(x, ts.Node)
    assert isinstance(m, StemWithFixedBatchNorm)

    x = sb.torch.module.convert_module(m.conv1, x, scope=scope + "/conv1")
    x = sb.torch.module.convert_module(m.bn1, x, scope=scope + "/bn1")
    x = ts.zoo.relu(name=scope + "/relu1", x=x)
    x = ts.frontend.onnx.pooling2d(name=scope + "pool1", x=x,
                                   ksize=(1, 1, 3, 3),
                                   stride=(1, 1, 2, 2),
                                   padding=[(0, 0), (0, 0), (1, 1), (1, 1)],
                                   auto_pad="NOTSET")

    return x


def convert_conv2d(m, x, scope=None):
    if isinstance(x, (tuple, list)):
        x = x[0]
    if scope is None:
        scope = ''
    assert isinstance(x, ts.Node)
    assert isinstance(m, Conv2d)

    return sb.torch.module.convert_conv2d(m, x, scope=scope)


def convert_frozen_bn(m, x, scope=None):
    if isinstance(x, (tuple, list)):
        x = x[0]
    if scope is None:
        scope = ''
    assert isinstance(x, ts.Node)
    assert isinstance(m, FrozenBatchNorm2d)

    print("--# -=[ Converting {} layer: {} ]=-".format(m.__class__.__name__, scope))
    print("--##    REPR: {}".format(m))
    """
    scale = self.weight * self.running_var.rsqrt()
    bias = self.bias - self.running_mean * scale
    scale = scale.reshape(1, -1, 1, 1)
    bias = bias.reshape(1, -1, 1, 1)
    return x * scale + bias
    """

    weight = numpy.asarray(m.weight.cpu(), dtype=numpy.float32)
    bias = numpy.asarray(m.bias.cpu(), dtype=numpy.float32)
    running_mean = numpy.asarray(m.running_mean.cpu(), dtype=numpy.float32)
    running_var = numpy.asarray(m.running_var.cpu(), dtype=numpy.float32)

    assert len(weight.shape) == 1
    assert len(bias.shape) == 1
    assert len(running_mean.shape) == 1
    assert len(running_var.shape) == 1

    scale = weight / numpy.sqrt(running_var)
    bias = bias - running_mean * scale

    x = ts.zoo.batch_scale(name=scope, x=x, scale=scale, bias=bias, dim=1)

    return x


def convert_bottleneck(m, x, scope=None):
    if isinstance(x, (tuple, list)):
        x = x[0]
    if scope is None:
        scope = ''
    assert isinstance(x, ts.Node)
    assert isinstance(m, BottleneckWithFixedBatchNorm)

    print("--# -=[ Converting {} layer: {} ]=-".format(m.__class__.__name__, scope))
    # print("--##    REPR: {}".format(m))

    residual = x

    out = sb.torch.module.convert_module(m.conv1, x, scope=scope + "/conv1")
    out = sb.torch.module.convert_module(m.bn1, out, scope=scope + "/bn1")
    out = ts.zoo.relu(name=scope + "/relu1", x=out)

    out = sb.torch.module.convert_module(m.conv2, out, scope=scope + "/conv2")
    out = sb.torch.module.convert_module(m.bn2, out, scope=scope + "/bn2")
    out = ts.zoo.relu(name=scope + "/relu2", x=out)

    out0 = sb.torch.module.convert_module(m.conv3, out, scope=scope + "/conv3")
    out = sb.torch.module.convert_module(m.bn3, out0, scope=scope + "/bn3")

    if m.downsample is not None:
        residual = sb.torch.module.convert_module(m.downsample, x, scope=scope + "/downsample")

    out = ts.zoo.add(name=scope + "/add", lhs=out, rhs=residual)
    out = ts.zoo.relu(name=scope + "/relu3", x=out)

    return out


def convert_bottleneck_deformable(m, x, scope=None):
    if isinstance(x, (tuple, list)):
        x = x[0]
    if scope is None:
        scope = ''
    assert isinstance(x, ts.Node)
    assert isinstance(m, BottleneckWithFixedBatchNormDeformable)

    print("--# -=[ Converting {} layer: {} ]=-".format(m.__class__.__name__, scope))
    # print("--##    REPR: {}".format(m))

    residual = x

    out = sb.torch.module.convert_module(m.conv1, x, scope=scope + "/conv1")
    out = sb.torch.module.convert_module(m.bn1, out, scope=scope + "/bn1")
    out = ts.zoo.relu(name=scope + "/relu1", x=out)

    out = sb.torch.module.convert_module(m.deformconv2, out, scope=scope + "/deformconv2")
    out = sb.torch.module.convert_module(m.bn2, out, scope=scope + "/bn2")
    out = ts.zoo.relu(name=scope + "/relu2", x=out)

    out0 = sb.torch.module.convert_module(m.conv3, out, scope=scope + "/conv3")
    out = sb.torch.module.convert_module(m.bn3, out0, scope=scope + "/bn3")

    if m.downsample is not None:
        residual = sb.torch.module.convert_module(m.downsample, x, scope=scope + "/downsample")

    out = ts.zoo.add(name=scope + "/add", lhs=out, rhs=residual)
    out = ts.zoo.relu(name=scope + "/relu3", x=out)

    return out


def convert_dcn(m, x, scope=None):
    if isinstance(x, (tuple, list)):
        x = x[0]
    if scope is None:
        scope = ''
    assert isinstance(x, ts.Node)
    assert isinstance(m, DCN)

    print("--# -=[ Converting {} layer: {} ]=-".format(m.__class__.__name__, scope))
    print("--##    REPR: {}".format(m))

    out = sb.torch.module.convert_module(m.conv_offset_mask, x, scope=scope + "/conv_offset_mask")

    o1, o2, mask = ts.zoo.chunk(name=scope + "/chunk", x=out, chunks=3, dim=1)
    offset = ts.zoo.concat(name=scope + "/concat", inputs=(o1, o2), dim=1)
    mask = ts.zoo.sigmoid(name=scope + "/sigmoid", x=mask)

    in_channels = m.in_channels
    out_channels = m.out_channels
    kernel_size = m.kernel_size
    stride = m.stride
    padding = m.padding
    dilation = m.dilation
    deformable_groups = m.deformable_groups

    weight = numpy.asarray(m.weight.cpu(), dtype=numpy.float32)
    bias = numpy.asarray(m.bias.cpu(), dtype=numpy.float32)

    output = ts.frontend.torch.dcn_v2_forward(name=scope + "/dcn", x=x, w=weight, b=bias, offset=offset, mask=mask,
                                              deformable_groups=deformable_groups, format=ts.zoo.Name.NCHW,
                                              padding=[(0, 0), (0, 0), (padding[0], padding[0]), (padding[1], padding[1])],
                                              stride=[1, 1, stride[0], stride[1]],
                                              dilation=[1, 1, dilation[0], dilation[1]])
    return output


def convert_attr_module(self, attr, scope, *args):
    return sb.torch.module.convert_module(getattr(self, attr), tuple(args), scope=scope + "/" + attr)


def interpolate(name, x, scale_factor):
    shape = ts.zoo.shape(name=name + "_shape", x=x)
    rhs = numpy.asarray([1, 1, scale_factor, scale_factor], dtype=numpy.int32)
    size = ts.zoo.mul(name=name + "_scale", lhs=shape, rhs=rhs)
    return ts.zoo.resize2d(name=name, x=x, size=size, type=ts.zoo.Type.resize2d_type.nearest)


def convert_fpn(m, x, scope=None):
    assert isinstance(x, (tuple, list))
    if scope is None:
        scope = ''
    assert isinstance(m, FPN)

    print("--# -=[ Converting {} layer: {} ]=-".format(m.__class__.__name__, scope))
    # print("--##    REPR: {}".format(m))

    self = m

    last_inner = convert_attr_module(self, self.inner_blocks[-1], scope, x[-1])
    results = []
    results.append(convert_attr_module(self, self.layer_blocks[-1], scope, last_inner))
    for feature, inner_block, layer_block in zip(
            x[:-1][::-1], self.inner_blocks[:-1][::-1], self.layer_blocks[:-1][::-1]
    ):
        inner_top_down = interpolate(scope + "/" + last_inner.name + "/interpolate", x=last_inner, scale_factor=2)
        inner_lateral = convert_attr_module(self, inner_block, scope, feature)
        # TODO use size instead of scale to make it robust to different sizes
        # inner_top_down = F.upsample(last_inner, size=inner_lateral.shape[-2:],
        # mode='bilinear', align_corners=False)
        last_inner = ts.zoo.add(scope + "/add_" + inner_block + "_" + last_inner.name, inner_lateral, inner_top_down)
        results.insert(0, convert_attr_module(self, layer_block, scope, last_inner))

    if self.top_blocks is not None:
        last_results = sb.torch.module.convert_module(m.top_blocks, results[-1], scope=scope + "/top_blocks")
        results.extend(last_results)

    return results


def convert_last_level_max_pool(m, x, scope=None):
    if isinstance(x, (tuple, list)):
        x = x[0]
    if scope is None:
        scope = ''
    assert isinstance(x, ts.Node)
    assert isinstance(m, LastLevelMaxPool)

    x = ts.frontend.onnx.pooling2d(name=scope, x=x,
                                   ksize=(1, 1, 1, 1),
                                   stride=(1, 1, 2, 2),
                                   padding=[(0, 0), (0, 0), (0, 0), (0, 0)],
                                   auto_pad="NOTSET")

    return [x,]


def convert_rpn(m, x, scope=None):
    """
    :param m:
    :param x: Node, List[Node]
    :param scope:
    :return: Node
    images, features
    """
    assert isinstance(x, (tuple, list))
    assert len(x) == 2 or len(x) == 3

    images = x[0]
    features = x[1]

    assert isinstance(features, (tuple, list))
    for feat in features:
        assert isinstance(feat, ts.Node)

    assert isinstance(images, ts.Node)
    assert isinstance(m, RPNModule)

    objectness, rpn_box_regression = convert_rpn_head(m.head, features, scope=scope + "/head")

    # packed_features = ts.menu.pack(name=scope + "/features", inputs=features)

    anchors = convert_anchor_generator(m.anchor_generator, (images, features), scope=scope + "/anchor_generator")

    boxes = convert_rpn_post_processor(m.box_selector_test, (anchors, objectness, rpn_box_regression), scope=scope + "/box_selector_test")

    # not support RPN only
    assert not m.cfg.MODEL.RPN_ONLY

    return boxes


def convert_rpn_head(m, x, scope=None):
    """

    :param m:
    :param x: List[Node]
    :param scope:
    :return:
    """
    assert isinstance(x, (tuple, list))
    for item in x:
        assert isinstance(item, ts.Node)

    assert isinstance(m, RPNHead)

    logits = []
    bbox_reg = []

    index = 0

    for feature in x:
        t = ts_convert_module(m.conv, feature, scope=scope + "/conv/" + str(index))
        t = ts.zoo.relu(scope + "/relu/" + str(index), t)
        logits.append(ts_convert_module(m.cls_logits, t, scope=scope + "/cls_logits/" + str(index)))
        bbox_reg.append(ts_convert_module(m.bbox_pred, t, scope=scope + "/bbox_pred/" + str(index)))

        index += 1

    return logits, bbox_reg


def convert_anchor_generator(m, x, scope=None):
    """
    :param m:
    :param x: Node, list[Node]/Node
    :param scope:
    :return: Packed tensor anchor
    """
    assert isinstance(x, (tuple, list))
    assert len(x) == 2

    images = x[0]
    features = x[1]

    if isinstance(features, (tuple, list)):
        for feat in features:
            assert isinstance(feat, ts.Node)
        features = ts.menu.pack(name=scope + "/features", inputs=features)
    elif isinstance(features, ts.Node):
        pass
    else:
        raise NotImplementedError("type(features) = {}".format(type(features)))

    assert isinstance(images, ts.Node)
    assert isinstance(m, AnchorGenerator)

    strides = m.strides
    cell_anchors = [numpy.asarray(base_anchors.cpu()) for base_anchors in m.cell_anchors]

    anchors = maskrcnn.anchor_generator(
        name=scope,
        images=images, features=features,
        strides=strides,
        cell_anchors=cell_anchors
    )

    return anchors


def convert_rpn_post_processor(m, x, scope=None):
    """
    :param m:
    :param x: PackedNode, list[Node]/Node, list[Node]/Node
    :param scope:
    :return: Node
    anchors, objectness, rpn_box_regression
    """
    assert isinstance(x, (tuple, list))
    assert len(x) == 3

    anchors = x[0]
    objectness = x[1]
    rpn_box_regression = x[2]

    if isinstance(objectness, (tuple, list)):
        for feat in objectness:
            assert isinstance(feat, ts.Node)
        objectness = ts.menu.pack(name=scope + "/objectness", inputs=objectness)
    elif isinstance(objectness, ts.Node):
        pass
    else:
        raise NotImplementedError("type(objectness) = {}".format(type(objectness)))

    if isinstance(rpn_box_regression, (tuple, list)):
        for feat in rpn_box_regression:
            assert isinstance(feat, ts.Node)
        rpn_box_regression = ts.menu.pack(name=scope + "/rpn_box_regression", inputs=rpn_box_regression)
    elif isinstance(rpn_box_regression, ts.Node):
        pass
    else:
        raise NotImplementedError("type(rpn_box_regression) = {}".format(type(rpn_box_regression)))

    assert isinstance(anchors, ts.Node)
    assert isinstance(m, RPNPostProcessor)

    return maskrcnn.box_selector(name=scope,
                                 anchors=anchors, objectness=objectness, rpn_box_regression=rpn_box_regression,
                                 pre_nms_top_n=m.pre_nms_top_n,
                                 min_size=m.min_size,
                                 nms_thresh=m.nms_thresh,
                                 post_nms_top_n=m.post_nms_top_n,
                                 fpn_post_nms_top_n=m.fpn_post_nms_top_n,
                                 weights=m.box_coder.weights,
                                 bbox_xform_clip=m.box_coder.bbox_xform_clip)


sb.torch.module.register_module_converter(GeneralizedRCNN, convert_grcnn)
sb.torch.module.register_module_converter(ResNet, convert_resnet)
sb.torch.module.register_module_converter(StemWithFixedBatchNorm, convert_stem)
sb.torch.module.register_module_converter(Conv2d, convert_conv2d)
sb.torch.module.register_module_converter(FrozenBatchNorm2d, convert_frozen_bn)
sb.torch.module.register_module_converter(BottleneckWithFixedBatchNorm, convert_bottleneck)
sb.torch.module.register_module_converter(FPN, convert_fpn)
sb.torch.module.register_module_converter(LastLevelMaxPool, convert_last_level_max_pool)

sb.torch.module.register_module_converter(BottleneckWithFixedBatchNormDeformable, convert_bottleneck_deformable)
sb.torch.module.register_module_converter(DCN, convert_dcn)

sb.torch.module.register_module_converter(RPNModule, convert_rpn)
sb.torch.module.register_module_converter(RPNHead, convert_rpn_head)
sb.torch.module.register_module_converter(AnchorGenerator, convert_anchor_generator)
sb.torch.module.register_module_converter(RPNPostProcessor, convert_rpn_post_processor)


def convert_module(m, x=None):
    """
    convert module to graph node
    :param m:
    :param x:
    :return:
    """
    m.eval()
    with torch.no_grad():
        return sb.torch.module.convert_module(m, x)