"""Miscellaneous interfaces for sMRIPost-LINC."""

import os

import numpy as np
from nipype.interfaces.base import (
    CommandLineInputSpec,
    DynamicTraitedSpec,
    File,
    SimpleInterface,
    TraitedSpec,
    isdefined,
    traits,
)
from nipype.interfaces.workbench.base import WBCommand as WBCommandBase
from nipype.utils.filemanip import fname_presuffix
from niworkflows.interfaces.fixes import (
    FixHeaderApplyTransforms,
    _FixTraitApplyTransformsInputSpec,
)

from smripost_linc.utils.utils import split_filename


class _ApplyTransformsInputSpec(_FixTraitApplyTransformsInputSpec):
    # Nipype's version doesn't have GenericLabel
    interpolation = traits.Enum(
        'Linear',
        'NearestNeighbor',
        'CosineWindowedSinc',
        'WelchWindowedSinc',
        'HammingWindowedSinc',
        'LanczosWindowedSinc',
        'MultiLabel',
        'Gaussian',
        'BSpline',
        'GenericLabel',
        argstr='%s',
        usedefault=True,
    )


class ApplyTransforms(FixHeaderApplyTransforms):
    """A modified version of FixHeaderApplyTransforms from niworkflows.

    The niworkflows version of ApplyTransforms "fixes the resampled image header
    to match the xform of the reference image".
    This modification overrides the allowed interpolation values,
    since FixHeaderApplyTransforms doesn't support GenericLabel,
    which is preferred over MultiLabel.
    """

    input_spec = _ApplyTransformsInputSpec

    def _run_interface(self, runtime):
        if not isdefined(self.inputs.output_image):
            self.inputs.output_image = fname_presuffix(
                self.inputs.input_image,
                suffix='_trans.nii.gz',
                newpath=runtime.cwd,
                use_ext=False,
            )

        runtime = super()._run_interface(runtime)
        return runtime


class _WBCommandInputSpec(CommandLineInputSpec):
    num_threads = traits.Int(1, usedefault=True, nohash=True, desc='set number of threads')


class WBCommand(WBCommandBase):
    """A base interface for wb_command.

    This inherits from Nipype's WBCommand interface, but adds a num_threads input.
    """

    @property
    def num_threads(self):
        """Get number of threads."""
        return self.inputs.num_threads

    @num_threads.setter
    def num_threads(self, value):
        self.inputs.num_threads = value

    def __init__(self, **inputs):
        super().__init__(**inputs)

        if hasattr(self.inputs, 'num_threads'):
            self.inputs.on_trait_change(self._nthreads_update, 'num_threads')

    def _nthreads_update(self):
        """Update environment with new number of threads."""
        self.inputs.environ['OMP_NUM_THREADS'] = str(self.inputs.num_threads)


class _CiftiSeparateMetricInputSpec(_WBCommandInputSpec):
    """Input specification for the CiftiSeparateMetric command."""

    in_file = File(
        exists=True,
        mandatory=True,
        argstr='%s ',
        position=0,
        desc='The input dense series',
    )
    direction = traits.Enum(
        'ROW',
        'COLUMN',
        mandatory=True,
        argstr='%s ',
        position=1,
        desc='which dimension to smooth along, ROW or COLUMN',
    )
    metric = traits.Str(
        mandatory=True,
        argstr=' -metric %s ',
        position=2,
        desc='which of the structure eg CORTEX_LEFT CORTEX_RIGHT'
        'check https://www.humanconnectome.org/software/workbench-command/-cifti-separate ',
    )
    out_file = File(
        name_source=['in_file'],
        name_template='correlation_matrix_%s.func.gii',
        keep_extension=True,
        argstr=' %s',
        position=3,
        desc='The gifti output, either left and right',
    )


class _CiftiSeparateMetricOutputSpec(TraitedSpec):
    """Output specification for the CiftiSeparateMetric command."""

    out_file = File(exists=True, desc='output CIFTI file')


class CiftiSeparateMetric(WBCommand):
    """Extract left or right hemisphere surfaces from CIFTI file (.dtseries).

    Other structures can also be extracted.
    The input cifti file must have a brain models mapping on the chosen
    dimension, columns for .dtseries,

    Examples
    --------
    >>> ciftiseparate = CiftiSeparateMetric()
    >>> ciftiseparate.inputs.in_file = 'sub-01XX_task-rest.dtseries.nii'
    >>> ciftiseparate.inputs.metric = "CORTEX_LEFT" # extract left hemisphere
    >>> ciftiseparate.inputs.out_file = 'sub_01XX_task-rest_hemi-L.func.gii'
    >>> ciftiseparate.inputs.direction = 'COLUMN'
    >>> ciftiseparate.cmdline
    wb_command  -cifti-separate 'sub-01XX_task-rest.dtseries.nii'  COLUMN \
      -metric CORTEX_LEFT 'sub_01XX_task-rest_hemi-L.func.gii'
    """

    input_spec = _CiftiSeparateMetricInputSpec
    output_spec = _CiftiSeparateMetricOutputSpec
    _cmd = 'wb_command  -cifti-separate'


