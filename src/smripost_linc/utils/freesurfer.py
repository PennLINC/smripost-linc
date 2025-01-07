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


def symlink_freesurfer_dir(freesurfer_dir, output_dir=None):
    """Symlink the FreeSurfer directory to the output directory.

    Folders will be created in the output directory if they do not exist,
    while files will be symlinked.

    Parameters
    ----------
    freesurfer_dir : str
        Path to the FreeSurfer directory.
    output_dir : str or None
        Path to the output directory. If None, the current working directory
        will be used.

    Returns
    -------
    str
        Path to the output directory.
    """
    import os
    from pathlib import Path

    if output_dir is None:
        output_dir = os.getcwd()

    freesurfer_dir = Path(freesurfer_dir).resolve()
    output_dir = Path(output_dir).resolve()

    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    for root, _, files in os.walk(freesurfer_dir):
        output_sub_dir = output_dir / Path(root).relative_to(freesurfer_dir)
        output_sub_dir.mkdir(exist_ok=True)

        for file_ in files:
            os.symlink(
                Path(root) / file_,
                output_sub_dir / file_,
            )

    return str(output_dir)
