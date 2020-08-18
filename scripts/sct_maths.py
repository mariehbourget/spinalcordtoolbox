#!/usr/bin/env python
#########################################################################################
#
# Perform mathematical operations on images
#
# ---------------------------------------------------------------------------------------
# Copyright (c) 2015 Polytechnique Montreal <www.neuro.polymtl.ca>
# Authors: Julien Cohen-Adad, Sara Dupont
#
# About the license: see the file LICENSE.TXT
#########################################################################################

from __future__ import division, absolute_import

import os
import sys

import numpy as np
import argparse
import pickle
import gzip
import matplotlib
import matplotlib.pyplot as plt

from spinalcordtoolbox.image import Image
from spinalcordtoolbox.utils import Metavar, SmartFormatter
import spinalcordtoolbox.math as sct_math

from sct_utils import printv, extract_fname, display_viewer_syntax, init_sct


def get_parser():

    parser = argparse.ArgumentParser(
        description='Perform mathematical operations on images. Some inputs can be either a number or a 4d image or '
                    'several 3d images separated with ","',
        add_help=None,
        formatter_class=SmartFormatter,
        prog=os.path.basename(__file__).strip(".py"))

    mandatory = parser.add_argument_group("MANDATORY ARGUMENTS")
    mandatory.add_argument(
        "-i",
        metavar=Metavar.file,
        help="Input file. Example: data.nii.gz",
        required=True)
    mandatory.add_argument(
        "-o",
        metavar=Metavar.file,
        help='Output file. Example: data_mean.nii.gz',
        required=True)

    optional = parser.add_argument_group("OPTIONAL ARGUMENTS")
    optional.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message and exit")

    basic = parser.add_argument_group('BASIC OPERATIONS')
    basic.add_argument(
        "-add",
        metavar='',
        nargs="+",
        help='Add following input. Can be a number or multiple images (separated with space).',
        required=False)
    basic.add_argument(
        "-sub",
        metavar='',
        nargs="+",
        help='Subtract following input. Can be a number or an image.',
        required=False)
    basic.add_argument(
        "-mul",
        metavar='',
        nargs="+",
        help='Multiply by following input. Can be a number or multiple images (separated with space).',
        required=False)
    basic.add_argument(
        "-div",
        metavar='',
        nargs="+",
        help='Divide by following input. Can be a number or an image.',
        required=False)
    basic.add_argument(
        '-mean',
        help='Average data across dimension.',
        required=False,
        choices=('x', 'y', 'z', 't'))
    basic.add_argument(
        '-rms',
        help='Compute root-mean-squared across dimension.',
        required=False,
        choices=('x', 'y', 'z', 't'))
    basic.add_argument(
        '-std',
        help='Compute STD across dimension.',
        required=False,
        choices=('x', 'y', 'z', 't'))
    basic.add_argument(
        "-bin",
        type=float,
        metavar=Metavar.float,
        help='Binarize image using specified threshold. Example: 0.5',
        required=False)

    thresholding = parser.add_argument_group("THRESHOLDING METHODS")
    thresholding.add_argument(
        '-otsu',
        type=int,
        metavar=Metavar.int,
        help='Threshold image using Otsu algorithm (from skimage). Specify the number of bins (e.g. 16, 64, 128)',
        required=False)
    thresholding.add_argument(
        "-adap",
        metavar=Metavar.list,
        help="R|Threshold image using Adaptive algorithm (from skimage). Separate following arguments with ',':"
             "\n Block size: Odd size of pixel neighborhood which is used to calculate the threshold value (e.g. 3, 7, 21, ...)"
             "\n Offset: Constant subtracted from weighted mean of neighborhood to calculate the local threshold value. Suggested offset is 0.",
        required=False)
    thresholding.add_argument(
        "-otsu-median",
        help="R|Threshold image using Median Otsu algorithm. Separate following arguments with ',':"
             "\n Size of the median filter (e.g. 2, 3)"
             "\n Number of iterations (e.g. 3, 4, 5)\n",
        metavar=Metavar.list,
        required=False)
    thresholding.add_argument(
        '-percent',
        type=int,
        help="Threshold image using percentile of its histogram.",
        metavar=Metavar.int,
        required=False)
    thresholding.add_argument(
        "-thr",
        type=float,
        help='Use following number to threshold image (zero below number).',
        metavar=Metavar.float,
        required=False)

    mathematical = parser.add_argument_group("MATHEMATICAL MORPHOLOGY")
    mathematical.add_argument(
        '-dilate',
        type=int,
        metavar=Metavar.int,
        help="Dilate binary or greyscale image with specified size. If shape={'square', 'cube'}: size corresponds to the length of "
             "an edge (size=1 has no effect). If shape={'disk', 'ball'}: size corresponds to the radius, not including "
             "the center element (size=0 has no effect).",
        required=False)
    mathematical.add_argument(
        '-erode',
        type=int,
        metavar=Metavar.int,
        help="Erode binary or greyscale image with specified size. If shape={'square', 'cube'}: size corresponds to the length of "
             "an edge (size=1 has no effect). If shape={'disk', 'ball'}: size corresponds to the radius, not including "
             "the center element (size=0 has no effect).",
        required=False)
    mathematical.add_argument(
        '-shape',
        help="Shape of the structuring element for the mathematical morphology operation. Default: ball.",
        required=False,
        choices=('square', 'cube', 'disk', 'ball'),
        default='ball')
    mathematical.add_argument(
        '-dim',
        type=int,
        help="Dimension of the array which 2D structural element will be orthogonal to. For example, if you wish to "
             "apply a 2D disk kernel in the X-Y plane, leaving Z unaffected, parameters will be: shape=disk, dim=2.",
        required=False,
        choices=(0, 1, 2))

    filtering = parser.add_argument_group("FILTERING METHODS")
    filtering.add_argument(
        "-smooth",
        metavar='',
        help='Gaussian smoothing filter with specified standard deviations in mm for each axis (Example: 2,2,1) or '
             'single value for all axis (Example: 2).',
        required=False)
    filtering.add_argument(
        '-laplacian',
        nargs="+",
        metavar='',
        help='Laplacian filtering with specified standard deviations in mm for all axes (Example: 2).',
        required=False)
    filtering.add_argument(
        '-denoise',
        help='R|Non-local means adaptative denoising from P. Coupe et al. as implemented in dipy. Separate with ". Example: p=1,b=3\n'
             ' p: (patch radius) similar patches in the non-local means are searched for locally, inside a cube of side 2*p+1 centered at each voxel of interest. Default: p=1\n'
             ' b: (block radius) the size of the block to be used (2*b+1) in the blockwise non-local means implementation. Default: b=5 '
             '    Note, block radius must be smaller than the smaller image dimension: default value is lowered for small images)\n'
             'To use default parameters, write -denoise 1',
        required=False)

    similarity = parser.add_argument_group("SIMILARITY METRIC")
    similarity.add_argument(
        '-mi',
        metavar=Metavar.file,
        help='Compute the mutual information (MI) between both input files (-i and -mi) as in: '
             'http://scikit-learn.org/stable/modules/generated/sklearn.metrics.mutual_info_score.html',
        required=False)
    similarity.add_argument(
        '-minorm',
        metavar=Metavar.file,
        help='Compute the normalized mutual information (MI) between both input files (-i and -mi) as in: '
             'http://scikit-learn.org/stable/modules/generated/sklearn.metrics.normalized_mutual_info_score.html',
        required=False)
    similarity.add_argument(
        '-corr',
        metavar=Metavar.file,
        help='Compute the cross correlation (CC) between both input files (-i and -cc).',
        required=False)

    misc = parser.add_argument_group("MISC")
    misc.add_argument(
        '-symmetrize',
        type=int,
        help='Symmetrize data along the specified dimension.',
        required=False,
        choices=(0, 1, 2))
    misc.add_argument(
        '-type',
        required=False,
        help='Output type.',
        choices=('uint8', 'int16', 'int32', 'float32', 'complex64', 'float64', 'int8', 'uint16', 'uint32', 'int64',
                 'uint64'))
    misc.add_argument(
        '-v',
        action="store_true",
        help="Increase verbosity. Setting this option will enable showing DEBUG messages.",
    )

    return parser


