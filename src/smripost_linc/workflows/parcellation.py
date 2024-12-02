# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Workflows for parcellating imaging data."""

from neuromaps.transforms import fslr_to_fsaverage
from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe
from niworkflows.engine.workflows import LiterateWorkflow as Workflow

from smripost_linc import config
from smripost_linc.interfaces.bids import BIDSURI


def remove_non_alphabetic(input_string):
    """Use regular expression to remove non-alphabetic characters."""
    import re

    clean_string = re.sub(r'[^a-zA-Z_0-9]', '', input_string.replace(' ', '_'))
    return clean_string


def fake_neuroparc_from_nifti(nifti_file):
    """Create a fake neuroparc JSON from a nifti file."""
    import nibabel as nb
    import numpy as np

    img = nb.load(nifti_file)
    unique_labels = np.unique(img.get_fdata().astype(np.int32))
    return {str(label): {} for label in unique_labels}


def fill_missing_parc(spec):
    maxval = max(map(int, spec.keys()))
    for key in range(maxval):
        strkey = str(key)
        if strkey not in spec:
            spec[strkey] = {'label': 'Unknown'}
    return spec


def ctab_from_neuroparc_json(neuroparc_json_file=None, atlas_nifti_file=None):
    """Extract colors and labels from a neuroparc JSON file."""
    import json

    if neuroparc_json_file is not None:
        with open(neuroparc_json_file) as jsonf:
            initial_specs = json.load(jsonf)
            if 'MetaData' in initial_specs:
                del initial_specs['MetaData']
    else:
        initial_specs = fake_neuroparc_from_nifti(atlas_nifti_file)

    parc_specs = fill_missing_parc(initial_specs)
    # Get a mapping from ints to label names from neuroparc
    int_to_label_map = {}
    for key, value in parc_specs.items():
        if not key.isnumeric():
            continue
        key = int(key)
        label = value.get('label') or f'region{key:05d}'
        int_to_label_map[key] = label

    int_to_label_map[0] = 'Unknown'
    labels = [
        remove_non_alphabetic(int_to_label_map[key]) for key in sorted(int_to_label_map.keys())
    ]
    colors = _create_colors(len(labels))
    return colors, labels


def create_annots(nifti_file, atlas, json_file=None):
    """Create .annot files from a nifti file and a json file."""
    import nibabel as nb
    import numpy as np
    from neuromaps import transforms

    lh_gii, rh_gii = transforms.mni152_to_fsaverage(
        nifti_file,
        fsavg_density='164k',
        method='nearest',
    )
    colors, names = ctab_from_neuroparc_json(
        neuroparc_json_file=json_file,
        atlas_nifti_file=nifti_file,
    )
    lh_annot = f'annots/lh.{atlas}.annot'
    nb.freesurfer.write_annot(
        lh_annot,
        labels=lh_gii.agg_data().astype(np.int32),
        ctab=colors,
        names=names,
        fill_ctab=True,
    )
    rh_annot = f'annots/rh.{atlas}.annot'
    nb.freesurfer.write_annot(
        rh_annot,
        labels=rh_gii.agg_data().astype(np.int32),
        ctab=colors,
        names=names,
        fill_ctab=True,
    )
    return lh_annot, rh_annot


def select_first(inlist):
    """Select the first element of a list."""
    return inlist[0]


def select_second(inlist):
    """Select the second element of a list."""
    return inlist[1]


