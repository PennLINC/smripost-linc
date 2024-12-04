.. include:: links.rst

.. _outputs:

##########################
Outputs of *sMRIPost-LINC*
##########################

*sMRIPost-LINC* outputs conform to the :abbr:`BIDS (brain imaging data structure)`
Derivatives specification (see `BIDS Derivatives`_, along with the
upcoming `BEP 011`_ and `BEP 012`_).
*sMRIPost-LINC* generates three broad classes of outcomes:

1.  **Visual QA (quality assessment) reports**:
    One :abbr:`HTML (hypertext markup language)` per subject,
    that allows the user a thorough visual assessment of the quality
    of processing and ensures the transparency of *sMRIPost-LINC* operation.

2.  **Atlases**:
    Atlases selected by the user are warped to fsaverage space and converted to
    Freesurfer ``.annot`` format.

3.  **Parcellated structural measures**:
    Anatomical measures are summarized by region of interest (ROI) from each of the atlases.

4.  **Confounds**:
    Some confound values, including Euler numbers, are saved in a TSV file.


******
Layout
******

Assuming sMRIPost-LINC is invoked with::

    smripost_linc <input_dir>/ <output_dir>/ participant [OPTIONS]

The outputs will be a `BIDS Derivatives`_ dataset of the form::

    <output_dir>/
      logs/
      atlases/
      sub-<label>/
      sub-<label>.html
      dataset_description.json
      .bidsignore

For each participant in the dataset,
a directory of derivatives (``sub-<label>/``)
and a visual report (``sub-<label>.html``) are generated.
The log directory contains `citation boilerplate`_ text.
``dataset_description.json`` is a metadata file in which sMRIPost-LINC
records metadata recommended by the BIDS standard.


**************
Visual Reports
**************

*sMRIPost-LINC* outputs summary reports,
written to ``<output dir>/smripost_linc/sub-<label>.html``.
These reports provide a quick way to make visual inspection of the results easy.


*************************
Parcellations and Atlases
*************************

*XCP-D* produces parcellated anatomical and functional outputs using a series of atlases.
The individual outputs are documented in the relevant sections of this document,
with this section describing the atlases themselves.

The atlases currently used in *XCP-D* can be separated into three groups: subcortical, cortical,
and combined cortical/subcortical.
The two subcortical atlases are the Tian atlas :footcite:p:`tian2020topographic` and the
CIFTI subcortical parcellation :footcite:p:`glasser2013minimal`.
The cortical atlases are the Glasser :footcite:p:`Glasser_2016`, the
Gordon :footcite:p:`Gordon_2014`,
the MIDB precision brain atlas derived from ABCD data and thresholded at 75% probability
:footcite:p:`hermosillo2022precision`,
and the Myers-Labonte infant atlas thresholded at 50% probability :footcite:`myers2023functional`.
The combined cortical/subcortical atlases are 10 different resolutions of the
4S (Schaefer Supplemented with Subcortical Structures) atlas.

The 4S atlas combines the Schaefer 2018 cortical atlas (version v0143) :footcite:p:`Schaefer_2017`
at 10 different resolutions (100, 200, 300, 400, 500, 600, 700, 800, 900, and 1000 parcels) with
the CIT168 subcortical atlas :footcite:p:`pauli2018high`,
the Diedrichson cerebellar atlas :footcite:p:`king2019functional`,
the HCP thalamic atlas :footcite:p:`najdenovska2018vivo`,
and the amygdala and hippocampus parcels from the HCP CIFTI subcortical parcellation
:footcite:p:`glasser2013minimal`.
The 4S atlas is used in the same manner across three PennLINC BIDS Apps:
*XCP-D*, QSIPrep_, and ASLPrep_, to produce synchronized outputs across modalities.
For more information about the 4S atlas, please see https://github.com/PennLINC/AtlasPack.

.. tip::

   You can choose to only use a subset of the available atlases by using the ``--atlases``
   parameter.

fsaverage-space atlases are written out to the ``atlases`` subfolder, following BEP038.
fsnative-space atlases are written out to the subject directory.

.. code-block::

   <output_dir>/
      atlases/
         dataset_description.json
         atlas-<label>/
            atlas-<label>_hemi-<L|R>_space-fsaverage_dseg.annot
            atlas-<label>_dseg.json
            atlas-<label>_dseg.tsv
      sub-<label>/[ses-<label>/]
         anat/
            sub-<label>[_ses-<label>]_hemi-<L|R>_space-fsnative_seg-<atlas>_dseg.annot
            sub-<label>[_ses-<label>]_hemi-<L|R>_space-fsnative_seg-<atlas>_dseg.json


*******************************
Parcellated Structural Measures
*******************************

*sMRIPost-LINC* outputs a set of parcellated structural measures.


*********
Confounds
*********

*sMRIPost-LINC* outputs a set of confounds that can be used to summarize data quality.
