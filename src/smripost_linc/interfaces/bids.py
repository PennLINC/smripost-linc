"""BIDS-related interfaces for sMRIPost-LINC."""

from json import loads

from bids.layout import Config
from nipype.interfaces.base import (
    DynamicTraitedSpec,
    SimpleInterface,
    TraitedSpec,
    traits,
)
from nipype.interfaces.io import add_traits
from niworkflows.interfaces.bids import DerivativesDataSink as BaseDerivativesDataSink

from smripost_linc.data import load as load_data
from smripost_linc.utils.bids import _get_bidsuris

# NOTE: Modified for smripost_linc's purposes
smripost_linc_spec = loads(load_data('io_spec.json').read_text())
bids_config = Config.load('bids')
deriv_config = Config.load('derivatives')

smripost_linc_entities = {v['name']: v['pattern'] for v in smripost_linc_spec['entities']}
merged_entities = {**bids_config.entities, **deriv_config.entities}
merged_entities = {k: v.pattern for k, v in merged_entities.items()}
merged_entities = {**merged_entities, **smripost_linc_entities}
merged_entities = [{'name': k, 'pattern': v} for k, v in merged_entities.items()]
config_entities = frozenset({e['name'] for e in merged_entities})


class DerivativesDataSink(BaseDerivativesDataSink):
    """Store derivative files.

    A child class of the niworkflows DerivativesDataSink,
    using smripost_linc's configuration files.
    """

    out_path_base = ''
    _allowed_entities = set(config_entities)
    _config_entities = config_entities
    _config_entities_dict = merged_entities
    _file_patterns = smripost_linc_spec['default_path_patterns']


class _BIDSURIInputSpec(DynamicTraitedSpec):
    dataset_links = traits.Dict(mandatory=True, desc='Dataset links')
    out_dir = traits.Str(mandatory=True, desc='Output directory')
    metadata = traits.Dict(desc='Metadata dictionary')
    field = traits.Str(
        'Sources',
        usedefault=True,
        desc='Field to use for BIDS URIs in metadata dict',
    )


class _BIDSURIOutputSpec(TraitedSpec):
    out = traits.List(
        traits.Str,
        desc='BIDS URI(s) for file',
    )
    metadata = traits.Dict(
        desc='Dictionary with "Sources" field.',
    )


class BIDSURI(SimpleInterface):
    """Convert input filenames to BIDS URIs, based on links in the dataset.

    This interface can combine multiple lists of inputs.
    """

    input_spec = _BIDSURIInputSpec
    output_spec = _BIDSURIOutputSpec

    def __init__(self, numinputs=0, **inputs):
        super().__init__(**inputs)
        self._numinputs = numinputs
        if numinputs >= 1:
            input_names = [f'in{i + 1}' for i in range(numinputs)]
        else:
            input_names = []
        add_traits(self.inputs, input_names)

    def _run_interface(self, runtime):
        inputs = [getattr(self.inputs, f'in{i + 1}') for i in range(self._numinputs)]
        uris = _get_bidsuris(inputs, self.inputs.dataset_links, self.inputs.out_dir)
        self._results['out'] = uris

        # Add the URIs to the metadata dictionary.
        metadata = self.inputs.metadata or {}
        metadata = metadata.copy()
        metadata[self.inputs.field] = metadata.get(self.inputs.field, []) + uris
        self._results['metadata'] = metadata

        return runtime