def init_load_atlases_wf(name='load_atlases_wf'):
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
    from smripost_linc.interfaces.bids import DerivativesDataSink
    from smripost_linc.utils.bids import collect_atlases
    from smripost_linc.utils.boilerplate import describe_atlases
    from smripost_linc.utils.parcellation import gifti_to_annot

    workflow = Workflow(name=name)
    output_dir = config.execution.output_dir

    atlases = collect_atlases(
        datasets=config.execution.datasets,
        atlases=config.execution.atlases,
        bids_filters=config.execution.bids_filters,
    )

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
                'bold_file',
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
                'atlas_files',
                'atlas_labels_files',
            ],
        ),
        name='outputnode',
    )
    workflow.connect([(inputnode, outputnode, [('atlas_names', 'atlas_names')])])

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
            ...
        else:
            # Convert NIfTI to GIFTI
            ...

        for hemi in ['L', 'R']:
            annot_node = lh_annots if hemi == 'L' else rh_annots
            selecter = select_first if hemi == 'L' else select_second
            # Identify space and file-type of the atlas
            if info['space'] == 'MNI152NLin6Asym' and info['format'] == 'nifti':
                # Convert MNI152NLin6Asym to annot
                create_annot = pe.Node(
                    niu.Function(
                        function=create_annots,
                    ),
                    name=f'create_annot_{atlas}',
                )
                create_annot.inputs.atlas = atlas

                # Warp fsaverage-annot to fsnative-annot
                ...

            elif info['format'] == 'nifti':
                raise NotImplementedError('Only MNI152NLin6Asym NIfTI atlases are supported.')

            elif info['space'] == 'fsLR':
                # Warp atlas from fsLR to fsaverage
                warp_fslr_to_fsaverage = pe.Node(
                    niu.Function(
                        function=fslr_to_fsaverage,
                    ),
                    name=f'warp_fslr_to_fsaverage_{atlas}',
                )
                warp_fslr_to_fsaverage.inputs.target_density = '164k'
                warp_fslr_to_fsaverage.inputs.hemi = hemi
                warp_fslr_to_fsaverage.inputs.method = 'nearest'
                workflow.connect([
                    (gifti_buffer, warp_fslr_to_fsaverage, [(f'{hemi.lower()}_gifti', 'in_file')]),
                ])  # fmt:skip

                # Convert fsaverage to annot
                ...

                # Warp fsaverage-annot to fsnative-annot
                ...

            elif info['space'] == 'fsaverage':
                # Convert fsaverage to annot
                create_annot = pe.Node(
                    niu.Function(
                        function=create_annots,
                    ),
                    name=f'create_annot_{atlas}',
                )
                create_annot.inputs.atlas = atlas

                # Warp fsaverage-annot to fsnative-annot
                ...

                # Write out fsnative-annot files
                workflow.connect([
                    (create_annot, annot_node, [(('annot', selecter), f'in{i_atlas + 1}')]),
                ])  # fmt:skip

            elif info['space'] == 'fsnative' and info['format'] == 'annot':
                # Write out fsnative-annot files
                workflow.connect([
                    (inputnode, annot_node, [(('atlas_file', selecter), f'in{i_atlas + 1}')]),
                ])  # fmt:skip

            if info['format'] != 'annot':
                convert_gifti_to_annot = pe.Node(
                    niu.Function(
                        function=gifti_to_annot,
                    ),
                    name=f'convert_gifti_to_annot_{atlas}_{hemi}',
                )

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

    copy_atlas = pe.MapNode(
        DerivativesDataSink(),
        name='copy_atlas',
        iterfield=['in_file', 'atlas', 'meta_dict', 'Sources'],
        run_without_submitting=True,
    )
    workflow.connect([
        (inputnode, copy_atlas, [
            ('name_source', 'name_source'),
            ('atlas_names', 'atlas'),
            ('atlas_files', 'in_file'),
            ('atlas_metadata', 'meta_dict'),
        ]),
        (atlas_srcs, copy_atlas, [('out', 'Sources')]),
        (copy_atlas, outputnode, [('out_file', 'atlas_files')]),
    ])  # fmt:skip

    copy_atlas_labels_file = pe.MapNode(
        DerivativesDataSink(),
        name='copy_atlas_labels_file',
        iterfield=['in_file', 'atlas'],
        run_without_submitting=True,
    )
    workflow.connect([
        (inputnode, copy_atlas_labels_file, [
            ('name_source', 'name_source'),
            ('atlas_names', 'atlas'),
            ('atlas_labels_files', 'in_file'),
        ]),
        (copy_atlas_labels_file, outputnode, [('out_file', 'atlas_labels_files')]),
    ])  # fmt:skip

    return workflow


