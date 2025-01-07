# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Utilities for working with FreeSurfer outputs."""

import os
from pathlib import Path


def find_fs_path(freesurfer_dir, subject_id, session_id=None):
    """Find a freesurfer dir for subject or subject+session."""

    if freesurfer_dir is None:
        return None

    # Look for longitudinal pipeline outputs first
    if session_id is not None:
        nosub = os.path.join(freesurfer_dir, f'{subject_id}_{session_id}.long.{subject_id}')
        if os.path.exists(nosub):
            return Path(nosub)
        withsub = os.path.join(
            freesurfer_dir,
            f'sub-{subject_id}_ses-{session_id}.long.sub-{subject_id}',
        )
        if os.path.exists(withsub):
            return Path(withsub)

        # Next try with session but not longitudinal processing, if specified
        nosub = os.path.join(freesurfer_dir, f'{subject_id}_{session_id}')
        if os.path.exists(nosub):
            return Path(nosub)
        withsub = os.path.join(freesurfer_dir, f'sub-{subject_id}_ses-{session_id}')
        if os.path.exists(withsub):
            return Path(withsub)

    nosub = os.path.join(freesurfer_dir, subject_id)
    if os.path.exists(nosub):
        return Path(nosub)
    withsub = os.path.join(freesurfer_dir, f'sub-{subject_id}')
    if os.path.exists(withsub):
        return Path(withsub)
    return None
