# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Workflows for working with FreeSurfer derivatives."""

from smripost_linc import config


def init_postprocess_freesurfer_wf(anat_file, metadata, name='postprocess_freesurfer_wf'):
    """Post-process FreeSurfer outputs."""
    from niworkflows.engine.workflows import LiterateWorkflow as Workflow

    workflow = Workflow(name=name)

    freesurfer_dir = config.execution.fs_subjects_dir

    return workflow
