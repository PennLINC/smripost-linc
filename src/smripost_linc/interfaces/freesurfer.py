"""Interfaces for working with FreeSurfer."""

import os
import shutil

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
    hemi = traits.Enum(
        'lh',
        'rh',
        desc='Hemisphere to parcellate',
        usedefault=True,
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
    arguments = traits.List(
        traits.Str,
        desc='Arguments for mri_segstats',
    )


class FreesurferFiles(SimpleInterface):
    """Collect FreeSurfer files to parcellate."""

    input_spec = _FreesurferFilesInputSpec
    output_spec = _FreesurferFilesOutputSpec

    def _run_interface(self, runtime):
        in_dir = self.inputs.freesurfer_dir
        gwr = os.path.join(in_dir, 'surf', f'{self.inputs.hemi}.w-g.pct.mgh')
        lgi = os.path.join(in_dir, 'surf', f'{self.inputs.hemi}.pial_lgi')
        files = []
        names = []
        arguments = []
        if os.path.exists(gwr):
            files.append(gwr)
            names.append('gwr')
            arguments.append('--snr')

        if os.path.exists(lgi):
            files.append(lgi)
            names.append('lgi')
            arguments.append('')

        self._results['files'] = files
        self._results['names'] = names

        return runtime


class _CopyAnnotsInputSpec(TraitedSpec):
    freesurfer_dir = Directory(
        exists=True,
        mandatory=True,
        desc='FreeSurfer directory',
    )
    subject_id = traits.Str(
        mandatory=True,
        desc='FreeSurfer subject ID',
    )
    in_file = File(
        exists=True,
        mandatory=True,
        desc='Input annotation file',
    )
    hemisphere = traits.Enum(
        'lh',
        'rh',
        desc='Hemisphere to copy annotation file to',
        usedefault=True,
    )
    atlas = traits.Str(
        desc='Atlas to used in annotation file name',
    )


class _CopyAnnotsOutputSpec(TraitedSpec):
    out_file = File(
        exists=True,
        desc='Output annotation file',
    )


class CopyAnnots(SimpleInterface):
    input_spec = _CopyAnnotsInputSpec
    output_spec = _CopyAnnotsOutputSpec

    def _run_interface(self, runtime):
        out_file = os.path.join(
            self.inputs.freesurfer_dir,
            self.inputs.subject_id,
            'label',
            f'{self.inputs.hemisphere}.{self.inputs.atlas}.annot',
        )
        self._results['out_file'] = out_file

        shutil.copyfile(self.inputs.in_file, out_file)

        return runtime


class _CollectFSAverageSurfacesInputSpec(TraitedSpec):
    freesurfer_dir = Directory(
        exists=True,
        mandatory=True,
        desc='FreeSurfer directory',
    )
    subject_id = traits.Str(
        mandatory=True,
        desc='FreeSurfer subject ID',
    )
    in_file = File(
        exists=True,
        mandatory=True,
        desc='Input annotation file',
    )
    hemisphere = traits.Enum(
        'lh',
        'rh',
        desc='Hemisphere to copy annotation file to',
        usedefault=True,
    )
    atlas = traits.Str(
        desc='Atlas to used in annotation file name',
    )


class _CollectFSAverageSurfacesOutputSpec(TraitedSpec):
    out_file = File(
        exists=True,
        desc='Output annotation file',
    )


class CollectFSAverageSurfaces(SimpleInterface):
    input_spec = _CollectFSAverageSurfacesInputSpec
    output_spec = _CollectFSAverageSurfacesOutputSpec

    def _run_interface(self, runtime):
        out_file = os.path.join(
            self.inputs.freesurfer_dir,
            self.inputs.subject_id,
            'label',
            f'{self.inputs.hemisphere}.{self.inputs.atlas}.annot',
        )
        self._results['out_file'] = out_file

        shutil.copyfile(self.inputs.in_file, out_file)

        return runtime
