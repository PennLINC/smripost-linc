# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Workflows for parcellating imaging data."""

from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe
from niworkflows.engine.workflows import LiterateWorkflow as Workflow

from smripost_linc import config
from smripost_linc.interfaces.bids import BIDSURI


def init_load_atlases_wf(atlases, name='load_atlases_wf'):
    """Load atlases, warp them to fsnative, and convert them to annot files.

    1.  Identify the atlases to be used in the workflow.
    2.  Classify atlases as fsLR, fsaverage, or fsnative-annot.
    3.  Warp the fsLR atlases to fsaverage.
    4.  Convert fsaverage atlases to annot files. (nibabel)
    5.  Warp fsaverage-annot files to fsnative-annot files. (mri_surf2surf)
    6.  Write out fsnative-annot files to derivatives.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from smripost_linc.tests.tests import mock_config
            from smripost_linc import config
            from smripost_linc.workflows.parcellation import init_load_atlases_wf

            with mock_config():
                wf = init_load_atlases_wf()

    Parameters
    ----------
    %(name)s
        Default is 'load_atlases_wf'.

    Inputs
    ------
    name_source

    Outputs
    -------
    atlas_files
    atlas_labels_files
    """
    from neuromaps import transforms

    from smripost_linc.interfaces.bids import DerivativesDataSink
    from smripost_linc.interfaces.misc import CiftiSeparateMetric
    from smripost_linc.utils.boilerplate import describe_atlases
    from smripost_linc.utils.parcellation import convert_gifti_to_annot

    workflow = Workflow(name=name)
    output_dir = config.execution.output_dir

    # Reorganize the atlas file information
    atlas_names, atlas_files, atlas_labels_files, atlas_metadata = [], [], [], []
    atlas_datasets = []
    for atlas, atlas_dict in atlases.items():
        config.loggers.workflow.info(f'Loading atlas: {atlas}')
        atlas_names.append(atlas)
        atlas_datasets.append(atlas_dict['dataset'])
        atlas_files.append(atlas_dict['image'])
        atlas_labels_files.append(atlas_dict['labels'])
        atlas_metadata.append(atlas_dict['metadata'])

    # Write a description
    atlas_str = describe_atlases(atlas_names)
    workflow.__desc__ = f"""
#### Segmentations

The following atlases were used in the workflow: {atlas_str}.
"""

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'name_source',
                'atlas_names',
                'atlas_datasets',
                'atlas_files',
                'atlas_labels_files',
                'atlas_metadata',
            ],
        ),
        name='inputnode',
    )
    inputnode.inputs.atlas_names = atlas_names
    inputnode.inputs.atlas_datasets = atlas_datasets
    inputnode.inputs.atlas_files = atlas_files
    inputnode.inputs.atlas_labels_files = atlas_labels_files
    inputnode.inputs.atlas_metadata = atlas_metadata

    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'atlas_names',
                'lh_fsaverage_annots',
                'rh_fsaverage_annots',
                'atlas_labels_files',
                'atlas_metadata',
            ],
        ),
        name='outputnode',
    )
    workflow.connect([
        (inputnode, outputnode, [
            ('atlas_names', 'atlas_names'),
            ('atlas_metadata', 'atlas_metadata'),
        ]),
    ])  # fmt:skip

    lh_annots = pe.Node(
        niu.Merge(len(atlases)),
        name='lh_annots',
    )
    rh_annots = pe.Node(
        niu.Merge(len(atlases)),
        name='rh_annots',
    )

    for i_atlas, (atlas, info) in enumerate(atlases.items()):
        gifti_buffer = pe.Node(
            niu.IdentityInterface(fields=['lh_gifti', 'rh_gifti']),
            name=f'gifti_buffer_{atlas}',
        )
        if info['format'] == 'gifti':
            gifti_buffer.inputs.lh_gifti = info['image'][0]
            gifti_buffer.inputs.rh_gifti = info['image'][1]

        elif info['format'] == 'cifti':
            # Split CIFTI into GIFTIs
            lh_cifti_to_gifti = pe.Node(
                CiftiSeparateMetric(
                    in_file=info['image'],
                    metric='CORTEX_LEFT',
                    direction='COLUMN',
                    num_threads=config.nipype.omp_nthreads,
                ),
                name=f'lh_cifti_to_gifti_{atlas}',
                n_procs=config.nipype.omp_nthreads,
            )
            rh_cifti_to_gifti = pe.Node(
                CiftiSeparateMetric(
                    in_file=info['image'],
                    metric='CORTEX_RIGHT',
                    direction='COLUMN',
                    num_threads=config.nipype.omp_nthreads,
                ),
                name=f'rh_cifti_to_gifti_{atlas}',
                n_procs=config.nipype.omp_nthreads,
            )
            workflow.connect([
                (lh_cifti_to_gifti, gifti_buffer, [('out_file', 'lh_gifti')]),
                (rh_cifti_to_gifti, gifti_buffer, [('out_file', 'rh_gifti')]),
            ])  # fmt:skip

        elif info['format'] == 'nifti' and info['space'] == 'MNI152NLin6Asym':
            # Convert NIfTI to GIFTI
            nifti_to_gifti = pe.Node(
                niu.Function(
                    function=transforms.mni152_to_fsaverage,
                    output_names=['lh_gifti', 'rh_gifti'],
                ),
                name=f'nifti_to_gifti_{atlas}',
            )
            nifti_to_gifti.inputs.img = info['image']
            nifti_to_gifti.inputs.fsavg_density = '164k'
            nifti_to_gifti.inputs.method = 'nearest'

            workflow.connect([
                (nifti_to_gifti, gifti_buffer, [
                    ('lh_gifti', 'lh_gifti'),
                    ('rh_gifti', 'rh_gifti'),
                ]),
            ])  # fmt:skip

            # The space is now fsaverage
            info['space'] = 'fsaverage'

        elif info['format'] == 'nifti':
            raise NotImplementedError(
                f'Unsupported format ({info["format"]}) and space ({info["space"]}) combination.'
            )

        else:
            raise NotImplementedError(f'Unsupported format ({info["format"]}).')

        for hemi in ['L', 'R']:
            annot_node = lh_annots if hemi == 'L' else rh_annots

            # Identify space and file-type of the atlas
            if info['space'] == 'fsLR':
                # Warp atlas from fsLR to fsaverage
                warp_fslr_to_fsaverage = pe.Node(
                    niu.Function(
                        function=transforms.fslr_to_fsaverage,
                    ),
                    name=f'warp_fslr_to_fsaverage_{atlas}_{hemi}',
                )
                warp_fslr_to_fsaverage.inputs.target_density = '164k'
                warp_fslr_to_fsaverage.inputs.hemi = hemi
                warp_fslr_to_fsaverage.inputs.method = 'nearest'
                workflow.connect([
                    (gifti_buffer, warp_fslr_to_fsaverage, [(f'{hemi.lower()}h_gifti', 'in_file')]),
                ])  # fmt:skip

                # Convert fsaverage to annot
                gifti_to_annot = pe.Node(
                    niu.Function(
                        function=convert_gifti_to_annot,
                    ),
                    name=f'gifti_to_annot_{atlas}_{hemi}',
                )
                workflow.connect([
                    (warp_fslr_to_fsaverage, gifti_to_annot, [('out', 'in_file')]),
                    (gifti_to_annot, annot_node, [('out', f'in{i_atlas + 1}')]),
                ])  # fmt:skip

            elif info['space'] == 'fsaverage':
                # Convert fsaverage to annot
                gifti_to_annot = pe.Node(
                    niu.Function(
                        function=convert_gifti_to_annot,
                    ),
                    name=f'gifti_to_annot_{atlas}_{hemi}',
                )
                workflow.connect([
                    (gifti_buffer, gifti_to_annot, [(f'{hemi.lower()}h_gifti', 'in_file')]),
                    (gifti_to_annot, annot_node, [('out', f'in{i_atlas + 1}')]),
                ])  # fmt:skip

            elif info['space'] == 'fsnative':
                raise NotImplementedError('fsnative atlases are not yet supported.')

    atlas_srcs = pe.MapNode(
        BIDSURI(
            numinputs=1,
            dataset_links=config.execution.dataset_links,
            out_dir=str(output_dir),
        ),
        name='atlas_srcs',
        iterfield=['in1'],
        run_without_submitting=True,
    )
    workflow.connect([(inputnode, atlas_srcs, [('atlas_files', 'in1')])])

    ds_atlas_lh = pe.MapNode(
        DerivativesDataSink(
            hemi='L',
            space='fsaverage',
            suffix='dseg',
            extension='.annot',
        ),
        name='ds_atlas_lh',
        iterfield=['in_file', 'atlas', 'meta_dict', 'Sources'],
        run_without_submitting=True,
    )
    workflow.connect([
        (inputnode, ds_atlas_lh, [
            ('atlas_names', 'atlas'),
            ('atlas_metadata', 'meta_dict'),
        ]),
        (lh_annots, ds_atlas_lh, [('out', 'in_file')]),
        (atlas_srcs, ds_atlas_lh, [('out', 'Sources')]),
        (ds_atlas_lh, outputnode, [('out_file', 'lh_fsaverage_annots')]),
    ])  # fmt:skip

    ds_atlas_rh = pe.MapNode(
        DerivativesDataSink(
            hemi='R',
            space='fsaverage',
            suffix='dseg',
            extension='.annot',
        ),
        name='ds_atlas_rh',
        iterfield=['in_file', 'atlas', 'meta_dict', 'Sources'],
        run_without_submitting=True,
    )
    workflow.connect([
        (inputnode, ds_atlas_rh, [
            ('name_source', 'source_file'),
            ('atlas_names', 'atlas'),
            ('atlas_metadata', 'meta_dict'),
        ]),
        (lh_annots, ds_atlas_rh, [('out', 'in_file')]),
        (atlas_srcs, ds_atlas_rh, [('out', 'Sources')]),
        (ds_atlas_rh, outputnode, [('out_file', 'rh_fsaverage_annots')]),
    ])  # fmt:skip

    copy_atlas_labels_file = pe.MapNode(
        DerivativesDataSink(suffix='dseg', extension='.tsv'),
        name='copy_atlas_labels_file',
        iterfield=['in_file', 'atlas'],
        run_without_submitting=True,
    )
    workflow.connect([
        (inputnode, copy_atlas_labels_file, [
            ('name_source', 'source_file'),
            ('atlas_names', 'atlas'),
            ('atlas_labels_files', 'in_file'),
        ]),
        (copy_atlas_labels_file, outputnode, [('out_file', 'atlas_labels_files')]),
    ])  # fmt:skip

    return workflow


