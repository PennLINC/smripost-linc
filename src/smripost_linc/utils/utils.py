"""Utility functions for sMRIPost-LINC."""

import logging
import os.path as op

import numpy as np
import pandas as pd

LGR = logging.getLogger(__name__)


def motpars_fmriprep2fsl(confounds):
    """Convert fMRIPrep motion parameters to FSL format.

    Parameters
    ----------
    confounds : str or pandas.DataFrame
        Confounds data from fMRIPrep.
        Relevant columns have the format "[rot|trans]_[x|y|z]".
        Rotations are in radians.

    Returns
    -------
    motpars_fsl : (T x 6) numpy.ndarray
        Motion parameters in FSL format, with rotations first (in radians) and
        translations second.
    """
    if isinstance(confounds, str) and op.isfile(confounds):
        confounds = pd.read_table(confounds)
    elif not isinstance(confounds, pd.DataFrame):
        raise ValueError('Input must be an existing file or a DataFrame.')

    # Rotations are in radians
    motpars_fsl = confounds[['rot_x', 'rot_y', 'rot_z', 'trans_x', 'trans_y', 'trans_z']].values
    return motpars_fsl


def motpars_spm2fsl(motpars):
    """Convert SPM format motion parameters to FSL format.

    Parameters
    ----------
    motpars : str or array_like
        SPM-format motion parameters.
        Rotations are in degrees and translations come first.

    Returns
    -------
    motpars_fsl : (T x 6) numpy.ndarray
        Motion parameters in FSL format, with rotations first (in radians) and
        translations second.
    """
    if isinstance(motpars, str) and op.isfile(motpars):
        motpars = np.loadtxt(motpars)
    elif not isinstance(motpars, np.ndarray):
        raise ValueError('Input must be an existing file or a numpy array.')

    if motpars.shape[1] != 6:
        raise ValueError(f'Motion parameters must have exactly 6 columns, not {motpars.shape[1]}.')

    # Split translations from rotations
    trans, rot = motpars[:, :3], motpars[:, 3:]

    # Convert rotations from degrees to radians
    rot *= np.pi / 180.0

    # Place rotations first
    motpars_fsl = np.hstack((rot, trans))
    return motpars_fsl


def motpars_afni2fsl(motpars):
    """Convert AFNI format motion parameters to FSL format.

    Parameters
    ----------
    motpars : str or array_like
        AfNI-format motion parameters in 1D file.
        Rotations are in degrees and translations come first.

    Returns
    -------
    motpars_fsl : (T x 6) numpy.ndarray
        Motion parameters in FSL format, with rotations first (in radians) and
        translations second.
    """
    if isinstance(motpars, str) and op.isfile(motpars):
        motpars = np.loadtxt(motpars)
    elif not isinstance(motpars, np.ndarray):
        raise ValueError('Input must be an existing file or a numpy array.')

    if motpars.shape[1] != 6:
        raise ValueError(f'Motion parameters must have exactly 6 columns, not {motpars.shape[1]}.')

    # Split translations from rotations
    trans, rot = motpars[:, :3], motpars[:, 3:]

    # Convert rotations from degrees to radians
    rot *= np.pi / 180.0

    # Place rotations first
    motpars_fsl = np.hstack((rot, trans))
    return motpars_fsl


def load_motpars(motion_file, source='auto'):
    """Load motion parameters from file.

    Parameters
    ----------
    motion_file : str
        Motion file.
    source : {"auto", "spm", "afni", "fsl", "fmriprep"}, optional
        Source of the motion data.
        If "auto", try to deduce the source based on the name of the file.

    Returns
    -------
    motpars : (T x 6) numpy.ndarray
        Motion parameters in FSL format, with rotations first (in radians) and
        translations second.
    """
    if source == 'auto':
        if op.basename(motion_file).startswith('rp_') and motion_file.endswith('.txt'):
            source = 'spm'
        elif motion_file.endswith('.1D'):
            source = 'afni'
        elif motion_file.endswith('.tsv'):
            source = 'fmriprep'
        elif motion_file.endswith('.txt'):
            source = 'fsl'
        else:
            raise Exception('Motion parameter source could not be determined automatically.')

    if source == 'spm':
        motpars = motpars_spm2fsl(motion_file)
    elif source == 'afni':
        motpars = motpars_afni2fsl(motion_file)
    elif source == 'fsl':
        motpars = np.loadtxt(motion_file)
    elif source == 'fmriprep':
        motpars = motpars_fmriprep2fsl(motion_file)
    else:
        raise ValueError(f'Source "{source}" not supported.')

    return motpars


def get_resource_path():
    """Return the path to general resources.

    Returns the path to general resources, terminated with separator.
    Resources are kept outside package folder in "resources".
    Based on function by Yaroslav Halchenko used in Neurosynth Python package.

    Returns
    -------
    resource_path : str
        Absolute path to resources folder.
    """
    return op.abspath(op.join(op.dirname(__file__), 'resources') + op.sep)


def _get_wf_name(bold_fname, prefix):
    """Derive the workflow name for supplied BOLD file.

    >>> _get_wf_name("/completely/made/up/path/sub-01_task-nback_bold.nii.gz", "aroma")
    'aroma_task_nback_wf'
    >>> _get_wf_name(
    ...     "/completely/made/up/path/sub-01_task-nback_run-01_echo-1_bold.nii.gz",
    ...     "preproc",
    ... )
    'preproc_task_nback_run_01_echo_1_wf'

    """
    from nipype.utils.filemanip import split_filename

    fname = split_filename(bold_fname)[1]
    fname_nosub = '_'.join(fname.split('_')[1:-1])
    return f"{prefix}_{fname_nosub.replace('-', '_')}_wf"


def update_dict(orig_dict, new_dict):
    """Update dictionary with values from another dictionary.

    Parameters
    ----------
    orig_dict : dict
        Original dictionary.
    new_dict : dict
        Dictionary with new values.

    Returns
    -------
    updated_dict : dict
        Updated dictionary.
    """
    updated_dict = orig_dict.copy()
    for key, value in new_dict.items():
        if (orig_dict.get(key) is not None) and (value is not None):
            print(f'Updating {key} from {orig_dict[key]} to {value}')
            updated_dict[key].update(value)
        elif value is not None:
            updated_dict[key] = value

    return updated_dict


def _convert_to_tsv(in_file):
    """Convert a file to TSV format.

    Parameters
    ----------
    in_file : str
        Input file.

    Returns
    -------
    out_file : str
        Output file.
    """
    import os

    import numpy as np

    out_file = os.path.abspath('out_file.tsv')
    arr = np.loadtxt(in_file)
    np.savetxt(out_file, arr, delimiter='\t')
    return out_file