# MAIN
# ==========================================================================================
def main(args=None):
    """
    Main function
    :param args:
    :return:
    """
    dim_list = ['x', 'y', 'z', 't']

    # Get parser args
    if args is None:
        args = None if sys.argv[1:] else ['--help']
    parser = get_parser()
    arguments = parser.parse_args(args=args)
    fname_in = arguments.i
    fname_out = arguments.o
    verbose = arguments.v
    init_sct(log_level=2 if verbose else 1, update=True)
    if '-type' in arguments:
        output_type = arguments.type
    else:
        output_type = None

    # Open file(s)
    im = Image(fname_in)
    data = im.data  # 3d or 4d numpy array
    dim = im.dim

    # run command
    if arguments.otsu is not None:
        param = arguments.otsu
        data_out = sct_math.otsu(data, param)

    elif arguments.adap is not None:
        param = convert_list_str(arguments.adap, "int")
        data_out = sct_math.adap(data, param[0], param[1])

    elif arguments.otsu_median is not None:
        param = convert_list_str(arguments.otsu_median, "int")
        data_out = sct_math.otsu_median(data, param[0], param[1])

    elif arguments.thr is not None:
        param = arguments.thr
        data_out = sct_math.threshold(data, param)

    elif arguments.percent is not None:
        param = arguments.percent
        data_out = sct_math.perc(data, param)

    elif arguments.bin is not None:
        bin_thr = arguments.bin
        data_out = sct_math.binarize(data, bin_thr=bin_thr)

    elif arguments.add is not None:
        data2 = get_data_or_scalar(arguments.add, data)
        data_concat = sct_math.concatenate_along_4th_dimension(data, data2)
        data_out = np.sum(data_concat, axis=3)

    elif arguments.sub is not None:
        data2 = get_data_or_scalar(arguments.sub, data)
        data_out = data - data2

    elif arguments.laplacian is not None:
        sigmas = convert_list_str(arguments.laplacian, "float")
        if len(sigmas) == 1:
            sigmas = [sigmas for i in range(len(data.shape))]
        elif len(sigmas) != len(data.shape):
            printv(parser.error('ERROR: -laplacian need the same number of inputs as the number of image dimension OR only one input'))
        # adjust sigma based on voxel size
        sigmas = [sigmas[i] / dim[i + 4] for i in range(3)]
        # smooth data
        data_out = sct_math.laplacian(data, sigmas)

    elif arguments.mul is not None:
        data2 = get_data_or_scalar(arguments.mul, data)
        data_concat = sct_math.concatenate_along_4th_dimension(data, data2)
        data_out = np.prod(data_concat, axis=3)

    elif arguments.div is not None:
        data2 = get_data_or_scalar(arguments.div, data)
        data_out = np.divide(data, data2)

    elif arguments.mean is not None:
        dim = dim_list.index(arguments.mean)
        if dim + 1 > len(np.shape(data)):  # in case input volume is 3d and dim=t
            data = data[..., np.newaxis]
        data_out = np.mean(data, dim)

    elif arguments.rms is not None:
        dim = dim_list.index(arguments.rms)
        if dim + 1 > len(np.shape(data)):  # in case input volume is 3d and dim=t
            data = data[..., np.newaxis]
        data_out = np.sqrt(np.mean(np.square(data.astype(float)), dim))

    elif arguments.std is not None:
        dim = dim_list.index(arguments.std)
        if dim + 1 > len(np.shape(data)):  # in case input volume is 3d and dim=t
            data = data[..., np.newaxis]
        data_out = np.std(data, dim, ddof=1)

    elif arguments.smooth is not None:
        sigmas = convert_list_str(arguments.smooth, "float")
        if len(sigmas) == 1:
            sigmas = [sigmas[0] for i in range(len(data.shape))]
        elif len(sigmas) != len(data.shape):
            printv(parser.error('ERROR: -smooth need the same number of inputs as the number of image dimension OR only one input'))
        # adjust sigma based on voxel size
        sigmas = [sigmas[i] / dim[i + 4] for i in range(3)]
        # smooth data
        data_out = sct_math.smooth(data, sigmas)

    elif arguments.dilate is not None:
        data_out = sct_math.dilate(data, size=arguments.dilate, shape=arguments.shape, dim=arguments.dim)

    elif arguments.erode is not None:
        data_out = sct_math.erode(data, size=arguments.erode, shape=arguments.shape, dim=arguments.dim)

    elif arguments.denoise is not None:
        # parse denoising arguments
        p, b = 1, 5  # default arguments
        list_denoise = (arguments.denoise).split(",")
        for i in list_denoise:
            if 'p' in i:
                p = int(i.split('=')[1])
            if 'b' in i:
                b = int(i.split('=')[1])
        data_out = sct_math.denoise_nlmeans(data, patch_radius=p, block_radius=b)

    elif arguments.symmetrize is not None:
        data_out = (data + data[list(range(data.shape[0] - 1, -1, -1)), :, :]) / float(2)

    elif arguments.mi is not None:
        # input 1 = from flag -i --> im
        # input 2 = from flag -mi
        im_2 = Image(arguments.mi)
        compute_similarity(im, im_2, fname_out, metric='mi', metric_full='Mutual information', verbose=verbose)
        data_out = None

    elif arguments.minorm is not None:
        im_2 = Image(arguments.minorm)
        compute_similarity(im, im_2, fname_out, metric='minorm', metric_full='Normalized Mutual information', verbose=verbose)
        data_out = None

    elif arguments.corr is not None:
        # input 1 = from flag -i --> im
        # input 2 = from flag -mi
        im_2 = Image(arguments.corr)
        compute_similarity(im, im_2, fname_out, metric='corr', metric_full='Pearson correlation coefficient', verbose=verbose)
        data_out = None

    # if no flag is set
    else:
        data_out = None
        printv(parser.error('ERROR: you need to specify an operation to do on the input image'))

    if data_out is not None:
        # Write output
        nii_out = Image(fname_in)  # use header of input file
        nii_out.data = data_out
        nii_out.save(fname_out, dtype=output_type)
    # TODO: case of multiple outputs
    # assert len(data_out) == n_out
    # if n_in == n_out:
    #     for im_in, d_out, fn_out in zip(nii, data_out, fname_out):
    #         im_in.data = d_out
    #         im_in.absolutepath = fn_out
    #         if "-w" in arguments:
    #             im_in.hdr.set_intent('vector', (), '')
    #         im_in.save()
    # elif n_out == 1:
    #     nii[0].data = data_out[0]
    #     nii[0].absolutepath = fname_out[0]
    #     if "-w" in arguments:
    #             nii[0].hdr.set_intent('vector', (), '')
    #     nii[0].save()
    # elif n_out > n_in:
    #     for dat_out, name_out in zip(data_out, fname_out):
    #         im_out = nii[0].copy()
    #         im_out.data = dat_out
    #         im_out.absolutepath = name_out
    #         if "-w" in arguments:
    #             im_out.hdr.set_intent('vector', (), '')
    #         im_out.save()
    # else:
    #     printv(parser.usage.generate(error='ERROR: not the correct numbers of inputs and outputs'))

    # display message
    if data_out is not None:
        display_viewer_syntax([fname_out], verbose=verbose)
    else:
        printv('\nDone! File created: ' + fname_out, verbose, 'info')


