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
    from nipype.interfaces.freesurfer import ParcellationStats

    from smripost_linc.interfaces.freesurfer import FreesurferFiles, MRISegStats
    from smripost_linc.interfaces.misc import ParcellationStats2TSV

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

    for hemi in ['lh', 'rh']:
        # Select Freesurfer files to parcellate (GWR and LGI)
        fs_files = pe.Node(FreesurferFiles(hemi=hemi), name=f'fs_files_{hemi}')
        workflow.connect([(inputnode, fs_files, [('freesurfer_dir', 'freesurfer_dir')])])

        # Parcellate each data file with each atlas in each hemisphere
        for atlas in atlases:
            mri_segstats = pe.MapNode(
                MRISegStats(
                    hemi=hemi,
                    mem_gb=mem_gb,
                ),
                name=f'mri_segstats_{hemi}_{atlas}',
                iterfield=['seg', 'slabel', 'arguments'],
            )
            workflow.connect([
                (fs_files, mri_segstats, [
                    ('files', 'in_file'),
                    ('names', 'slabel'),
                    ('arguments', 'arguments'),
                ]),
                (inputnode, mri_segstats, [(f'{hemi}_fsnative_annots', 'annot_file')]),
            ])  # fmt:skip

            # Now calculate standard surface stats
            parcellation_stats = pe.Node(
                ParcellationStats(subject_id='', hemisphere=hemi, th3=True, noglobal=True),
                name=f'parcellation_stats_{hemi}_{atlas}',
            )
            workflow.connect([
                (inputnode, parcellation_stats, [(f'{hemi}_fsnative_annots', 'in_annotation')]),
            ])  # fmt:skip

            # Convert parcellated data to TSV
            parcstats_to_tsv = pe.Node(
                ParcellationStats2TSV(
                    hemi=hemi,
                    atlas=atlas,
                ),
                name=f'parcstats_to_tsv_{hemi}_{atlas}',
            )

            # Write out parcellated data
            ...

    return workflow
