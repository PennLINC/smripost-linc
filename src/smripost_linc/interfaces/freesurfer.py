"""Interfaces for working with FreeSurfer."""

import os
import shutil
from glob import glob

from nipype.interfaces.base import (
    Directory,
    DynamicTraitedSpec,
    File,
    SimpleInterface,
    TraitedSpec,
    traits,
)
from nipype.interfaces.freesurfer import ParcellationStats as BaseParcellationStats
from nipype.interfaces.freesurfer.utils import ParcellationStatsInputSpec


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
        self._results['arguments'] = arguments
        raise Exception(self._results)

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


class _CollectFSAverageSurfacesOutputSpec(TraitedSpec):
    lh_fsaverage_files = traits.List(
        File(exists=True),
        desc='Left-hemisphere fsaverage-space surfaces',
    )
    rh_fsaverage_files = traits.List(
        File(exists=True),
        desc='Right-hemisphere fsaverage-space surfaces',
    )
    names = traits.List(
        traits.Str,
        desc='Names of collected surfaces',
    )


class CollectFSAverageSurfaces(SimpleInterface):
    input_spec = _CollectFSAverageSurfacesInputSpec
    output_spec = _CollectFSAverageSurfacesOutputSpec

    def _run_interface(self, runtime):
        in_dir = os.path.join(
            self.inputs.freesurfer_dir,
            'surf',
        )
        lh_mgh_files = sorted(glob(os.path.join(in_dir, 'lh.*.fsaverage.mgh')))
        self._results['lh_fsaverage_files'] = lh_mgh_files
        self._results['names'] = []
        rh_mgh_files = []
        for lh_file in lh_mgh_files:
            name = os.path.basename(lh_file).split('.')[1]
            self._results['names'].append(name)
            rh_file = os.path.join(in_dir, f'rh.{name}.fsaverage.mgh')
            rh_mgh_files.append(rh_file)

        self._results['rh_fsaverage_files'] = rh_mgh_files
        if not rh_mgh_files:
            raise FileNotFoundError(f'No mgh files found in {in_dir}')

        return runtime


class _ParcellationStatsInputSpec(ParcellationStatsInputSpec):
    noglobal = traits.Bool(
        argstr='--noglobal',
        desc='Do not compute global stats',
    )


class ParcellationStats(BaseParcellationStats):
    input_spec = _ParcellationStatsInputSpec
