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

    ver = Version(config.environment.version)

    smripost_linc_wf = Workflow(name=f'smripost_linc_{ver.major}_{ver.minor}_wf')
    smripost_linc_wf.base_dir = config.execution.work_dir

    for subject_id in config.execution.participant_label:
        single_subject_wf = init_single_subject_wf(subject_id)

        single_subject_wf.config['execution']['crashdump_dir'] = str(
            config.execution.output_dir / f'sub-{subject_id}' / 'log' / config.execution.run_uuid
        )
        for node in single_subject_wf._get_all_nodes():
            node.config = deepcopy(single_subject_wf.config)

        smripost_linc_wf.add_nodes([single_subject_wf])

        # Dump a copy of the config file into the log directory
        log_dir = (
            config.execution.output_dir / f'sub-{subject_id}' / 'log' / config.execution.run_uuid
        )
        log_dir.mkdir(exist_ok=True, parents=True)
        config.to_filename(log_dir / 'smripost_linc.toml')

    return smripost_linc_wf


def init_single_subject_wf(subject_id: str):
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
performed using *sMRIPost-LINC* {config.environment.version} (@ica_aroma),
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

    if config.execution.datasets:
        # Raw dataset + derivatives dataset
        config.loggers.workflow.info('Raw+derivatives workflow mode enabled')
        # Just build a list of anatomical files right now
        subject_data = collect_derivatives(
            raw_dataset=config.execution.layout,
            derivatives_dataset=None,
            entities=entities,
            fieldmap_id=None,
            allow_multiple=True,
            spaces=None,
        )
        subject_data['bold'] = listify(subject_data['bold_raw'])
    else:
        # Derivatives dataset only
        config.loggers.workflow.info('Derivatives-only workflow mode enabled')
        # Just build a list of BOLD files right now
        subject_data = collect_derivatives(
            raw_dataset=None,
            derivatives_dataset=config.execution.layout,
            entities=entities,
            fieldmap_id=None,
            allow_multiple=True,
            spaces=None,
        )
        # Patch standard-space BOLD files into 'bold' key
        subject_data['bold'] = listify(subject_data['bold_mni152nlin6asym'])

    # Make sure we always go through these two checks
    if not subject_data['bold']:
        task_id = config.execution.task_id
        raise RuntimeError(
            f"No BOLD images found for participant {subject_id} and "
            f"task {task_id if task_id else '<all>'}. "
            "All workflows require BOLD images. "
            f"Please check your BIDS filters: {config.execution.bids_filters}."
        )

    config.loggers.workflow.info(
        f'Collected subject data:\n{yaml.dump(subject_data, default_flow_style=False, indent=4)}',
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

    # Append the functional section to the existing anatomical excerpt
    # That way we do not need to stream down the number of bold datasets
    func_pre_desc = f"""
Functional data postprocessing

: For each of the {len(subject_data['bold'])} BOLD runs found per subject
(across all tasks and sessions), the following postprocessing was performed.
"""
    workflow.__desc__ += func_pre_desc

    for anat_file in subject_data['bold']:
        single_run_wf = init_single_run_wf(anat_file)
        workflow.add_nodes([single_run_wf])

    return clean_datasinks(workflow)


def init_single_run_wf(anat_file):
    """Set up a single-run workflow for sMRIPost-LINC."""
    from fmriprep.utils.misc import estimate_bold_mem_usage
    from niworkflows.engine.workflows import LiterateWorkflow as Workflow

    from smripost_linc.utils.bids import collect_derivatives, extract_entities
    from smripost_linc.workflows.freesurfer import init_postprocess_freesurfer_wf
    from smripost_linc.workflows.outputs import init_anat_fit_reports_wf

    spaces = config.workflow.spaces

    workflow = Workflow(name=_get_wf_name(anat_file, 'single_run'))
    workflow.__desc__ = ''

    anat_metadata = config.execution.layout.get_metadata(anat_file)
    mem_gb = estimate_bold_mem_usage(anat_file)[1]

    entities = extract_entities(anat_file)

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
            f'Collected run data for {os.path.basename(anat_file)}:\n'
            f'{yaml.dump(anatomical_cache, default_flow_style=False, indent=4)}'
        ),
    )

    # Run single-run processing
    postprocess_freesurfer_wf = init_postprocess_freesurfer_wf(
        anat_file=anat_file, metadata=anat_metadata, mem_gb=mem_gb
    )

    # Generate reportlets
    anat_fit_reports_wf = init_anat_fit_reports_wf(output_dir=config.execution.output_dir)
    anat_fit_reports_wf.inputs.inputnode.source_file = anat_file
    anat_fit_reports_wf.inputs.inputnode.anat2std_xfm = anatomical_cache['anat2mni152nlin6asym']
    anat_fit_reports_wf.inputs.inputnode.anat_dseg = anatomical_cache['anat_dseg']

    # Fill-in datasinks seen so far
    for node in workflow.list_node_names():
        if node.split('.')[-1].startswith('ds_'):
            workflow.get_node(node).inputs.base_directory = config.execution.output_dir
            workflow.get_node(node).inputs.source_file = anat_file

    return workflow


def _prefix(subid):
    return subid if subid.startswith('sub-') else f'sub-{subid}'


def clean_datasinks(workflow: pe.Workflow) -> pe.Workflow:
    """Overwrite ``out_path_base`` of smriprep's DataSinks."""
    for node in workflow.list_node_names():
        if node.split('.')[-1].startswith('ds_'):
            workflow.get_node(node).interface.out_path_base = ''
    return workflow


def get_nss(confounds_file):
    """Get number of non-steady state volumes."""
    import numpy as np
    import pandas as pd

    df = pd.read_table(confounds_file)

    nss_cols = [c for c in df.columns if c.startswith('non_steady_state_outlier')]

    dummy_scans = 0
    if nss_cols:
        initial_volumes_df = df[nss_cols]
        dummy_scans = np.any(initial_volumes_df.to_numpy(), axis=1)
        dummy_scans = np.where(dummy_scans)[0]

        # reasonably assumes all NSS volumes are contiguous
        dummy_scans = int(dummy_scans[-1] + 1)

    return dummy_scans
