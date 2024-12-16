# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
#
# Copyright 2023 The NiPreps Developers <pennlinc@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# We support and encourage derived works from this project, please read
# about our expectations at
#
#     https://www.pennlinc.org/community/licensing/
#
"""
sMRIPost-LINC workflows
^^^^^^^^^^^^^^^^^^^^^^^

.. autofunction:: init_smripost_linc_wf
.. autofunction:: init_single_subject_wf
.. autofunction:: init_single_run_wf

"""

import os
import sys
from collections import defaultdict
from copy import deepcopy

import yaml
from nipype.pipeline import engine as pe
from packaging.version import Version

from smripost_linc import config
from smripost_linc.utils.utils import _get_wf_name, update_dict


def init_smripost_linc_wf():
    """Build *sMRIPost-LINC*'s pipeline.

    This workflow organizes the execution of sMRIPost-LINC,
    with a sub-workflow for each subject.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from smripost_linc.workflows.tests import mock_config
            from smripost_linc.workflows.base import init_smripost_linc_wf

            with mock_config():
                wf = init_smripost_linc_wf()

    """
    from niworkflows.engine.workflows import LiterateWorkflow as Workflow

    from smripost_linc.utils.bids import collect_atlases
    from smripost_linc.workflows.parcellation import init_load_atlases_wf

    ver = Version(config.environment.version)

    smripost_linc_wf = Workflow(name=f'smripost_linc_{ver.major}_{ver.minor}_wf')
    smripost_linc_wf.base_dir = config.execution.work_dir

    atlases = collect_atlases(
        datasets=config.execution.datasets,
        atlases=config.execution.atlases,
        bids_filters=config.execution.bids_filters,
    )

    load_atlases_wf = init_load_atlases_wf(atlases=atlases)

    for subject_id in config.execution.participant_label:
        single_subject_wf = init_single_subject_wf(subject_id, atlases=atlases)

        single_subject_wf.config['execution']['crashdump_dir'] = str(
            config.execution.output_dir / f'sub-{subject_id}' / 'log' / config.execution.run_uuid
        )
        for node in single_subject_wf._get_all_nodes():
            node.config = deepcopy(single_subject_wf.config)

        smripost_linc_wf.connect([
            (load_atlases_wf, single_subject_wf, [
                ('outputnode.atlas_names', 'inputnode.atlas_names'),
                ('outputnode.lh_fsaverage_annots', 'inputnode.lh_fsaverage_annots'),
                ('outputnode.rh_fsaverage_annots', 'inputnode.rh_fsaverage_annots'),
                ('outputnode.atlas_labels_files', 'inputnode.atlas_labels_files'),
            ]),
        ])  # fmt:skip

        # Dump a copy of the config file into the log directory
        log_dir = (
            config.execution.output_dir / f'sub-{subject_id}' / 'log' / config.execution.run_uuid
        )
        log_dir.mkdir(exist_ok=True, parents=True)
        config.to_filename(log_dir / 'smripost_linc.toml')

    return smripost_linc_wf


