"""Tests for smripost_linc.workflows."""

from fmriprep.workflows.tests import mock_config

from smripost_linc import config


def test_init_ica_aroma_wf(tmp_path_factory):
    from smripost_linc.workflows.aroma import init_ica_aroma_wf

    tempdir = tmp_path_factory.mktemp('test_init_ica_aroma_wf')

    with mock_config():
        config.execution.output_dir = tempdir / 'out'
        config.execution.work_dir = tempdir / 'work'
        config.workflow.denoise_method = ['nonaggr', 'orthaggr']
        config.workflow.melodic_dim = -200
        config.workflow.err_on_warn = False

        wf = init_ica_aroma_wf(
            bold_file='sub-01_task-rest_bold.nii.gz',
            metadata={'RepetitionTime': 2.0},
            mem_gb={'resampled': 1},
        )
        assert wf.name == 'aroma_task_rest_wf'


def test_init_denoise_wf(tmp_path_factory):
    from smripost_linc.workflows.aroma import init_denoise_wf

    tempdir = tmp_path_factory.mktemp('test_init_denoise_wf')

    with mock_config():
        config.execution.output_dir = tempdir / 'out'
        config.execution.work_dir = tempdir / 'work'

        wf = init_denoise_wf(
            bold_file='sub-01_task-rest_bold.nii.gz',
            metadata={'RepetitionTime': 2.0},
        )
        assert wf.name == 'denoise_task_rest_wf'