def init_parcellate_fsaverage_wf(
    mem_gb,
    compute_mask=True,
    name='parcellate_fsaverage_wf',
):
    """Parcellate stuff.

    Part of the parcellation includes applying vertex-wise and node-wise masks.

    Vertex-wise masks are typically calculated from the full BOLD run,
    wherein any vertex that has a time series of all zeros or NaNs is excluded.
    Additionally, if *any* volumes in a vertex's time series are NaNs,
    that vertex will be excluded.

    The node-wise mask is determined based on the vertex-wise mask and the workflow's
    coverage threshold.
    Any nodes in the atlas with less than the coverage threshold's % of vertices retained by the
    vertex-wise mask will have that node's time series set to NaNs.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from xcp_d.tests.tests import mock_config
            from xcp_d import config
            from xcp_d.workflows.connectivity import init_parcellate_cifti_wf

            with mock_config():
                wf = init_parcellate_cifti_wf(mem_gb={'resampled': 2})

    Parameters
    ----------
    mem_gb : :obj:`dict`
        Dictionary of memory allocations.
    compute_mask : :obj:`bool`
        Whether to compute a vertex-wise mask for the CIFTI file.
        When processing full BOLD runs, this should be True.
        When processing truncated BOLD runs or scalar maps, this should be False,
        and the vertex-wise mask should be provided via the inputnode..
        Default is True.
    name : :obj:`str`
        Workflow name.
        Default is 'parcellate_cifti_wf'.

    Inputs
    ------
    in_file
        CIFTI file to parcellate.
    atlas_files
        List of CIFTI atlas files.
    atlas_labels_files
        List of TSV atlas labels files.
    vertexwise_coverage
        Vertex-wise coverage mask.
        Only used if `compute_mask` is False.
    coverage_cifti
        Coverage CIFTI files. One for each atlas.
        Only used if `compute_mask` is False.

    Outputs
    -------
    parcellated_cifti
        Parcellated CIFTI files. One for each atlas.
    parcellated_tsv
        Parcellated TSV files. One for each atlas.
    vertexwise_coverage
        Vertex-wise coverage mask. Only output if `compute_mask` is True.
    coverage_cifti
        Coverage CIFTI files. One for each atlas. Only output if `compute_mask` is True.
    coverage_tsv
        Coverage TSV files. One for each atlas. Only output if `compute_mask` is True.
    """
    from xcp_d import config
    from xcp_d.interfaces.connectivity import CiftiMask, CiftiToTSV, CiftiVertexMask
    from xcp_d.interfaces.workbench import CiftiMath, CiftiParcellateWorkbench

    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'in_file',
                'atlas_files',
                'atlas_labels_files',
                'vertexwise_coverage',
                'coverage_cifti',
            ],
        ),
        name='inputnode',
    )

    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'parcellated_cifti',
                'parcellated_tsv',
                'vertexwise_coverage',
                'coverage_cifti',
                'coverage_tsv',
            ],
        ),
        name='outputnode',
    )

    # Replace vertices with all zeros with NaNs using Python.
    coverage_buffer = pe.Node(
        niu.IdentityInterface(fields=['vertexwise_coverage', 'coverage_cifti']),
        name='coverage_buffer',
    )
    if compute_mask:
        # Write out a vertex-wise binary coverage map using Python.
        vertexwise_coverage = pe.Node(
            CiftiVertexMask(),
            name='vertexwise_coverage',
        )
        workflow.connect([
            (inputnode, vertexwise_coverage, [('in_file', 'in_file')]),
            (vertexwise_coverage, coverage_buffer, [('mask_file', 'vertexwise_coverage')]),
            (vertexwise_coverage, outputnode, [('mask_file', 'vertexwise_coverage')]),
        ])  # fmt:skip

        parcellate_coverage = pe.MapNode(
            CiftiParcellateWorkbench(
                direction='COLUMN',
                only_numeric=True,
                out_file='parcellated_atlas.pscalar.nii',
                num_threads=config.nipype.omp_nthreads,
            ),
            name='parcellate_coverage',
            iterfield=['atlas_label'],
            n_procs=config.nipype.omp_nthreads,
        )
        workflow.connect([
            (inputnode, parcellate_coverage, [('atlas_files', 'atlas_label')]),
            (vertexwise_coverage, parcellate_coverage, [('mask_file', 'in_file')]),
            (parcellate_coverage, coverage_buffer, [('out_file', 'coverage_cifti')]),
            (parcellate_coverage, outputnode, [('out_file', 'coverage_cifti')]),
        ])  # fmt:skip

        coverage_to_tsv = pe.MapNode(
            CiftiToTSV(),
            name='coverage_to_tsv',
            iterfield=['in_file', 'atlas_labels'],
        )
        workflow.connect([
            (inputnode, coverage_to_tsv, [('atlas_labels_files', 'atlas_labels')]),
            (parcellate_coverage, coverage_to_tsv, [('out_file', 'in_file')]),
            (coverage_to_tsv, outputnode, [('out_file', 'coverage_tsv')]),
        ])  # fmt:skip
    else:
        workflow.connect([
            (inputnode, coverage_buffer, [
                ('vertexwise_coverage', 'vertexwise_coverage'),
                ('coverage_cifti', 'coverage_cifti'),
            ]),
        ])  # fmt:skip

    # Parcellate the data file using the vertex-wise coverage.
    parcellate_data = pe.MapNode(
        CiftiParcellateWorkbench(
            direction='COLUMN',
            only_numeric=True,
            out_file=f'parcellated_data.{"ptseries" if compute_mask else "pscalar"}.nii',
            num_threads=config.nipype.omp_nthreads,
        ),
        name='parcellate_data',
        iterfield=['atlas_label'],
        mem_gb=mem_gb['resampled'],
        n_procs=config.nipype.omp_nthreads,
    )
    workflow.connect([
        (inputnode, parcellate_data, [
            ('in_file', 'in_file'),
            ('atlas_files', 'atlas_label'),
        ]),
        (coverage_buffer, parcellate_data, [('vertexwise_coverage', 'cifti_weights')]),
    ])  # fmt:skip

    # Threshold node coverage values based on coverage threshold.
    threshold_coverage = pe.MapNode(
        CiftiMath(
            expression=f'data > {config.workflow.min_coverage}',
            num_threads=config.nipype.omp_nthreads,
        ),
        name='threshold_coverage',
        iterfield=['data'],
        mem_gb=mem_gb['resampled'],
        n_procs=config.nipype.omp_nthreads,
    )
    workflow.connect([(coverage_buffer, threshold_coverage, [('coverage_cifti', 'data')])])

    # Mask out uncovered nodes from parcellated denoised data
    mask_parcellated_data = pe.MapNode(
        CiftiMask(),
        name='mask_parcellated_data',
        iterfield=['in_file', 'mask'],
        mem_gb=mem_gb['resampled'],
    )
    workflow.connect([
        (parcellate_data, mask_parcellated_data, [('out_file', 'in_file')]),
        (threshold_coverage, mask_parcellated_data, [('out_file', 'mask')]),
        (mask_parcellated_data, outputnode, [('out_file', 'parcellated_cifti')]),
    ])  # fmt:skip

    # Convert the parcellated CIFTI to a TSV file
    cifti_to_tsv = pe.MapNode(
        CiftiToTSV(),
        name='cifti_to_tsv',
        iterfield=['in_file', 'atlas_labels'],
    )
    workflow.connect([
        (inputnode, cifti_to_tsv, [('atlas_labels_files', 'atlas_labels')]),
        (mask_parcellated_data, cifti_to_tsv, [('out_file', 'in_file')]),
        (cifti_to_tsv, outputnode, [('out_file', 'parcellated_tsv')]),
    ])  # fmt:skip

    return workflow