def get_data(list_fname):
    """
    Get data from list of file names
    :param list_fname:
    :return: 3D or 4D numpy array.
    """
    try:
        nii = [Image(f_in) for f_in in list_fname]
    except Exception as e:
        printv(str(e), 1, 'error')  # file does not exist, exit program
    data0 = nii[0].data
    data = nii[0].data
    # check that every images have same shape
    for i in range(1, len(nii)):
        if not np.shape(nii[i].data) == np.shape(data0):
            printv('\nWARNING: shape(' + list_fname[i] + ')=' + str(np.shape(nii[i].data)) + ' incompatible with shape(' + list_fname[0] + ')=' + str(np.shape(data0)), 1, 'warning')
            printv('\nERROR: All input images must have same dimensions.', 1, 'error')
        else:
            data = sct_math.concatenate_along_4th_dimension(data, nii[i].data)
    return data


def get_data_or_scalar(argument, data_in):
    """
    Get data from list of file names (scenario 1) or scalar (scenario 2)
    :param argument: list of file names of scalar
    :param data_in: if argument is scalar, use data to get np.shape
    :return: 3d or 4d numpy array
    """
    # try to convert argument in float
    try:
        # build data2 with same shape as data
        data_out = data_in[:, :, :] * 0 + float(argument[0])
    # if conversion fails, it should be a string (i.e. file name)
    except ValueError:
        data_out = get_data(argument)
    return data_out


