"""Utilities to handle BIDS inputs."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from bids.layout import BIDSLayout
from bids.utils import listify
from nipype.interfaces.base import isdefined
from nipype.interfaces.utility.base import _ravel
from niworkflows.utils.spaces import SpatialReferences

from smripost_linc.data import load as load_data


def extract_entities(file_list: str | list[str]) -> dict:
    """Return a dictionary of common entities given a list of files.

    Parameters
    ----------
    file_list : str | list[str]
        File path or list of file paths.

    Returns
    -------
    entities : dict
        Dictionary of entities.

    Examples
    --------
    >>> extract_entities('sub-01/anat/sub-01_T1w.nii.gz')
    {'subject': '01', 'suffix': 'T1w', 'datatype': 'anat', 'extension': '.nii.gz'}
    >>> extract_entities(['sub-01/anat/sub-01_T1w.nii.gz'] * 2)
    {'subject': '01', 'suffix': 'T1w', 'datatype': 'anat', 'extension': '.nii.gz'}
    >>> extract_entities(['sub-01/anat/sub-01_run-1_T1w.nii.gz',
    ...                   'sub-01/anat/sub-01_run-2_T1w.nii.gz'])
    {'subject': '01', 'run': [1, 2], 'suffix': 'T1w', 'datatype': 'anat', 'extension': '.nii.gz'}

    """
    from collections import defaultdict

    from bids.layout import parse_file_entities

    entities = defaultdict(list)
    for e, v in [
        ev_pair for f in listify(file_list) for ev_pair in parse_file_entities(f).items()
    ]:
        entities[e].append(v)

    def _unique(inlist):
        inlist = sorted(set(inlist))
        if len(inlist) == 1:
            return inlist[0]
        return inlist

    return {k: _unique(v) for k, v in entities.items()}


def collect_derivatives(
    raw_dataset: Path | BIDSLayout | None,
    derivatives_dataset: Path | BIDSLayout | None,
    entities: dict | None,
    spec: dict | None = None,
    patterns: list[str] | None = None,
    allow_multiple: bool = False,
    spaces: SpatialReferences | None = None,
) -> dict:
    """Gather existing derivatives and compose a cache.

    TODO: Ingress 'spaces' and search for images in the spaces *or* xfms to those spaces.

    Parameters
    ----------
    raw_dataset : Path | BIDSLayout | None
        Path to the raw dataset or a BIDSLayout instance.
    derivatives_dataset : Path | BIDSLayout
        Path to the derivatives dataset or a BIDSLayout instance.
    entities : dict
        Dictionary of entities to use for filtering.
    spec : dict | None
        Specification dictionary.
    patterns : list[str] | None
        List of patterns to use for filtering.
    allow_multiple : bool
        Allow multiple files to be returned for a given query.
    spaces : SpatialReferences | None
        Spatial references to select for.

    Returns
    -------
    derivs_cache : dict
        Dictionary with keys corresponding to the derivatives and values
        corresponding to the file paths.
    """
    from json import loads

    if not entities:
        entities = {}

    _spec = None
    if spec is None or patterns is None:
        _spec = json.loads(load_data.readable('io_spec.json').read_text())

        if spec is None:
            spec = _spec['queries']

        if patterns is None:
            patterns = _spec['default_path_patterns']

        _spec.pop('queries')

    config = ['bids', 'derivatives']
    if _spec:
        config = ['bids', 'derivatives', _spec]

    # Search for derivatives data
    derivs_cache = defaultdict(list, {})
    if derivatives_dataset is not None:
        layout = derivatives_dataset
        if isinstance(layout, Path):
            dataset_description = layout / 'dataset_description.json'
            if not dataset_description.is_file():
                raise FileNotFoundError(f'Dataset description not found: {dataset_description}')

            desc = loads(dataset_description.read_text())
            if desc.get('DatasetType') != 'derivative':
                return derivs_cache

            layout = BIDSLayout(
                layout,
                config=config,
                validate=False,
            )

        for k, q in spec['derivatives'].items():
            if k.startswith('anat'):
                # Allow anatomical derivatives at session level or subject level
                query = {**{'session': [entities.get('session'), None]}, **q}
            else:
                # Combine entities with query. Query values override file entities.
                query = {**entities, **q}

            item = layout.get(return_type='filename', **query)
            if not item:
                derivs_cache[k] = None
            elif not allow_multiple and len(item) > 1 and k.startswith('anat'):
                # Anatomical derivatives are allowed to have multiple files (e.g., T1w and T2w)
                # but we just grab the first one
                derivs_cache[k] = item[0]
            elif not allow_multiple and len(item) > 1:
                raise ValueError(f'Multiple files found for {k}: {item}')
            else:
                derivs_cache[k] = item[0] if len(item) == 1 else item

        for k, q in spec['transforms'].items():
            if k.startswith('anat'):
                # Allow anatomical derivatives at session level or subject level
                query = {**{'session': [entities.get('session'), None]}, **q}
            else:
                # Combine entities with query. Query values override file entities.
                query = {**entities, **q}

            item = layout.get(return_type='filename', **query)
            if not item:
                derivs_cache[k] = None
            elif not allow_multiple and len(item) > 1 and k.startswith('anat'):
                # Anatomical derivatives are allowed to have multiple files (e.g., T1w and T2w)
                # but we just grab the first one
                derivs_cache[k] = item[0]
            elif not allow_multiple and len(item) > 1:
                raise ValueError(f'Multiple files found for {k}: {item}')
            else:
                derivs_cache[k] = item[0] if len(item) == 1 else item

    # Search for requested output spaces
    # XXX: This is all BOLD-specific.
    if spaces is not None:
        # Put the output-space files/transforms in lists so they can be parallelized with
        # template_iterator_wf.
        spaces_found, bold_outputspaces, bold_mask_outputspaces = [], [], []
        for space in spaces.references:
            # First try to find processed BOLD+mask files in the requested space
            bold_query = {**entities, **spec['derivatives']['bold_mni152nlin6asym']}
            bold_query['space'] = space.space
            bold_query = {**bold_query, **space.spec}
            bold_item = layout.get(return_type='filename', **bold_query)
            bold_outputspaces.append(bold_item[0] if bold_item else None)

            mask_query = {**entities, **spec['derivatives']['bold_mask_mni152nlin6asym']}
            mask_query['space'] = space.space
            mask_query = {**mask_query, **space.spec}
            mask_item = layout.get(return_type='filename', **mask_query)
            bold_mask_outputspaces.append(mask_item[0] if mask_item else None)

            spaces_found.append(bool(bold_item) and bool(mask_item))

        if all(spaces_found):
            derivs_cache['bold_outputspaces'] = bold_outputspaces
            derivs_cache['bold_mask_outputspaces'] = bold_mask_outputspaces
        else:
            # The requested spaces were not found, try to find transforms
            print(
                'Not all requested output spaces were found. '
                'We will try to find transforms to these spaces and apply them to the BOLD data.',
                flush=True,
            )

        spaces_found, anat2outputspaces_xfm = [], []
        for space in spaces.references:
            # Now try to find transform to the requested space
            anat2space_query = {
                **{'session': [entities.get('session'), None]},
                **spec['transforms']['anat2mni152nlin6asym'],
            }
            anat2space_query['to'] = space.space
            item = layout.get(return_type='filename', **anat2space_query)
            anat2outputspaces_xfm.append(item[0] if item else None)
            spaces_found.append(bool(item))

        if all(spaces_found):
            derivs_cache['anat2outputspaces_xfm'] = anat2outputspaces_xfm
        else:
            missing_spaces = ', '.join(
                [s.space for s, found in zip(spaces.references, spaces_found) if not found]
            )
            raise ValueError(
                f'Transforms to the following requested spaces not found: {missing_spaces}.'
            )

    return derivs_cache


def collect_atlases(datasets, atlases, bids_filters=None):
    """Collect atlases from a list of BIDS-Atlas datasets.

    Selection of labels files and metadata does not leverage the inheritance principle.
    That probably won't be possible until PyBIDS supports the BIDS-Atlas extension natively.

    Parameters
    ----------
    datasets : dict of str:str or str:BIDSLayout pairs
        Dictionary of BIDS datasets to search for atlases.
    atlases : list of str
        List of atlases to collect from across the datasets.
    bids_filters : dict
        Additional filters to apply to the BIDS query.
        Only the "atlas" key is used.

    Returns
    -------
    atlas_cache : dict
        Dictionary of atlases with metadata.
        Keys are the atlas names, values are dictionaries with keys:

        - "dataset" : str
            Name of the dataset containing the atlas.
        - "image" : str
            Path to the atlas image.
        - "labels" : str
            Path to the atlas labels file.
        - "metadata" : dict
            Metadata associated with the atlas.
    """
    import json

    import pandas as pd
    from bids.layout import BIDSLayout

    from smripost_linc.data import load as load_data

    atlas_cfg = load_data('atlas_bids_config.json')
    bids_filters = bids_filters or {}

    atlas_filter = bids_filters.get('atlas', {})
    # Hard-code space for now
    atlas_filter['space'] = ['fsaverage', 'fsLR', 'MNI152NLin6Asym']

    atlas_cache = {}
    for dataset_name, dataset_path in datasets.items():
        if not isinstance(dataset_path, BIDSLayout):
            layout = BIDSLayout(dataset_path, config=[atlas_cfg], validate=False)
        else:
            layout = dataset_path

        if layout.get_dataset_description().get('DatasetType') != 'atlas':
            continue

        for atlas in atlases:
            atlas_images = layout.get(
                atlas=atlas,
                **atlas_filter,
                return_type='file',
            )
            if not atlas_images:
                continue
            elif len(atlas_images) > 1:
                bulleted_list = '\n'.join([f'  - {img}' for img in atlas_images])
                print(
                    f'Multiple atlas images found for {atlas} with query {atlas_filter}:\n'
                    f'{bulleted_list}\nUsing {atlas_images[0]}.'
                )

            if atlas in atlas_cache:
                raise ValueError(f"Multiple datasets contain the same atlas '{atlas}'")

            atlas_image = atlas_images[0]
            atlas_labels = layout.get_nearest(atlas_image, extension='.tsv', strict=False)
            atlas_metadata_file = layout.get_nearest(atlas_image, extension='.json', strict=True)

            if not atlas_labels:
                raise FileNotFoundError(f'No TSV file found for {atlas_image}')

            atlas_metadata = None
            if atlas_metadata_file:
                with open(atlas_metadata_file) as f_obj:
                    atlas_metadata = json.load(f_obj)

            atlas_file = layout.get_file(atlas_image)
            extension = atlas_file.entities['extension']
            file_format = {
                '.nii': 'nifti',
                '.nii.gz': 'nifti',
                '.label.gii': 'gifti',
                '.dlabel.nii': 'cifti',
            }.get(extension, 'unknown')

            atlas_cache[atlas] = {
                'dataset': dataset_name,
                'image': atlas_image,
                'labels': atlas_labels,
                'metadata': atlas_metadata,
                'space': atlas_file.entities['space'],
                'format': file_format,
            }

    for atlas in atlases:
        if atlas not in atlas_cache:
            print(f'No atlas images found for {atlas} with query {atlas_filter}')

    for _atlas, atlas_info in atlas_cache.items():
        if not atlas_info['labels']:
            raise FileNotFoundError(f"No TSV file found for {atlas_info['image']}")

        if atlas_info['format'] == 'unknown':
            raise ValueError(f"Unknown format for atlas '{_atlas}' (extension='{extension}')")

        # Check the contents of the labels file
        df = pd.read_table(atlas_info['labels'])
        if 'label' not in df.columns:
            raise ValueError(f"'label' column not found in {atlas_info['labels']}")

        if 'index' not in df.columns:
            raise ValueError(f"'index' column not found in {atlas_info['labels']}")

    return atlas_cache


def write_bidsignore(deriv_dir):
    bids_ignore = (
        '*.html',
        'logs/',
        'figures/',  # Reports
        '*_xfm.*',  # Unspecified transform files
        '*.surf.gii',  # Unspecified structural outputs
        # Unspecified functional outputs
        '*_boldref.nii.gz',
        '*_bold.func.gii',
        '*_mixing.tsv',
        '*_timeseries.tsv',
    )
    ignore_file = Path(deriv_dir) / '.bidsignore'

    ignore_file.write_text('\n'.join(bids_ignore) + '\n')


def write_derivative_description(input_dir, output_dir, dataset_links=None):
    """Write dataset_description.json file for derivatives.

    Parameters
    ----------
    input_dir : :obj:`str`
        Path to the primary input dataset being ingested.
        This may be a raw BIDS dataset (in the case of raw+derivatives workflows)
        or a preprocessing derivatives dataset (in the case of derivatives-only workflows).
    output_dir : :obj:`str`
        Path to the output sMRIPost-LINC dataset.
    dataset_links : :obj:`dict`, optional
        Dictionary of dataset links to include in the dataset description.
    """
    import json
    import os

    from packaging.version import Version

    from smripost_linc import __version__

    DOWNLOAD_URL = f'https://github.com/pennlinc/smripost_linc/archive/{__version__}.tar.gz'

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    orig_dset_description = os.path.join(input_dir, 'dataset_description.json')
    if not os.path.isfile(orig_dset_description):
        raise FileNotFoundError(f'Dataset description does not exist: {orig_dset_description}')

    with open(orig_dset_description) as fobj:
        desc = json.load(fobj)

    # Update dataset description
    desc['Name'] = 'sMRIPost-LINC- Anatomical Postprocessing Outputs'
    desc['BIDSVersion'] = '1.9.0dev'
    desc['DatasetType'] = 'derivative'
    desc['HowToAcknowledge'] = 'Include the generated boilerplate in the methods section.'

    # Start with GeneratedBy from the primary input dataset's dataset_description.json
    desc['GeneratedBy'] = desc.get('GeneratedBy', [])

    # Add GeneratedBy from derivatives' dataset_description.jsons
    for name, link in enumerate(dataset_links):
        if name not in ('templateflow', 'input'):
            dataset_desc = Path(link) / 'dataset_description.json'
            if dataset_desc.is_file():
                with open(dataset_desc) as fobj:
                    dataset_desc_dict = json.load(fobj)

                if 'GeneratedBy' in dataset_desc_dict:
                    desc['GeneratedBy'].insert(0, dataset_desc_dict['GeneratedBy'][0])

    # Add GeneratedBy from sMRIPost-LINC
    desc['GeneratedBy'].insert(
        0,
        {
            'Name': 'sMRIPost-LINC',
            'Version': __version__,
            'CodeURL': DOWNLOAD_URL,
        },
    )

    # Keys that can only be set by environment
    if 'SMRIPOST_LINC_DOCKER_TAG' in os.environ:
        desc['GeneratedBy'][0]['Container'] = {
            'Type': 'docker',
            'Tag': f"pennlinc/smripost_linc:{os.environ['SMRIPOST_LINC_DOCKER_TAG']}",
        }

    if 'SMRIPOST_LINC__SINGULARITY_URL' in os.environ:
        desc['GeneratedBy'][0]['Container'] = {
            'Type': 'singularity',
            'URI': os.getenv('SMRIPOST_LINC__SINGULARITY_URL'),
        }

    # Replace local templateflow path with URL
    dataset_links = dataset_links.copy()
    dataset_links['templateflow'] = 'https://github.com/templateflow/templateflow'

    # Add DatasetLinks
    desc['DatasetLinks'] = desc.get('DatasetLinks', {})
    for k, v in dataset_links.items():
        if k in desc['DatasetLinks'].keys() and str(desc['DatasetLinks'][k]) != str(v):
            print(f"'{k}' is already a dataset link. Overwriting.")

        desc['DatasetLinks'][k] = str(v)

    out_desc = Path(output_dir / 'dataset_description.json')
    if out_desc.is_file():
        old_desc = json.loads(out_desc.read_text())
        old_version = old_desc['GeneratedBy'][0]['Version']
        if Version(__version__).public != Version(old_version).public:
            print(f'Previous output generated by version {old_version} found.')
    else:
        out_desc.write_text(json.dumps(desc, indent=4))


def validate_input_dir(exec_env, bids_dir, participant_label, need_T1w=True):
    # Ignore issues and warnings that should not influence FMRIPREP
    import subprocess
    import sys
    import tempfile

    validator_config_dict = {
        'ignore': [
            'EVENTS_COLUMN_ONSET',
            'EVENTS_COLUMN_DURATION',
            'TSV_EQUAL_ROWS',
            'TSV_EMPTY_CELL',
            'TSV_IMPROPER_NA',
            'VOLUME_COUNT_MISMATCH',
            'BVAL_MULTIPLE_ROWS',
            'BVEC_NUMBER_ROWS',
            'DWI_MISSING_BVAL',
            'INCONSISTENT_SUBJECTS',
            'INCONSISTENT_PARAMETERS',
            'BVEC_ROW_LENGTH',
            'B_FILE',
            'PARTICIPANT_ID_COLUMN',
            'PARTICIPANT_ID_MISMATCH',
            'TASK_NAME_MUST_DEFINE',
            'PHENOTYPE_SUBJECTS_MISSING',
            'STIMULUS_FILE_MISSING',
            'DWI_MISSING_BVEC',
            'EVENTS_TSV_MISSING',
            'TSV_IMPROPER_NA',
            'ACQTIME_FMT',
            'Participants age 89 or higher',
            'DATASET_DESCRIPTION_JSON_MISSING',
            'FILENAME_COLUMN',
            'WRONG_NEW_LINE',
            'MISSING_TSV_COLUMN_CHANNELS',
            'MISSING_TSV_COLUMN_IEEG_CHANNELS',
            'MISSING_TSV_COLUMN_IEEG_ELECTRODES',
            'UNUSED_STIMULUS',
            'CHANNELS_COLUMN_SFREQ',
            'CHANNELS_COLUMN_LOWCUT',
            'CHANNELS_COLUMN_HIGHCUT',
            'CHANNELS_COLUMN_NOTCH',
            'CUSTOM_COLUMN_WITHOUT_DESCRIPTION',
            'ACQTIME_FMT',
            'SUSPICIOUSLY_LONG_EVENT_DESIGN',
            'SUSPICIOUSLY_SHORT_EVENT_DESIGN',
            'MALFORMED_BVEC',
            'MALFORMED_BVAL',
            'MISSING_TSV_COLUMN_EEG_ELECTRODES',
            'MISSING_SESSION',
        ],
        'error': ['NO_T1W'] if need_T1w else [],
        'ignoredFiles': ['/dataset_description.json', '/participants.tsv'],
    }
    # Limit validation only to data from requested participants
    if participant_label:
        all_subs = {s.name[4:] for s in bids_dir.glob('sub-*')}
        selected_subs = {s[4:] if s.startswith('sub-') else s for s in participant_label}
        bad_labels = selected_subs.difference(all_subs)
        if bad_labels:
            error_msg = (
                'Data for requested participant(s) label(s) not found. Could '
                'not find data for participant(s): %s. Please verify the requested '
                'participant labels.'
            )
            if exec_env == 'docker':
                error_msg += (
                    ' This error can be caused by the input data not being '
                    'accessible inside the docker container. Please make sure all '
                    'volumes are mounted properly (see https://docs.docker.com/'
                    'engine/reference/commandline/run/#mount-volume--v---read-only)'
                )
            if exec_env == 'singularity':
                error_msg += (
                    ' This error can be caused by the input data not being '
                    'accessible inside the singularity container. Please make sure '
                    'all paths are mapped properly (see https://www.sylabs.io/'
                    'guides/3.0/user-guide/bind_paths_and_mounts.html)'
                )
            raise RuntimeError(error_msg % ','.join(bad_labels))

        ignored_subs = all_subs.difference(selected_subs)
        if ignored_subs:
            for sub in ignored_subs:
                validator_config_dict['ignoredFiles'].append(f'/sub-{sub}/**')
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.json') as temp:
        temp.write(json.dumps(validator_config_dict))
        temp.flush()
        try:
            subprocess.check_call(['bids-validator', str(bids_dir), '-c', temp.name])  # noqa: S607
        except FileNotFoundError:
            print('bids-validator does not appear to be installed', file=sys.stderr)


def _find_nearest_path(path_dict, input_path):
    """Find the nearest relative path from an input path to a dictionary of paths.

    If ``input_path`` is not relative to any of the paths in ``path_dict``,
    the absolute path string is returned.
    If ``input_path`` is already a BIDS-URI, then it will be returned unmodified.

    Parameters
    ----------
    path_dict : dict of (str, Path)
        A dictionary of paths.
    input_path : Path
        The input path to match.

    Returns
    -------
    matching_path : str
        The nearest relative path from the input path to a path in the dictionary.
        This is either the concatenation of the associated key from ``path_dict``
        and the relative path from the associated value from ``path_dict`` to ``input_path``,
        or the absolute path to ``input_path`` if no matching path is found from ``path_dict``.

    Examples
    --------
    >>> from pathlib import Path
    >>> path_dict = {
    ...     'bids::': Path('/data/derivatives/fmriprep'),
    ...     'bids:raw:': Path('/data'),
    ...     'bids:deriv-0:': Path('/data/derivatives/source-1'),
    ... }
    >>> input_path = Path('/data/derivatives/source-1/sub-01/func/sub-01_task-rest_bold.nii.gz')
    >>> _find_nearest_path(path_dict, input_path)  # match to 'bids:deriv-0:'
    'bids:deriv-0:sub-01/func/sub-01_task-rest_bold.nii.gz'
    >>> input_path = Path('/out/sub-01/func/sub-01_task-rest_bold.nii.gz')
    >>> _find_nearest_path(path_dict, input_path)  # no match- absolute path
    '/out/sub-01/func/sub-01_task-rest_bold.nii.gz'
    >>> input_path = Path('/data/sub-01/func/sub-01_task-rest_bold.nii.gz')
    >>> _find_nearest_path(path_dict, input_path)  # match to 'bids:raw:'
    'bids:raw:sub-01/func/sub-01_task-rest_bold.nii.gz'
    >>> input_path = 'bids::sub-01/func/sub-01_task-rest_bold.nii.gz'
    >>> _find_nearest_path(path_dict, input_path)  # already a BIDS-URI
    'bids::sub-01/func/sub-01_task-rest_bold.nii.gz'
    """
    # Don't modify BIDS-URIs
    if isinstance(input_path, str) and input_path.startswith('bids:'):
        return input_path

    input_path = Path(input_path)
    matching_path = None
    for key, path in path_dict.items():
        if input_path.is_relative_to(path):
            relative_path = input_path.relative_to(path)
            if (matching_path is None) or (len(relative_path.parts) < len(matching_path.parts)):
                matching_key = key
                matching_path = relative_path

    if matching_path is None:
        matching_path = str(input_path.absolute())
    else:
        matching_path = f'{matching_key}{matching_path}'

    return matching_path


def _get_bidsuris(in_files, dataset_links, out_dir):
    """Convert input paths to BIDS-URIs using a dictionary of dataset links."""
    in_files = listify(in_files)
    in_files = _ravel(in_files)
    # Remove undefined inputs
    in_files = [f for f in in_files if isdefined(f)]
    # Convert the dataset links to BIDS URI prefixes
    updated_keys = {f'bids:{k}:': Path(v) for k, v in dataset_links.items()}
    updated_keys['bids::'] = Path(out_dir)
    # Convert the paths to BIDS URIs
    out = [_find_nearest_path(updated_keys, f) for f in in_files]
    return out
