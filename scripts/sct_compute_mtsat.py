#!/usr/bin/env python
# -*- coding: utf-8
#########################################################################################
#
# Compute MT saturation map and T1 map from a PD-weigthed, a T1-weighted and MT-weighted FLASH images
#
# Reference paper:
#    Helms G, Dathe H, Kallenberg K, Dechent P. High-resolution maps of magnetization transfer with inherent correction
#    for RF inhomogeneity and T1 relaxation obtained from 3D FLASH MRI. Magn Reson Med 2008;60(6):1396-1407.

# ---------------------------------------------------------------------------------------
# Copyright (c) 2018 Polytechnique Montreal <www.neuro.polymtl.ca>
# Author: Julien Cohen-Adad
#
# About the license: see the file LICENSE.TXT
#########################################################################################


import sys
import os
import argparse
import json

from spinalcordtoolbox.utils import Metavar, SmartFormatter, splitext
from spinalcordtoolbox.qmri.mt import compute_mtsat
from spinalcordtoolbox.image import Image

import sct_utils as sct


def get_parser(argv):
    parser = argparse.ArgumentParser(
        description='Compute MTsat and T1map. '
                    'Reference: Helms G, Dathe H, Kallenberg K, Dechent P. High-resolution maps of magnetization '
                    'transfer with inherent correction for RF inhomogeneity and T1 relaxation obtained from 3D FLASH '
                    'MRI. Magn Reson Med 2008;60(6):1396-1407.',
        add_help=False,
        formatter_class=SmartFormatter,
        prog=os.path.basename(__file__).strip(".py")
    )

    mandatoryArguments = parser.add_argument_group("\nMANDATORY ARGUMENTS")
    mandatoryArguments.add_argument(
        "-mt",
        required=True,
        help="Image with MT_ON",
        metavar=Metavar.file,
        )
    mandatoryArguments.add_argument(
        "-pd",
        required=True,
        help="Image PD weighted (typically, the MT_OFF)",
        metavar=Metavar.file,
        )
    mandatoryArguments.add_argument(
        "-t1",
        required=True,
        help="Image T1-weighted",
        metavar=Metavar.file,
        )

    optional = parser.add_argument_group('\nOPTIONAL ARGUMENTS')
    optional.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message and exit")
    optional.add_argument(
        "-trmt",
        help="TR [in ms] for mt image. By default, will be fetch from the json sidecar (if it exists).",
        type=float,
        metavar=Metavar.float,
        )
    optional.add_argument(
        "-trpd",
        help="TR [in ms] for pd image. By default, will be fetch from the json sidecar (if it exists).",
        type=float,
        metavar=Metavar.float,
        )
    optional.add_argument(
        "-trt1",
        help="TR [in ms] for t1 image. By default, will be fetch from the json sidecar (if it exists).",
        type=float,
        metavar=Metavar.float,
        )
    optional.add_argument(
        "-famt",
        help="Flip angle [in deg] for mt image. By default, will be fetch from the json sidecar (if it exists).",
        type=float,
        metavar=Metavar.float,
        )
    optional.add_argument(
        "-fapd",
        help="Flip angle [in deg] for pd image. By default, will be fetch from the json sidecar (if it exists).",
        type=float,
        metavar=Metavar.float,
        )
    optional.add_argument(
        "-fat1",
        help="Flip angle [in deg] for t1 image. By default, will be fetch from the json sidecar (if it exists).",
        type=float,
        metavar=Metavar.float,
        )
    optional.add_argument(
        "-b1map",
        help="B1 map",
        metavar=Metavar.file,
        default=None)
    optional.add_argument(
        "-omtsat",
        metavar=Metavar.str,
        help="Output file for MTsat. Default is mtsat.nii.gz",
        default=None)
    optional.add_argument(
        "-ot1map",
        metavar=Metavar.str,
        help="Output file for T1map. Default is t1map.nii.gz",
        default=None)
    optional.add_argument(
        "-v",
        help="Verbose: 0 = no verbosity, 1 = verbose (default).",
        type=int,
        choices=(0, 1),
        default=1)

    return parser


