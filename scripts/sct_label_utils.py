#!/usr/bin/env python
#########################################################################################
#
# All sort of utilities for labels.
#
# ---------------------------------------------------------------------------------------
# Copyright (c) 2015 Polytechnique Montreal <www.neuro.polymtl.ca>
# Author: Benjamin De Leener, Julien Cohen-Adad
# Modified: 2015-02-11
#
# About the license: see the file LICENSE.TXT
#########################################################################################

# TODO: for vert-disc: make it faster! currently the module display-voxel is very long (esp. when ran on PAM50). We can find an alternative approach by sweeping through centerline voxels.
# TODO: label_disc: for top vertebrae, make label at the center of the cord (currently it's at the tip)
# TODO: check if use specified several processes.
# TODO: currently it seems like cross_radius is given in pixel instead of mm

from __future__ import division, absolute_import

import os
import sys
import argparse
from typing import Sequence

import numpy as np

from spinalcordtoolbox.image import Image, zeros_like
from spinalcordtoolbox.types import Coordinate
from spinalcordtoolbox.reports.qc import generate_qc
import spinalcordtoolbox.labels as sct_labels

# TODO: Properly test when first PR (that includes list_type) gets merged
from spinalcordtoolbox.utils import Metavar, SmartFormatter, ActionCreateFolder, list_type
import sct_utils as sct



def get_parser():
    # initialize default param
    param_default = Param()
    # Initialize the parser
    parser = argparse.ArgumentParser(
        description="Utility functions for label images.",
        formatter_class=SmartFormatter,
        add_help=None,
        prog=os.path.basename(__file__).strip(".py")
    )

    req_group = parser.add_argument_group("\nREQUIRED")
    req_group.add_argument(
        '-i',
        metavar=Metavar.file,
        required=True,
        help="Input image (Required) Example: t2_labels.nii.gz"
    )

    io_group = parser.add_argument_group("\nOPTIONAL I/O")

    io_group.add_argument(
        '-o',
        metavar=Metavar.file,
        help=("Output image. Example: t2_labels.nii.gz"
              "Note: If no output image is provided, input image will be overwritten!")
    )

    io_group.add_argument(
        '-ilabel',
        metavar=Metavar.file,
        help="File that contain labels that you want to correct. It is possible to add new points with this option. "
             "Use with -create-viewer. Example: t2_labels_auto.nii.gz"
    )

    functions = parser.add_argument_group("\nLABEL FUNCTIONS")
    func_group = functions.add_mutually_exclusive_group(required=True)

    func_group.add_argument(
        '-add',
        metavar=Metavar.int,
        type=int,
        help="Add value to all labels. Value can be negative."
    )

    func_group.add_argument(
        '-create',
        metavar=Metavar.list,
        type=list_type(':', Coordinate),
        help="Create labels in a new image. List labels as: x1,y1,z1,value1:x2,y2,z2,value2. "
             "Example: 12,34,32,1:12,35,33,2"
    )

    func_group.add_argument(
        '-create-add',
        metavar=Metavar.list,
        type=list_type(':', Coordinate),
        help="Same as '-create', but add labels to the input image instead of creating a new image. "
             "Example: 12,34,32,1:12,35,33,2"
    )

    func_group.add_argument(
        '-create-seg',
        metavar=Metavar.list,
        type=list_type(':', str),
        help="R|Create labels along cord segmentation (or centerline) defined by '-i'. First value is 'z', second is "
             "the value of the label. Separate labels with ':'. Example: 5,1:14,2:23,3. \n"
             "To select the mid-point in the superior-inferior direction, set z to '-1'. For example if you know that "
             "C2-C3 disc is centered in the S-I direction, then enter: -1,3"
    )
    func_group.add_argument(
        '-create-viewer',
        metavar=Metavar.list,
        type=list_type(',', int),
        help="Manually label from a GUI a list of labels IDs, separated with ','. Example: 2,3,4,5"
    )

    func_group.add_argument(
        '-cubic-to-point',
        action="store_true",
        help="Compute the center-of-mass for each label value."
    )

    func_group.add_argument(
        '-display',
        action="store_true",
        help="Display all labels (i.e. non-zero values)."
    )
    func_group.add_argument(
        '-increment',
        action="store_true",
        help="Takes all non-zero values, sort them along the inverse z direction, and attributes the values "
             "1, 2, 3, etc."
    )
    func_group.add_argument(
        '-vert-body',
        metavar=Metavar.list,
        type=list_type(',', int),
        help="R|From vertebral labeling, create points that are centered at the mid-vertebral levels. Separate "
             "desired levels with ','. Example: 3,8\n"
             "To get all levels, enter 0."
    )

    func_group.add_argument(
        '-vert-continuous',
        action="store_true",
        help="Convert discrete vertebral labeling to continuous vertebral labeling.",
    )
    func_group.add_argument(
        '-MSE',
        metavar=Metavar.file,
        help="Compute Mean Square Error between labels from input and reference image. Specify reference image here."
    )
    func_group.add_argument(
        '-remove-reference',
        metavar=Metavar.file,
        help="Remove labels from input image (-i) that are not in reference image (specified here)."
    )
    func_group.add_argument(
        '-remove-sym',
        metavar=Metavar.file,
        help="Remove labels from input image (-i) and reference image (specified here) that don't match. You must "
             "provide two output names separated by ','."
    )
    func_group.add_argument(
        '-remove',
        metavar=Metavar.list,
        type=list_type(',', int),
        help="Remove labels of specific value (specified here) from reference image."
    )
    func_group.add_argument(
        '-keep',
        metavar=Metavar.list,
        type=list_type(',', int),
        help="Keep labels of specific value (specified here) from reference image."
    )

    optional = parser.add_argument_group("\nOPTIONAL ARGUMENTS")
    optional.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message and exit."
    )

    optional.add_argument(
        '-msg',
        metavar=Metavar.str,
        help="Display a message to explain the labeling task. Use with -create-viewer"
    )

    optional.add_argument(
        '-v',
        choices=['0', '1', '2'],
        default='1',
        help="Verbose. 0: nothing. 1: basic. 2: extended."
    )

    optional.add_argument(
        '-qc',
        metavar=Metavar.folder,
        action=ActionCreateFolder,
        help="The path where the quality control generated content will be saved."
    )

    optional.add_argument(
        '-qc-dataset',
        metavar=Metavar.str,
        help="If provided, this string will be mentioned in the QC report as the dataset the process was run on."
    )

    optional.add_argument(
        '-qc-subject',
        metavar=Metavar.str,
        help="If provided, this string will be mentioned in the QC report as the subject the process was run on."
    )

    return parser


