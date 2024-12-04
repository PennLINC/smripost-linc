"""Interfaces for working with FreeSurfer."""

import os

from nipype.interfaces.base import (
    Directory,
    DynamicTraitedSpec,
    File,
    SimpleInterface,
    TraitedSpec,
    isdefined,
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


class _MRISegStatsInputSpec(FSTraitedSpec):
    # required
    subject_id = traits.String(
        'subject_id',
        usedefault=True,
        position=-3,
        argstr='%s',
        mandatory=True,
        desc='Subject being processed',
    )
    hemisphere = traits.Enum(
        'lh',
        'rh',
        position=-2,
        argstr='%s',
        mandatory=True,
        desc='Hemisphere being processed',
    )
    # implicit
    wm = File(
        mandatory=True,
        exists=True,
        desc='Input file must be <subject_id>/mri/wm.mgz',
    )
    lh_white = File(
        mandatory=True,
        exists=True,
        desc='Input file must be <subject_id>/surf/lh.white',
    )
    rh_white = File(
        mandatory=True,
        exists=True,
        desc='Input file must be <subject_id>/surf/rh.white',
    )
    lh_pial = File(
        mandatory=True, exists=True, desc='Input file must be <subject_id>/surf/lh.pial'
    )
    rh_pial = File(
        mandatory=True, exists=True, desc='Input file must be <subject_id>/surf/rh.pial'
    )
    transform = File(
        mandatory=True,
        exists=True,
        desc='Input file must be <subject_id>/mri/transforms/talairach.xfm',
    )
    thickness = File(
        mandatory=True,
        exists=True,
        desc='Input file must be <subject_id>/surf/?h.thickness',
    )
    brainmask = File(
        mandatory=True,
        exists=True,
        desc='Input file must be <subject_id>/mri/brainmask.mgz',
    )
    aseg = File(
        mandatory=True,
        exists=True,
        desc='Input file must be <subject_id>/mri/aseg.presurf.mgz',
    )
    ribbon = File(
        mandatory=True,
        exists=True,
        desc='Input file must be <subject_id>/mri/ribbon.mgz',
    )
    cortex_label = File(exists=True, desc='implicit input file {hemi}.cortex.label')
    # optional
    surface = traits.String(position=-1, argstr='%s', desc="Input surface (e.g. 'white')")
    mgz = traits.Bool(argstr='-mgz', desc='Look for mgz files')
    in_cortex = File(argstr='-cortex %s', exists=True, desc='Input cortex label')
    in_annotation = File(
        argstr='-a %s',
        exists=True,
        xor=['in_label'],
        desc='compute properties for each label in the annotation file separately',
    )
    in_label = File(
        argstr='-l %s',
        exists=True,
        xor=['in_annotatoin', 'out_color'],
        desc='limit calculations to specified label',
    )
    tabular_output = traits.Bool(argstr='-b', desc='Tabular output')
    out_table = File(
        argstr='-f %s',
        exists=False,
        genfile=True,
        requires=['tabular_output'],
        desc='Table output to tablefile',
    )
    out_color = File(
        argstr='-c %s',
        exists=False,
        genfile=True,
        xor=['in_label'],
        desc="Output annotation files's colortable to text file",
    )
    copy_inputs = traits.Bool(
        desc='If running as a node, set this to True. '
        'This will copy the input files to the node directory.'
    )
    th3 = traits.Bool(
        argstr='-th3',
        requires=['cortex_label'],
        desc='turns on new vertex-wise volume calc for mris_anat_stats',
    )


class _MRISegStatsOutputSpec(TraitedSpec):
    out_table = File(exists=False, desc='Table output to tablefile')
    out_color = File(exists=False, desc="Output annotation files's colortable to text file")


class MRISegStats(FSCommand):
    """
    This program computes a number of anatomical properties.

    Examples
    ========
    >>> from nipype.interfaces.freesurfer import ParcellationStats
    >>> import os
    >>> parcstats = ParcellationStats()
    >>> parcstats.inputs.subject_id = '10335'
    >>> parcstats.inputs.hemisphere = 'lh'
    >>> parcstats.inputs.wm = './../mri/wm.mgz' # doctest: +SKIP
    >>> parcstats.inputs.transform = './../mri/transforms/talairach.xfm' # doctest: +SKIP
    >>> parcstats.inputs.brainmask = './../mri/brainmask.mgz' # doctest: +SKIP
    >>> parcstats.inputs.aseg = './../mri/aseg.presurf.mgz' # doctest: +SKIP
    >>> parcstats.inputs.ribbon = './../mri/ribbon.mgz' # doctest: +SKIP
    >>> parcstats.inputs.lh_pial = 'lh.pial' # doctest: +SKIP
    >>> parcstats.inputs.rh_pial = 'lh.pial' # doctest: +SKIP
    >>> parcstats.inputs.lh_white = 'lh.white' # doctest: +SKIP
    >>> parcstats.inputs.rh_white = 'rh.white' # doctest: +SKIP
    >>> parcstats.inputs.thickness = 'lh.thickness' # doctest: +SKIP
    >>> parcstats.inputs.surface = 'white'
    >>> parcstats.inputs.out_table = 'lh.test.stats'
    >>> parcstats.inputs.out_color = 'test.ctab'
    >>> parcstats.cmdline # doctest: +SKIP
    'mris_anatomical_stats -c test.ctab -f lh.test.stats 10335 lh white'
    """

    _cmd = 'mri_segstats'
    input_spec = _MRISegStatsInputSpec
    output_spec = _MRISegStatsOutputSpec

    def run(self, **inputs):
        if self.inputs.copy_inputs:
            self.inputs.subjects_dir = os.getcwd()
            if 'subjects_dir' in inputs:
                inputs['subjects_dir'] = self.inputs.subjects_dir
            copy2subjdir(self, self.inputs.lh_white, 'surf', 'lh.white')
            copy2subjdir(self, self.inputs.lh_pial, 'surf', 'lh.pial')
            copy2subjdir(self, self.inputs.rh_white, 'surf', 'rh.white')
            copy2subjdir(self, self.inputs.rh_pial, 'surf', 'rh.pial')
            copy2subjdir(self, self.inputs.wm, 'mri', 'wm.mgz')
            copy2subjdir(
                self,
                self.inputs.transform,
                os.path.join('mri', 'transforms'),
                'talairach.xfm',
            )
            copy2subjdir(self, self.inputs.brainmask, 'mri', 'brainmask.mgz')
            copy2subjdir(self, self.inputs.aseg, 'mri', 'aseg.presurf.mgz')
            copy2subjdir(self, self.inputs.ribbon, 'mri', 'ribbon.mgz')
            copy2subjdir(
                self,
                self.inputs.thickness,
                'surf',
                f'{self.inputs.hemisphere}.thickness',
            )
            if isdefined(self.inputs.cortex_label):
                copy2subjdir(
                    self,
                    self.inputs.cortex_label,
                    'label',
                    f'{self.inputs.hemisphere}.cortex.label',
                )
        createoutputdirs(self._list_outputs())
        return super().run(**inputs)

    def _gen_filename(self, name):
        if name in ['out_table', 'out_color']:
            return self._list_outputs()[name]
        return None

    def _list_outputs(self):
        outputs = self._outputs().get()
        if isdefined(self.inputs.out_table):
            outputs['out_table'] = os.path.abspath(self.inputs.out_table)
        else:
            # subject stats directory
            stats_dir = os.path.join(self.inputs.subjects_dir, self.inputs.subject_id, 'stats')
            if isdefined(self.inputs.in_annotation):
                # if out_table is not defined just tag .stats on the end
                # instead of .annot
                if self.inputs.surface == 'pial':
                    basename = os.path.basename(self.inputs.in_annotation).replace(
                        '.annot', '.pial.stats'
                    )
                else:
                    basename = os.path.basename(self.inputs.in_annotation).replace(
                        '.annot', '.stats'
                    )
            elif isdefined(self.inputs.in_label):
                # if out_table is not defined just tag .stats on the end
                # instead of .label
                if self.inputs.surface == 'pial':
                    basename = os.path.basename(self.inputs.in_label).replace(
                        '.label', '.pial.stats'
                    )
                else:
                    basename = os.path.basename(self.inputs.in_label).replace('.label', '.stats')
            else:
                basename = str(self.inputs.hemisphere) + '.aparc.annot.stats'
            outputs['out_table'] = os.path.join(stats_dir, basename)
        if isdefined(self.inputs.out_color):
            outputs['out_color'] = os.path.abspath(self.inputs.out_color)
        else:
            # subject label directory
            out_dir = os.path.join(self.inputs.subjects_dir, self.inputs.subject_id, 'label')
            if isdefined(self.inputs.in_annotation):
                # find the annotation name (if it exists)
                basename = os.path.basename(self.inputs.in_annotation)
                for item in ['lh.', 'rh.', 'aparc.', 'annot']:
                    basename = basename.replace(item, '')
                annot = basename
                # if the out_color table is not defined, one with the annotation
                # name will be created
                if 'BA' in annot:
                    outputs['out_color'] = os.path.join(out_dir, annot + 'ctab')
                else:
                    outputs['out_color'] = os.path.join(out_dir, 'aparc.annot.' + annot + 'ctab')
            else:
                outputs['out_color'] = os.path.join(out_dir, 'aparc.annot.ctab')
        return outputs
