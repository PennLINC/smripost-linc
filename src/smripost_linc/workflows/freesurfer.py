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

    freesurfer_files = pe.Node(
        FreesurferInputs(),
        name='freesurfer_files',
    )
    workflow.connect([(inputnode, freesurfer_files, [('freesurfer_dir', 'freesurfer_dir')])])

    return workflow