# MAIN
# ==========================================================================================
def main(args=None):
    parser = get_parser()
    if args:
        arguments = parser.parse_args(args)
    else:
        arguments = parser.parse_args(args=None if sys.argv[1:] else ['--help'])

    input_filename = arguments.i
    img = Image(input_filename)

    # input_fname_output = None
    # input_fname_ref = None
    # input_cross_radius = 5
    # input_dilate = False
    # input_coordinates = None
    # vertebral_levels = None
    # value = None

    if arguments.add is not None:
        out = sct_labels.add(img, arguments.add)
    elif arguments.create is not None:
        out = sct_labels.create_labels_empty(img, arguments.create)
    elif arguments.create_add is not None:
        out = sct_labels.create_labels(img, arguments.create_add)
    elif arguments.create_seg is not None:
        out = sct_labels.create_labels_along_segmentation(img, arguments.create_seg)
    elif arguments.cubic_to_point:
        out = sct_labels.cubic_to_point(img)
    elif arguments.display:
        display_voxel(img, arguments.v)
    elif arguments.increment:
        out = sct_labels.increment_z_inverse(img)
    elif arguments.vert_body is not None:
        out = sct_labels.label_vertebrae(img, arguments.vert_body)
    elif arguments.vert_continuous:
        process_type = 'vert-continuous'
    elif arguments.MSE is not None:
        process_type = 'MSE'
        input_fname_ref = arguments.r
    elif arguments.remove_reference is not None:
        process_type = 'remove-reference'
        input_fname_ref = arguments.remove_reference
    elif arguments.remove_symm is not None:
        process_type = 'remove-symm'
        input_fname_ref = arguments.r
    elif arguments.create_viewer is not None:
        process_type = 'create-viewer'
        value = arguments.create_viewer
    elif arguments.remove is not None:
        process_type = 'remove'
        value = arguments.remove
    elif arguments.keep is not None:
        process_type = 'keep'
        value = arguments.keep
    else:
        # no process chosen
        sct.printv('ERROR: No process was chosen.', 1, 'error')
    if arguments.msg is not None:
        msg = arguments.msg + "\n"
    else:
        msg = ""
    if arguments.o is not None:
        input_fname_output = arguments.o
    if arguments.ilabel is not None:
        input_fname_previous = arguments.ilabel
    else:
        input_fname_previous = None
    verbose = int(arguments.v)
    sct.init_sct(log_level=verbose, update=True)  # Update log level


    # return based on process type
    if process_type == 'display-voxel':
        return processor.useful_notation

    path_qc = arguments.qc
    qc_dataset = arguments.qc_dataset
    qc_subject = arguments.qc_subject
    if path_qc is not None:
        generate_qc(fname_in1=input_filename, fname_seg=input_fname_output[0], args=args,
                    path_qc=os.path.abspath(path_qc), dataset=qc_dataset, subject=qc_subject, process='sct_label_utils')


