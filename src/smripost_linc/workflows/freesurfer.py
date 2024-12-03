# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Workflows for working with FreeSurfer derivatives."""

from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe
from niworkflows.engine.workflows import LiterateWorkflow as Workflow


def init_parcellate_external_wf(
    atlases,
    mem_gb,
    name='parcellate_external_wf',
):
    """Parcellate external atlases provided as fsnative-space annot files.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from smripost_linc.tests.tests import mock_config
            from smripost_linc import config
            from smripost_linc.workflows.freesurfer import init_parcellate_external_wf

            with mock_config():
                wf = init_parcellate_external_wf(mem_gb={'resampled': 2})

    Parameters
    ----------
    mem_gb : :obj:`dict`
        Dictionary of memory allocations.
    name : :obj:`str`
        Workflow name.
        Default is 'parcellate_external_wf'.

    Inputs
    ------
    lh_fsnative_annots
    rh_fsnative_annots

    Outputs
    -------
    parcellated_tsvs
        Parcellated TSV files. One for each atlas and hemisphere.
    """
    print(atlases)
    print(mem_gb)

    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'freesurfer_dir',
                'lh_fsnative_annots',
                'rh_fsnative_annots',
            ],
        ),
        name='inputnode',
    )

    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'parcellated_tsvs',
            ],
        ),
        name='outputnode',
    )
    workflow.add_nodes([inputnode, outputnode])

    # Select Freesurfer files to parcellate

    # Parcellate each data file with each atlas in each hemisphere

    # Convert parcellated data to TSV

    # Write out parcellated data
    ...

    return workflow