def init_warp_atlases_to_fsnative_wf(
    anat_file,
    atlases,
    name='warp_atlases_to_fsnative_wf',
):
    """Warp fsaverage atlases in annot format to fsnative space (still in annot format).

    Parameters
    ----------
    anat_file : str
        Path to the anatomical file.
        Just used to set the source_file in the DerivativesDataSink.
    atlases : list of str
        List of atlas names.
    name : str
        Workflow name.

    Inputs
    ------
    freesurfer_dir
        Path to the FreeSurfer directory.
    lh_fsaverage_annots
        List of left hemisphere fsaverage annot files.
    rh_fsaverage_annots
        List of right hemisphere fsaverage annot files.
    atlas_metadata
        Metadata for the atlases.

    Outputs
    -------
    lh_fsnative_annots
        List of left hemisphere fsnative annot files.
    rh_fsnative_annots
        List of right hemisphere fsnative annot files.
    """
    from nipype.interfaces import freesurfer as fs

    from smripost_linc.interfaces.bids import DerivativesDataSink

    workflow = Workflow(name=name)
    output_dir = config.execution.output_dir

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'subject_id',
                'freesurfer_dir',
                'lh_fsaverage_annots',
                'rh_fsaverage_annots',
                'atlas_metadata',
            ],
        ),
        name='inputnode',
    )
    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'lh_fsnative_annots',
                'rh_fsnative_annots',
            ],
        ),
        name='outputnode',
    )

    lh_fsnative_annots = pe.Node(
        niu.Merge(len(atlases)),
        name='lh_fsnative_annots',
    )
    rh_fsnative_annots = pe.Node(
        niu.Merge(len(atlases)),
        name='rh_fsnative_annots',
    )

    for hemi in ['L', 'R']:
        annot_node = lh_fsnative_annots if hemi == 'L' else rh_fsnative_annots

        hemistr = f'{hemi.lower()}h'
        fsaverage_to_fsnative = pe.MapNode(
            fs.SurfaceTransform(
                hemi=hemistr,
                source_subject='fsaverage',
            ),
            name=f'fsaverage_to_fsnative_{hemistr}',
            iterfield=['source_annot_file'],
        )
        workflow.connect([
            (inputnode, fsaverage_to_fsnative, [
                (f'{hemistr}_fsaverage_annots', 'source_annot_file'),
                ('freesurfer_dir', 'subjects_dir'),
                ('subject_id', 'target_subject'),
            ]),
        ])  # fmt:skip

        # Use a loop instead of MapNodes because DerivativesDataSink won't apply
        for i_atlas, atlas in enumerate(atlases):
            select_fsaverage_annot = pe.Node(
                niu.Select(index=i_atlas),
                name=f'select_fsaverage_annot_{hemistr}_{atlas}',
            )
            select_fsnative_annot = pe.Node(
                niu.Select(index=i_atlas),
                name=f'select_fsnative_annot_{hemistr}_{atlas}',
            )
            select_atlas_metadata = pe.Node(
                niu.Select(index=i_atlas),
                name=f'select_atlas_metadata_{hemistr}_{atlas}',
            )
            workflow.connect([
                (inputnode, select_fsaverage_annot, [(f'{hemistr}_fsaverage_annots', 'inlist')]),
                (inputnode, select_atlas_metadata, [('atlas_metadata', 'inlist')]),
                (fsaverage_to_fsnative, select_fsnative_annot, [('out_file', 'inlist')]),
            ])  # fmt:skip

            atlas_src = pe.Node(
                BIDSURI(
                    numinputs=1,
                    dataset_links=config.execution.dataset_links,
                    out_dir=str(output_dir),
                ),
                name=f'atlas_src_{hemistr}_{atlas}',
                run_without_submitting=True,
            )
            workflow.connect([(select_fsaverage_annot, atlas_src, [('out', 'in1')])])

            ds_fsnative_atlas = pe.Node(
                DerivativesDataSink(
                    source_file=anat_file,
                    space='fsnative',
                    segmentation=atlas,
                    hemi=hemi,
                    extension='.annot',
                ),
                name=f'ds_fsnative_atlas_{hemistr}_{atlas}',
                iterfield=['in_file', 'meta_dict', 'Sources'],
            )
            workflow.connect([
                (select_atlas_metadata, ds_fsnative_atlas, [('out', 'meta_dict')]),
                (atlas_src, ds_fsnative_atlas, [('out', 'Sources')]),
                (ds_fsnative_atlas, annot_node, [('out_file', f'in{i_atlas}')]),
            ])  # fmt:skip

    workflow.connect([
        (lh_fsnative_annots, outputnode, [('out', 'lh_fsnative_annots')]),
        (rh_fsnative_annots, outputnode, [('out', 'rh_fsnative_annots')]),
    ])  # fmt:skip

    return workflow
