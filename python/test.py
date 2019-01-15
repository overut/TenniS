#!/usr/bin/env python

from tensorstack import Node
from tensorstack import Module
from tensorstack import bubble
from tensorstack import tensor
from tensorstack import device
from tensorstack import zoo


if __name__ == '__main__':
    a = bubble.param("a")
    b = bubble.param("b")
    data = bubble.data("data", tensor.from_any(3, dtype=float), device=device.CPU)\

    c = bubble.op("c", "sum", [a, b, data])

    module = Module()

    module.load(c)

    with open("test.module.txt", "w") as fo:
        Module.Save(stream=fo, module=module)