def init_single_subject_wf(subject_id: str, atlases: list):
    """Organize the postprocessing pipeline for a single subject.

    It collects and reports information about the subject,
    and prepares sub-workflows to postprocess each BOLD series.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from smripost_linc.workflows.tests import mock_config
            from smripost_linc.workflows.base import init_single_subject_wf

            with mock_config():
                wf = init_single_subject_wf('01')

    Parameters
    ----------
    subject_id : :obj:`str`
        Subject label for this single-subject workflow.

    Notes
    -----
    1.  Load sMRIPost-LINC config file.
    2.  Collect sMRIPrep and Freesurfer derivatives.
    3.  Warp/convert atlases to fsnative-space annot files.
    4.  Use mri_anatomical_stats to extract brain tissue volumes for each of the atlases.
    5.  Extract Euler number from recon-all.log.
    """
    from bids.utils import listify
    from nipype.interfaces import utility as niu
    from niworkflows.engine.workflows import LiterateWorkflow as Workflow
    from niworkflows.interfaces.bids import BIDSInfo
    from niworkflows.interfaces.nilearn import NILEARN_VERSION

    from smripost_linc.interfaces.bids import DerivativesDataSink
    from smripost_linc.interfaces.reportlets import AboutSummary, SubjectSummary
    from smripost_linc.utils.bids import collect_derivatives

    spaces = config.workflow.spaces

    workflow = Workflow(name=f'sub_{subject_id}_wf')
    workflow.__desc__ = f"""
Results included in this manuscript come from postprocessing
performed using *sMRIPost-LINC* {config.environment.version},
which is based on *Nipype* {config.environment.nipype_version}
(@nipype1; @nipype2; RRID:SCR_002502).

"""
    workflow.__postdesc__ = f"""

Many internal operations of *sMRIPost-LINC* use
*Nilearn* {NILEARN_VERSION} [@nilearn, RRID:SCR_001362].
For more details of the pipeline, see [the section corresponding
to workflows in *sMRIPost-LINC*'s documentation]\
(https://smripost_linc.readthedocs.io/en/latest/workflows.html \
"FMRIPrep's documentation").


### Copyright Waiver

The above boilerplate text was automatically generated by sMRIPost-LINC
with the express intention that users should copy and paste this
text into their manuscripts *unchanged*.
It is released under the [CC0]\
(https://creativecommons.org/publicdomain/zero/1.0/) license.

### References

"""
    entities = config.execution.bids_filters or {}
    entities['subject'] = subject_id

    subject_data = collect_derivatives(
        derivatives_dataset=config.execution.layout,
        entities=entities,
        fieldmap_id=None,
        allow_multiple=True,
        spaces=None,
    )
    subject_data['anat'] = None
    if subject_data['t1w']:
        subject_data['anat'] = listify(subject_data['t1w'])
    elif subject_data['t2w']:
        subject_data['anat'] = listify(subject_data['t2w'])

    # Make sure we always check that we have an anatomical image
    if not subject_data['anat']:
        raise RuntimeError(
            f'No anatomical images found for participant {subject_id}. '
            'All workflows require anatomical images. '
            f'Please check your BIDS filters: {config.execution.bids_filters}.'
        )

    config.loggers.workflow.info(
        f'Collected subject data:\n{yaml.dump(subject_data, default_flow_style=False, indent=4)}',
    )

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'atlas_names',
                'lh_fsaverage_annots',
                'rh_fsaverage_annots',
                'atlas_labels_files',
            ],
        ),
        name='inputnode',
        run_without_submitting=True,
    )

    bids_info = pe.Node(
        BIDSInfo(
            bids_dir=config.execution.bids_dir,
            bids_validate=False,
            in_file=subject_data['bold'][0],
        ),
        name='bids_info',
    )

    summary = pe.Node(
        SubjectSummary(
            bold=subject_data['bold'],
            std_spaces=spaces.get_spaces(nonstandard=False),
            nstd_spaces=spaces.get_spaces(standard=False),
        ),
        name='summary',
        run_without_submitting=True,
    )
    workflow.connect([(bids_info, summary, [('subject', 'subject_id')])])

    about = pe.Node(
        AboutSummary(version=config.environment.version, command=' '.join(sys.argv)),
        name='about',
        run_without_submitting=True,
    )

    ds_report_summary = pe.Node(
        DerivativesDataSink(
            source_file=subject_data['bold'][0],
            base_directory=config.execution.output_dir,
            desc='summary',
            datatype='figures',
        ),
        name='ds_report_summary',
        run_without_submitting=True,
    )
    workflow.connect([(summary, ds_report_summary, [('out_report', 'in_file')])])

    ds_report_about = pe.Node(
        DerivativesDataSink(
            source_file=subject_data['bold'][0],
            base_directory=config.execution.output_dir,
            desc='about',
            datatype='figures',
        ),
        name='ds_report_about',
        run_without_submitting=True,
    )
    workflow.connect([(about, ds_report_about, [('out_report', 'in_file')])])

    for anat_file in subject_data['anat']:
        single_run_wf = init_single_run_wf(anat_file=anat_file, atlases=atlases)
        workflow.connect([
            (inputnode, single_run_wf, [
                ('lh_fsaverage_annots', 'inputnode.lh_fsaverage_annots'),
                ('rh_fsaverage_annots', 'inputnode.rh_fsaverage_annots'),
                ('atlas_metadata', 'inputnode.atlas_metadata'),
            ]),
        ])  # fmt:skip

    return clean_datasinks(workflow)


