# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Workflows for working with FreeSurfer derivatives."""

from nipype.interfaces import freesurfer as fs
from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe
from niworkflows.engine.workflows import LiterateWorkflow as Workflow

from smripost_linc.interfaces.bids import DerivativesDataSink
from smripost_linc.interfaces.freesurfer import ParcellationStats


def init_parcellate_external_wf(
    name_source,
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
    from smripost_linc.interfaces.freesurfer import CopyAnnots, FreesurferFiles
    from smripost_linc.interfaces.misc import ParcellationStats2TSV

    print(mem_gb)

    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'subject_id',
                'freesurfer_dir',
                'atlases',
                'lh_fsnative_annots',
                'rh_fsnative_annots',
            ],
        ),
        name='inputnode',
    )

    # TODO: Ensure fsaverage is copied over as well.
    copy_freesurfer_files = pe.Node(
        niu.Function(
            input_names=['freesurfer_dir', 'output_dir'],
            output_names=['output_dir', 'subject_id'],
            function=symlink_freesurfer_dir,
        ),
        name='copy_freesurfer_files',
    )
    workflow.connect([(inputnode, copy_freesurfer_files, [('freesurfer_dir', 'freesurfer_dir')])])

    for hemi in ['lh', 'rh']:
        # Select Freesurfer files to parcellate (GWR and LGI)
        fs_files = pe.Node(FreesurferFiles(hemi=hemi), name=f'fs_files_{hemi}')
        workflow.connect([(inputnode, fs_files, [('freesurfer_dir', 'freesurfer_dir')])])

        # Copy the fsnative annot files to the freesurfer directory
        copy_annots = pe.MapNode(
            CopyAnnots(hemisphere=hemi),
            name=f'copy_annots_{hemi}',
            iterfield=['in_file', 'atlas'],
        )
        workflow.connect([
            (inputnode, copy_annots, [
                (f'{hemi}_fsnative_annots', 'in_file'),
                ('atlases', 'atlas'),
            ]),
            (copy_freesurfer_files, copy_annots, [
                ('output_dir', 'freesurfer_dir'),
                ('subject_id', 'subject_id'),
            ]),
        ])  # fmt:skip

        # Parcellate each data file with each atlas in each hemisphere
        for atlas in atlases:
            prepare_segstats_arg = pe.Node(
                niu.Merge(3),
                name=f'prepare_segstats_arg_{hemi}_{atlas}',
            )
            prepare_segstats_arg.inputs.in2 = hemi
            prepare_segstats_arg.inputs.in3 = atlas
            workflow.connect([
                (copy_freesurfer_files, prepare_segstats_arg, [('subject_id', 'in1')]),
            ])  # fmt:skip

            mri_segstats = pe.MapNode(
                fs.SegStats(),
                name=f'mri_segstats_{hemi}_{atlas}',
                iterfield=['in_file', 'slabel', 'args'],
            )
            workflow.connect([
                (fs_files, mri_segstats, [
                    ('files', 'in_file'),
                    ('names', 'slabel'),
                    ('arguments', 'args'),
                ]),
                (copy_freesurfer_files, mri_segstats, [('output_dir', 'subjects_dir')]),
                (prepare_segstats_arg, mri_segstats, [('out', 'annot')]),
            ])  # fmt:skip

            # Convert parcellated data to TSV
            segstats_to_tsv = pe.MapNode(
                ParcellationStats2TSV(
                    hemi=hemi,
                    atlas=atlas,
                ),
                name=f'segstats_to_tsv_{hemi}_{atlas}',
                iterfield=['in_file'],
            )
            workflow.connect([(mri_segstats, segstats_to_tsv, [('summary_file', 'in_file')])])

            # Write out parcellated data
            ds_segstats_tsv = pe.MapNode(
                DerivativesDataSink(
                    source_file=name_source,
                    space='fsnative',
                    segmentation=atlas,
                    hemi=hemi,
                    suffix='morph',
                    extension='.tsv',
                ),
                name=f'ds_segstats_tsv_{hemi}_{atlas}',
                iterfield=['in_file', 'statistic'],
            )
            workflow.connect([
                (fs_files, ds_segstats_tsv, [('names', 'statistic')]),
                (segstats_to_tsv, ds_segstats_tsv, [('out_file', 'in_file')]),
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
                ParcellationStats2TSV(hemi=hemi, atlas=atlas),
                name=f'parcstats_to_tsv_{hemi}_{atlas}',
            )
            workflow.connect([(parcellation_stats, parcstats_to_tsv, [('out_table', 'in_file')])])

            # Write out parcellated data
            ds_parcstats_tsv = pe.Node(
                DerivativesDataSink(
                    source_file=name_source,
                    space='fsnative',
                    segmentation=atlas,
                    hemi=hemi,
                    statistic='freesurfer',
                    suffix='morph',
                    extension='.tsv',
                ),
                name=f'ds_parcstats_tsv_{hemi}_{atlas}',
            )
            workflow.connect([
                (fs_files, ds_parcstats_tsv, [('names', 'desc')]),
                (parcstats_to_tsv, ds_parcstats_tsv, [('out_file', 'in_file')]),
            ])  # fmt:skip

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


def init_convert_metrics_to_cifti_wf(name='convert_metrics_to_cifti_wf'):
    """Convert FreeSurfer metrics from MGH format to CIFTI format in fsLR space.

    This directly writes out the converted files, so it is mostly a standalone workflow.

    Parameters
    ----------
    name : :obj:`str`
        Workflow name.
        Default is 'convert_metrics_to_cifti_wf'.

    Inputs
    ------
    freesurfer_dir
        Path to the structural file's FreeSurfer directory.

    """
    from smripost_linc.interfaces.freesurfer import CollectFSAverageSurfaces
    from smripost_linc.interfaces.misc import CiftiCreateDenseScalar

    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(fields=['freesurfer_dir']),
        name='inputnode',
    )

    # Calculate local gyrification index
    # This may require MATLAB
    calculate_lgi = pe.Node(
        fs.ReconAll(directive='localGI'),
        name='calculate_lgi',
    )
    workflow.connect([
        (inputnode, calculate_lgi, [
            ('freesurfer_dir', 'subjects_dir'),
            ('subject_id', 'subject_id'),
        ]),
    ])  # fmt:skip

    # Smooth scalar maps in the recon-all directory
    qcache = pe.Node(
        fs.ReconAll(directive='qcache'),
        name='qcache',
    )
    workflow.connect([
        (inputnode, qcache, [
            ('freesurfer_dir', 'subjects_dir'),
            ('subject_id', 'subject_id'),
        ]),
    ])  # fmt:skip

    # XXX: Need to run recon-all here to get some files into mgh
    # # Run qcache on this person to get the mgh files (XXX: of what???)
    # This step smooths all of the scalar maps in the recon-all directory
    # (e.g., thickness, curvature). We just need to warp the smoothed version to fsLR CIFTIs.
    # ${singularity_cmd} recon-all -s ${subject_id} -qcache
    #
    # # Run the lGI stuff on it. NOTE: this is not done with a container
    # # because it requires matlab :(
    # # CUBIC-specific stuff needed for LGI to be run outside of a container
    # HAS_LGI=1
    #
    # set +e
    # recon-all -s ${subject_id} -localGI
    #
    # # It may fail the first time, so try running it again:
    # Failure = creates corrupted lgi file that needs to be deleted
    # if [ $? -gt 0 ]; then
    #     HAS_LGI=0
    #     find ${subject_fs} -name '*pial_lgi' -delete
    # fi
    # set -e
    #
    # # create the .stats files for each annot file
    # XXX: This is done in the parcellate_external_wf
    # # Create the tsvs for the regional stats from the parcellations
    # XXX: This is done in the parcellate_external_wf
    #
    # # Get these into MGH
    # if [ $HAS_LGI -gt 0 ]; then
    #     ${singularity_cmd} recon-all -s ${subject_id} -qcache -measure pial_lgi
    # fi

    # Convert FreeSurfer metrics to CIFTIfy
    collect_fsaverage_surfaces = pe.Node(
        CollectFSAverageSurfaces(),
        name='collect_fsaverage_surfaces',
    )
    workflow.connect([
        (inputnode, collect_fsaverage_surfaces, [('freesurfer_dir', 'freesurfer_dir')]),
    ])  # fmt:skip

    convert_gifti_to_cifti = pe.MapNode(
        CiftiCreateDenseScalar(),
        name='convert_gifti_to_cifti',
        iterfield=['lh_gifti', 'rh_gifti'],
    )

    for hemi in ['lh', 'rh']:
        convert_to_gifti = pe.MapNode(
            fs.MRIsConvert(out_datatype='gii'),
            name=f'convert_to_gifti_{hemi}',
            iterfield=['in_file'],
        )
        workflow.connect([
            (collect_fsaverage_surfaces, convert_to_gifti, [
                (f'{hemi}_fsaverage_files', 'in_file'),
            ]),
        ])  # fmt:skip

        warp_fsaverage_to_fslr = pe.MapNode(
            niu.Function(
                input_names=['in_file', 'hemi'],
                output_names=['out_file'],
                function=fsaverage_to_fslr,
            ),
            name=f'warp_fsaverage_to_fslr_{hemi}',
            iterfield=['in_file'],
        )
        warp_fsaverage_to_fslr.inputs.hemi = hemi
        workflow.connect([
            (convert_to_gifti, warp_fsaverage_to_fslr, [('converted', 'in_file')]),
            (warp_fsaverage_to_fslr, convert_gifti_to_cifti, [('out_file', f'{hemi}_gifti')]),
        ])  # fmt:skip

    ds_cifti = pe.MapNode(
        DerivativesDataSink(
            space='fsLR',
            extension='.dscalar.nii',
        ),
        name='ds_cifti',
        iterfield=['in_file', 'suffix'],
    )
    workflow.connect([
        (collect_fsaverage_surfaces, ds_cifti, [('names', 'suffix')]),
        (convert_gifti_to_cifti, ds_cifti, [('out_file', 'in_file')]),
    ])  # fmt:skip

    return workflow


def fsaverage_to_fslr(in_file, hemi):
    """Convert fsaverage-space GIFTI files to a CIFTI file in fsLR space."""
    import os

    from neuromaps import transforms

    out_file = os.path.abspath('cifti.dscalar.nii')

    fslr_gifti = transforms.fsaverage_to_fslr(
        in_file,
        target_density='164k',
        hemi=hemi[0].upper(),
        method='linear',
    )
    out_file = os.path.abspath(f'{hemi}.dscalar.nii')
    fslr_gifti.to_filename(out_file)

    return out_file