class _CiftiCreateDenseScalarInputSpec(_WBCommandInputSpec):
    """Input specification for the CiftiSeparateVolumeAll command."""

    out_file = File(
        exists=False,
        mandatory=False,
        genfile=True,
        argstr='%s',
        position=0,
        desc='The CIFTI output.',
    )
    left_metric = File(
        exists=True,
        mandatory=False,
        argstr='-left-metric %s',
        position=1,
        desc='The input surface data from the left hemisphere.',
    )
    right_metric = File(
        exists=True,
        mandatory=False,
        argstr='-right-metric %s',
        position=2,
        desc='The input surface data from the right hemisphere.',
    )
    volume_data = File(
        exists=True,
        mandatory=False,
        argstr='-volume %s',
        position=3,
        desc='The input volumetric data.',
    )
    structure_label_volume = File(
        exists=True,
        mandatory=False,
        argstr='%s',
        position=4,
        desc='A label file indicating the structure of each voxel in volume_data.',
    )


class _CiftiCreateDenseScalarOutputSpec(TraitedSpec):
    """Output specification for the CiftiCreateDenseScalar command."""

    out_file = File(exists=True, desc='output CIFTI file')


class CiftiCreateDenseScalar(WBCommand):
    """Extract volumetric data from CIFTI file (.dtseries).

    Other structures can also be extracted.
    The input cifti file must have a brain models mapping on the chosen
    dimension, columns for .dtseries,

    Examples
    --------
    >>> cifticreatedensescalar = CiftiCreateDenseScalar()
    >>> cifticreatedensescalar.inputs.out_file = 'sub_01_task-rest.dscalar.nii'
    >>> cifticreatedensescalar.inputs.left_metric = 'sub_01_task-rest_hemi-L.func.gii'
    >>> cifticreatedensescalar.inputs.left_metric = 'sub_01_task-rest_hemi-R.func.gii'
    >>> cifticreatedensescalar.inputs.volume_data = 'sub_01_task-rest_subcortical.nii.gz'
    >>> cifticreatedensescalar.inputs.structure_label_volume = 'sub_01_task-rest_labels.nii.gz'
    >>> cifticreatedensescalar.cmdline
    wb_command -cifti-create-dense-scalar 'sub_01_task-rest.dscalar.nii' \
        -left-metric 'sub_01_task-rest_hemi-L.func.gii' \
        -right-metric 'sub_01_task-rest_hemi-R.func.gii' \
        -volume-data 'sub_01_task-rest_subcortical.nii.gz' 'sub_01_task-rest_labels.nii.gz'
    """

    input_spec = _CiftiCreateDenseScalarInputSpec
    output_spec = _CiftiCreateDenseScalarOutputSpec
    _cmd = 'wb_command -cifti-create-dense-scalar'

    def _gen_filename(self, name):
        if name != 'out_file':
            return None

        if isdefined(self.inputs.out_file):
            return self.inputs.out_file
        elif isdefined(self.inputs.volume_data):
            _, fname, _ = split_filename(self.inputs.volume_data)
        else:
            _, fname, _ = split_filename(self.inputs.left_metric)

        return f'{fname}_converted.dscalar.nii'

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs['out_file'] = os.path.abspath(self._gen_filename('out_file'))
        return outputs


class _ParcellationStats2TSVInputSpec(DynamicTraitedSpec):
    in_file = File(exists=True, mandatory=True, desc='parcellated data')
    hemisphere = traits.Enum('lh', 'rh', usedefault=True, desc='hemisphere')
    atlas = traits.Str(mandatory=True, desc='atlas name')
    out_file = File(
        name_source=['in_file'],
        name_template='parcellated_%s.tsv',
        keep_extension=True,
        desc='The TSV file',
    )


class _ParcellationStats2TSVOutputSpec(TraitedSpec):
    out_file = File(exists=True, desc='TSV file with parcellated data')


class ParcellationStats2TSV(SimpleInterface):
    """Convert parcellated data to TSV."""

    input_spec = _ParcellationStats2TSVInputSpec
    output_spec = _ParcellationStats2TSVOutputSpec

    def _sanity_check_columns(df, ref_col, red_col, atol=0):
        if not np.allclose(
            df[ref_col].astype(np.float32),
            df[red_col].astype(np.float32),
            atol=atol,
        ):
            raise Exception(f'The {ref_col} values were not identical to {red_col}')

        df.drop(red_col, axis=1, inplace=True)
        return df

    def _run_interface(self, runtime):
        import pandas as pd

        redundant_columns = [
            ('NumVert', 'NVertices_wgpct', 0),
            ('SurfArea', 'Area_mm2_wgpct', 1),
            ('NumVert', 'NVertices_piallgi', 0),
            ('SurfArea', 'Area_mm2_piallgi', 1),
        ]

        with open(self.inputs.in_file) as f_obj:
            data = f_obj.readlines()

        idx = [i for i, line in enumerate(data) if line.startswith('# ColHeaders ')]
        if len(idx) != 1:
            raise ValueError(f'Could not find column headers in the file {self.inputs.in_file}')

        idx = idx[0]

        columns_row = data[idx]
        actual_data = data[idx + 1 :]
        actual_data = [line.split() for line in actual_data]
        columns = columns_row.replace('# ColHeaders ', '').split()

        df = pd.DataFrame(
            columns=columns,
            data=actual_data,
        )
        df.insert(0, 'hemisphere', self.inputs.hemisphere)
        df.insert(0, 'atlas', self.inputs.atlas)

        for ref_col, red_col, atol in redundant_columns:
            if ref_col in df.columns and red_col in df.columns:
                df = self._sanity_check_columns(df=df, ref_col=ref_col, red_col=red_col, atol=atol)

        df.to_csv(self._results['out_file'], sep='\t', index=False)

        return runtime
