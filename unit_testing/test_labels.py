#!/usr/bin/env python
# -*- coding: utf-8
# pytest unit tests for spinalcordtoolbox.labels

import logging
from time import time

import numpy as np
import pytest

import spinalcordtoolbox.labels as sct_labels
from spinalcordtoolbox.image import Image, zeros_like
from spinalcordtoolbox.utils import sct_test_path
from spinalcordtoolbox.types import Coordinate
from test_image import fake_3dimage, fake_3dimage2

logger = logging.getLogger(__name__)

seg_img = Image(sct_test_path('t2', 't2_seg-manual.nii.gz'))
t2_img = Image(sct_test_path('t2', 't2.nii.gz'))


# TODO [AJ] investigate how to parametrize fixtures from test_image.py
# without redefining the function here
def fake_3dimage_sct2():
    """
    :return: an Image (3D) in RAS+ (aka SCT LPI) space
    shape = (1,2,3)
    """
    i = fake_3dimage2()
    img = Image(i.get_data(), hdr=i.header,
                orientation="RPI",
                dim=i.header.get_data_shape(),
                )
    return img


def fake_3dimage_sct():
    """
    :return: an Image (3D) in RAS+ (aka SCT LPI) space
    shape = (7,8,9)
    """
    i = fake_3dimage()
    img = Image(i.get_data(), hdr=i.header,
                orientation="LPI",
                dim=i.header.get_data_shape(),
                )
    return img


test_images = [fake_3dimage_sct(), fake_3dimage_sct2(), t2_img]


# AJ remove test if we keep add_faster + refactor caller
@pytest.mark.parametrize("test_image", test_images)
def test_add(test_image):
    a = test_image.copy()
    val = 4

    t1 = time()
    sct_added = sct_labels.add(a, val)
    t2 = time()
    np_added = sct_labels.add_faster(a, val)
    t3 = time()

    c = sct_added.data == np_added.data
    assert c.all()

    l1 = t2 - t1
    l2 = t3 - t2
    logger.debug(f"time to run sct_labels.add() -> {l1}")
    logger.debug(f"time to run np add -> {l2}")
    logger.debug(f"speed x improvement -> {l1/l2}")


@pytest.mark.parametrize("test_image", test_images)
def test_create_labels_empty(test_image):
    a = test_image.copy()
    expected = zeros_like(a)

    labels = [Coordinate(l) for l in [[0, 0, 0, 7], [0, 1, 2, 5]]]
    expected.data[0][0][0] = 7
    expected.data[0][1][2] = 5

    b = sct_labels.create_labels_empty(a, labels)

    diff = b.data == expected.data
    assert diff.all()


@pytest.mark.parametrize("test_image", test_images)
def test_create_labels(test_image):
    a = test_image.copy()
    labels = [Coordinate(l) for l in [[0, 1, 0, 99], [0, 1, 2, 5]]]

    b = sct_labels.create_labels(a, labels)

    assert b.data[0][1][0] == 99
    assert b.data[0][1][2] == 5


@pytest.mark.parametrize("test_seg", [seg_img])
def test_create_labels_along_segmentation(test_seg):
    a = test_seg.copy()
    labels = [(5, 1), (14, 2), (23, 3)]

    b = sct_labels.create_labels_along_segmentation(a, labels)

    assert b.orientation == a.orientation

    # TODO [AJ] implement test


@pytest.mark.skip(reason="To be implemented")
def test_cubic_to_point():
    raise NotImplementedError()


@pytest.mark.skip(reason="To be implemented")
def test_increment_z_inverse():
    raise NotImplementedError()


@pytest.mark.skip(reason="To be implemented")
def test_labelize_from_disks():
    raise NotImplementedError()


@pytest.mark.skip(reason="To be implemented")
def test_label_vertebrae():
    raise NotImplementedError()


@pytest.mark.skip(reason="To be implemented")
def test_compute_mean_squared_error():
    raise NotImplementedError()


@pytest.mark.parametrize("test_image", test_images)
def test_remove_missing_labels(test_image):
    src = test_image.copy()
    ref = test_image.copy()

    expected = test_image.copy()

    # change 2 labels in ref
    ref.data[0][0][0] = 99
    ref.data[0][1][2] = 99

    # manually set expected
    expected.data[0][0][0] = 0
    expected.data[0][1][2] = 0

    res = sct_labels.remove_missing_labels(src, ref)
    diff = res.data == expected.data

    assert diff.all()


@pytest.mark.skip(reason="To be implemented")
def test_get_coordinates_in_destination():
    raise NotImplementedError()


@pytest.mark.parametrize("test_image", test_images)
def test_labels_diff(test_image):
    src = test_image.copy()
    ref = test_image.copy()

    # change some labels
    ref.data[0][0][0] = 99
    ref.data[0][1][2] = 99

    src.data[0][1][1] = 99

    # check that changes appear in diff
    missing_from_ref, missing_from_src = sct_labels.labels_diff(src, ref)
    assert missing_from_ref[0] == Coordinate([0, 0, 0, src.data[0][0][0]])
    assert missing_from_ref[1] == Coordinate([0, 1, 2, src.data[0][1][2]])
    assert missing_from_src[0] == Coordinate([0, 1, 1, ref.data[0][1][1]])


@pytest.mark.parametrize("test_image", test_images)
def test_continuous_vertebral_levels(test_image):
    a = test_image.copy()
    b = sct_labels.continuous_vertebral_levels(a)

    # check that orientation is maintained
    assert b.orientation == a.orientation

    # TODO [AJ] implement test


@pytest.mark.parametrize("test_image", test_images)
def test_remove_labels_from_image(test_image):
    img = test_image.copy()
    expected = test_image.copy()
    labels = [Coordinate(l) for l in [[0, 0, 0, 7], [0, 1, 2, 5]]]

    res = sct_labels.remove_labels_from_image(img, labels)

    expected.data[0][0][0] = 0
    expected.data[0][1][2] = 0

    diff = res.data == expected.data
    assert diff.all()


@pytest.mark.parametrize("test_image", test_images)
def test_remove_other_labels_from_image(test_image):
    img = test_image.copy()
    expected = zeros_like(test_image)

    labels = [Coordinate(l) for l in [[0, 0, 0, 7], [0, 1, 2, 5]]]
    res = sct_labels.remove_other_labels_from_image(img, labels)

    expected.data[0][0][0] = img.data[0][0][0]
    expected.data[0][1][2] = img.data[0][1][2]

    diff = res.data == expected.data

    assert diff.all()