def display_voxel(img: Image, verbose: int):
    """
    Display all the labels that are contained in the input image.
    :param img: source image
    :param verbose: verbosity level
    """

    coordinates_input = img.getNonZeroCoordinates(sorting='value')
    useful_notation = ''

    for coord in coordinates_input:
        sct.printv('Position=(' + str(coord.x) + ',' + str(coord.y) + ',' + str(coord.z) + ') -- Value= ' + str(coord.value), verbose=verbose)
        if useful_notation:
            useful_notation = useful_notation + ':'
        useful_notation += str(coord)

    sct.printv('All labels (useful syntax):', verbose=verbose)
    sct.printv(useful_notation, verbose=verbose)

# TODO [AJ] -> just print warnings or log or raise?
def check_distance_between_labels(img: Image, max_dist_mm: float):
    """
    Calculate the distances between each label in the input image.
    If a distance is larger than max_dist_mm, a warning message is displayed.
    :param img: input image
    :param max_dist: maximum distance (in mm) allowed between labels
    """
    coordinates_input = img.getNonZeroCoordinates()

    # for all points with non-zeros neighbors, force the neighbors to 0
    for i in range(0, len(coordinates_input) - 1):
        dist = np.sqrt((coordinates_input[i].x - coordinates_input[i + 1].x)**2 + (coordinates_input[i].y - coordinates_input[i + 1].y)**2 + (coordinates_input[i].z - coordinates_input[i + 1].z)**2)

        if dist < max_dist_mm:
            sct.printv('Warning: the distance between label ' + str(i) + '[' + str(coordinates_input[i].x) + ',' + str(coordinates_input[i].y) + ',' + str(
                coordinates_input[i].z) + ']=' + str(coordinates_input[i].value) + ' and label ' + str(i + 1) + '[' + str(
                coordinates_input[i + 1].x) + ',' + str(coordinates_input[i + 1].y) + ',' + str(coordinates_input[i + 1].z) + ']=' + str(
                coordinates_input[i + 1].value) + ' is larger than ' + str(max_dist_mm) + '. Distance=' + str(dist))


def launch_sagittal_viewer(labels: Sequence[Coordinate], previous_points=None):
    from spinalcordtoolbox.gui import base
    from spinalcordtoolbox.gui.sagittal import launch_sagittal_dialog

    params = base.AnatomicalParams()
    params.vertebraes = labels
    params.input_file_name = img.absolutepath
    params.output_file_name = self.fname_output
    params.subtitle = self.msg
    if previous_points is not None:
        params.message_warn = 'Please select the label you want to add \nor correct in the list below before clicking \non the image'
    output = zeros_like(img)
    output.absolutepath = self.fname_output
    launch_sagittal_dialog(img, output, params, previous_points)

    return output


if __name__ == "__main__":
    sct.init_sct()
    # call main function
    main()