def init_single_run_wf(anat_file, atlases):
    """Set up a single-run workflow for sMRIPost-LINC.

    This workflow organizes the postprocessing pipeline for a single
    preprocessed anatomical image.
    """
    from fmriprep.utils.misc import estimate_bold_mem_usage
    from nipype.interfaces import utility as niu
    from nipype.pipeline import engine as pe
    from niworkflows.engine.workflows import LiterateWorkflow as Workflow

    from smripost_linc.utils.bids import collect_derivatives, extract_entities
    from smripost_linc.utils.freesurfer import find_fs_path
    from smripost_linc.workflows.freesurfer import (
        init_convert_metrics_to_cifti_wf,
        init_parcellate_external_wf,
    )
    from smripost_linc.workflows.parcellation import init_warp_atlases_to_fsnative_wf

    spaces = config.workflow.spaces

    workflow = Workflow(name=_get_wf_name(anat_file, 'single_run'))
    workflow.__desc__ = ''

    mem_gb = estimate_bold_mem_usage(anat_file)[1]

    entities = extract_entities(anat_file)

    # Collect the segmentation results
    # Look for Freesurfer folder
    anat_fs_dir = find_fs_path(
        config.execution.fs_subjects_dir,
        entities['subject'],
        session_id=entities.get('session'),
    )
    if anat_fs_dir is None:
        raise RuntimeError(
            f'No FreeSurfer folder found for participant {entities["subject"]}. '
            'All workflows require FreeSurfer output. '
            'Please check your FreeSurfer subjects directory: '
            f'{config.execution.fs_subjects_dir}.'
        )

    # XXX: Then MCRIBS? Then Infant-FS?

    anatomical_cache = defaultdict(list, {})
    if config.execution.datasets:
        # Collect native-space derivatives and transforms
        anatomical_cache = collect_derivatives(
            raw_dataset=config.execution.layout,
            derivatives_dataset=None,
            entities=entities,
            allow_multiple=False,
            spaces=None,
        )
        for deriv_dir in config.execution.datasets.values():
            anatomical_cache = update_dict(
                anatomical_cache,
                collect_derivatives(
                    raw_dataset=None,
                    derivatives_dataset=deriv_dir,
                    entities=entities,
                    allow_multiple=False,
                    spaces=spaces,
                ),
            )

    else:
        # Collect MNI152NLin6Asym:res-2 derivatives
        # Only derivatives dataset was passed in, so we expected standard-space derivatives
        anatomical_cache.update(
            collect_derivatives(
                raw_dataset=None,
                derivatives_dataset=config.execution.layout,
                entities=entities,
                allow_multiple=False,
                spaces=spaces,
            ),
        )

    config.loggers.workflow.info(
        (
            f'Collected preprocessing derivatives for {os.path.basename(anat_file)}:\n'
            f'{yaml.dump(anatomical_cache, default_flow_style=False, indent=4)}'
        ),
    )

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'lh_fsaverage_annots',
                'rh_fsaverage_annots',
                'atlas_metadata',
            ],
        ),
        name='inputnode',
        run_without_submitting=True,
    )

    # Run single-run processing
    warp_atlases_to_fsnative_wf = init_warp_atlases_to_fsnative_wf(
        anat_file=anat_file,
        atlases=atlases,
        mem_gb=mem_gb,
    )
    warp_atlases_to_fsnative_wf.inputs.inputnode.freesurfer_dir = anat_fs_dir
    workflow.connect([
        (inputnode, warp_atlases_to_fsnative_wf, [
            ('lh_fsaverage_annots', 'inputnode.lh_fsaverage_annots'),
            ('rh_fsaverage_annots', 'inputnode.rh_fsaverage_annots'),
            ('atlas_metadata', 'inputnode.atlas_metadata'),
        ]),
    ])  # fmt:skip

    parcellate_external_wf = init_parcellate_external_wf(
        atlases=atlases,
        mem_gb={'resampled': 2},
    )
    parcellate_external_wf.inputs.inputnode.freesurfer_dir = anat_fs_dir
    workflow.connect([
        (warp_atlases_to_fsnative_wf, parcellate_external_wf, [
            ('outputnode.lh_fsnative_annots', 'inputnode.lh_fsnative_annots'),
            ('outputnode.rh_fsnative_annots', 'inputnode.rh_fsnative_annots'),
        ]),
    ])  # fmt:skip

    # TODO: Calculate myelin map if both T1w and T2w are available

    # Warp GIFTIs to fsLR CIFTIs
    convert_metrics_to_cifti_wf = init_convert_metrics_to_cifti_wf()
    convert_metrics_to_cifti_wf.inputs.inputnode.freesurfer_dir = anat_fs_dir
    workflow.add_nodes([convert_metrics_to_cifti_wf])

    # Fill-in datasinks seen so far
    for node in workflow.list_node_names():
        node_name = node.split('.')[-1]
        if node_name.startswith('ds_'):
            workflow.get_node(node).inputs.base_directory = config.execution.output_dir

            if not node_name.startswith('ds_atlas_'):
                workflow.get_node(node).inputs.source_file = anat_file

    return workflow


def clean_datasinks(workflow: pe.Workflow) -> pe.Workflow:
    """Overwrite ``out_path_base`` of smriprep's DataSinks."""
    for node in workflow.list_node_names():
        if node.split('.')[-1].startswith('ds_'):
            workflow.get_node(node).interface.out_path_base = ''
    return workflow
