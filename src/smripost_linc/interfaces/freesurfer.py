"""Interfaces for working with FreeSurfer."""

from nipype.interfaces.base import (
    Directory,
    DynamicTraitedSpec,
    File,
    SimpleInterface,
    TraitedSpec,
    traits,
)


class _FreesurferFilesInputSpec(DynamicTraitedSpec):
    freesurfer_dir = Directory(
        exists=True,
        mandatory=True,
        desc="Directory containing anatomical file's FreeSurfer outputs",
    )


class _FreesurferFilesOutputSpec(TraitedSpec):
    files = traits.List(
        File(exists=True),
        desc='FreeSurfer files to parcellate',
    )
    names = traits.List(
        traits.Str,
        desc='Names of FreeSurfer files to parcellate',
    )


class FreesurferFiles(SimpleInterface):
    """Collect FreeSurfer files to parcellate."""

    input_spec = _FreesurferFilesInputSpec
    output_spec = _FreesurferFilesOutputSpec

    def _run_interface(self, runtime):
        ...

        return runtime


class _FreesurferAnnotsInputSpec(DynamicTraitedSpec):
    freesurfer_dir = Directory(
        exists=True,
        mandatory=True,
        desc="Directory containing anatomical file's FreeSurfer outputs",
    )


class _FreesurferAnnotsOutputSpec(TraitedSpec):
    files = traits.List(
        File(exists=True),
        desc='FreeSurfer files to parcellate',
    )
    names = traits.List(
        traits.Str,
        desc='Names of FreeSurfer files to parcellate',
    )


class FreesurferAnnots(SimpleInterface):
    """Collect FreeSurfer annot files in fsaverage space."""

    input_spec = _FreesurferAnnotsInputSpec
    output_spec = _FreesurferAnnotsOutputSpec

    def _run_interface(self, runtime):
        ...

        return runtime