def convert_list_str(string_list, type='int'):
    """
    Receive a string and then converts it into a list of selected type.
    Example: "2,2,3" --> [2, 2, 3]
    :param string_list: List of comma-separated string
    :param type: string: int, float
    :return:
    """
    new_type_list = (string_list).split(",")
    for inew_type_list, ele in enumerate(new_type_list):
        if type is "int":
            new_type_list[inew_type_list] = int(ele)
        elif type is "float":
            new_type_list[inew_type_list] = float(ele)

    return new_type_list


def compute_similarity(img1: Image, img2: Image, fname_out: str, metric: str, metric_full: str, verbose):
    """
    Sanitize input and compute similarity metric between two images data.
    """
    if img1.data.size != img2.data.size:
        raise ValueError(f"Input images don't have the same size! \nPlease use  \"sct_register_multimodal -i im1.nii.gz -d im2.nii.gz -identity 1\"  to put the input images in the same space")

    res, data1_1d, data2_1d = sct_math.compute_similarity(img1.data, img2.data, metric=metric)

    if verbose:
        matplotlib.use('Agg')
        plt.plot(data1_1d, 'b')
        plt.plot(data2_1d, 'r')
        plt.grid
        plt.title('Similarity: ' + metric_full + ' = ' + str(res))
        plt.savefig('fig_similarity.png')

    path_out, filename_out, ext_out = extract_fname(fname_out)
    if ext_out not in ['.txt', '.pkl', '.pklz', '.pickle']:
        raise ValueError(f"The output file should a text file or a pickle file. Received extension: {ext_out}")

    if ext_out == '.txt':
        with open(fname_out, 'w') as f:
            f.write(metric_full + ': \n' + str(res))
    elif ext_out == '.pklz':
        pickle.dump(res, gzip.open(fname_out, 'wb'), protocol=2)
    else:
        pickle.dump(res, open(fname_out, 'w'), protocol=2)


if __name__ == "__main__":
    init_sct()
    main()
