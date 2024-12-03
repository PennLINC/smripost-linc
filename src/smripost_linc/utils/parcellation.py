"""Utility functions for parcellation."""


def convert_gifti_to_annot(gifti, atlas, hemi, labels_file):
    """Create .annot files from a nifti file and a json file."""
    import os

    import nibabel as nb
    import numpy as np
    import pandas as pd

    labels_df = pd.read_table(labels_file)
    atlas_labels = labels_df['label'].tolist()

    gifti_img = nb.load(gifti)
    colors = _create_colors(len(atlas_labels))

    annot = os.path.abspath(f'{hemi}.{atlas}.annot')
    nb.freesurfer.write_annot(
        annot,
        labels=gifti_img.agg_data().astype(np.int32),
        ctab=colors,
        names=atlas_labels,
        fill_ctab=True,
    )

    return annot


def _create_colors(n_colors):
    """Create RGBT-format colors for annotation files."""
    import numpy as np

    color_set = {(0, 0, 0, 0)}
    while len(color_set) < n_colors:
        new_color = tuple((np.random.rand(3) * 155).astype(np.int32)) + (0,)
        color_set.add(new_color)
    color_mat = np.array(sorted(color_set))
    if color_mat.shape[0] != n_colors:
        raise ValueError(f'Could not generate {n_colors} unique colors.')

    return color_mat
