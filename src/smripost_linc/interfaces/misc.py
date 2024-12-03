"""Miscellaneous interfaces for fmriprep-aroma."""

from nipype.interfaces.base import (
    CommandLineInputSpec,
    File,
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