def get_json_file_name(fname, check_exist=False):
    """
    Get json file name by replacing '.nii' or '.nii.gz' extension by '.json'.
    Check if input file follows NIFTI extension rules.
    Optional: check if json file exists.
    :param fname: str: Input NIFTI file name.
    check_exist: Bool: Check if json file exists.
    :return: fname_json
    """
    list_ext = ['.nii', '.nii.gz']
    basename, ext = splitext(fname)
    if ext not in list_ext:
        raise ValueError("Problem with file: {}. Extension should be one of {}".format(fname, list_ext))
    fname_json = basename + '.json'

    if check_exist:
        if not os.path.isfile(fname_json):
            raise FileNotFoundError(f"{fname_json} not found. Either provide the file alongside {fname}, or explicitly "
                                    f"set tr and fa arguments for this image type.")

    return fname_json


def fetch_metadata(fname_json, field):
    """
    Return specific field value from json sidecar.
    :param fname_json: str: Json file
    :param field: str: Field to retrieve
    :return: value of the field.
    """
    with open(fname_json) as f:
        metadata = json.load(f)
    if field not in metadata:
        KeyError("Json file {} does not contain the field: {}".format(fname_json, field))
    else:
        return metadata[field]


def main(argv):
    parser = get_parser(argv)
    args = parser.parse_args(argv if argv else ['--help'])
    verbose = args.v
    sct.init_sct(log_level=verbose, update=True)  # Update log level

    sct.printv('Load data...', verbose)
    nii_mt = Image(args.mt)
    nii_pd = Image(args.pd)
    nii_t1 = Image(args.t1)
    if args.b1map is None:
        nii_b1map = None
    else:
        nii_b1map = Image(args.b1map)

    if args.trmt is None:
        args.trmt = fetch_metadata(get_json_file_name(args.mt, check_exist=True), 'RepetitionTime')
    if args.trpd is None:
        args.trpd = fetch_metadata(get_json_file_name(args.pd, check_exist=True), 'RepetitionTime')
    if args.trt1 is None:
        args.trt1 = fetch_metadata(get_json_file_name(args.t1, check_exist=True), 'RepetitionTime')
    if args.famt is None:
        args.famt = fetch_metadata(get_json_file_name(args.mt, check_exist=True), 'FlipAngle')
    if args.fapd is None:
        args.fapd = fetch_metadata(get_json_file_name(args.pd, check_exist=True), 'FlipAngle')
    if args.fat1 is None:
        args.fat1 = fetch_metadata(get_json_file_name(args.t1, check_exist=True), 'FlipAngle')

    # compute MTsat
    nii_mtsat, nii_t1map = compute_mtsat(nii_mt, nii_pd, nii_t1,
                                         args.trmt, args.trpd, args.trt1,
                                         args.famt, args.fapd, args.fat1,
                                         nii_b1map=nii_b1map)

    # Output MTsat and T1 maps
    # by default, output in the same directory as the input images
    sct.printv('Generate output files...', verbose)
    if args.omtsat is None:
        fname_mtsat = os.path.join(os.path.dirname(nii_mt.absolutepath), "mtsat.nii.gz")
    else:
        fname_mtsat = args.omtsat
    nii_mtsat.save(fname_mtsat)
    if args.ot1map is None:
        fname_t1map = os.path.join(os.path.dirname(nii_mt.absolutepath), "t1map.nii.gz")
    else:
        fname_t1map = args.ot1map
    nii_t1map.save(fname_t1map)

    sct.display_viewer_syntax([fname_mtsat, fname_t1map],
                              colormaps=['gray', 'gray'],
                              minmax=['-10,10', '0, 3'],
                              opacities=['1', '1'],
                              verbose=verbose)


if __name__ == '__main__':
    main(sys.argv[1:])
