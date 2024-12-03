# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Workflows for working with FreeSurfer derivatives."""

from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe
from niworkflows.engine.workflows import LiterateWorkflow as Workflow


def init_postprocess_freesurfer_wf(
    anat_file,
    freesurfer_dir,
    metadata,
    name='postprocess_freesurfer_wf',
):
    """Post-process FreeSurfer outputs.

    1. Collect Freesurfer outputs to parcellate.
    2. Collect necessary transforms to warp atlases to fsnative annot files.
    """

    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'freesurfer_dir',
            ],
        ),
        name='inputnode',
    )

    copy_freesurfer_files = pe.Node(
        niu.Function(
            input_names=['freesurfer_dir', 'output_dir'],
            output_names=['output_dir'],
            function=symlink_freesurfer_dir,
        ),
        name='copy_freesurfer_files',
    )
    workflow.connect([(inputnode, copy_freesurfer_files, [('freesurfer_dir', 'freesurfer_dir')])])

    return workflow


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
