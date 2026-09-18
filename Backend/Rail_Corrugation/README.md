# Rail Corrugation

Start with [Rail_Corrugation.ipynb](Rail_Corrugation.ipynb). It is the main, self-contained notebook for EDA, feature extraction, baseline comparisons, error analysis, refinement, and model selection.

## Run it

1. Put the supplied `Train/` folder and `Train_Labels.csv` in `Dataset/`.
2. Open `Rail_Corrugation.ipynb` in VS Code or Jupyter and select a Python kernel.
3. Use **Restart Kernel and Run All**. The first scan reads about 4.38 GB one file at a time; allow a few minutes for extraction and validation.

Dependencies: NumPy, pandas, SciPy, matplotlib, seaborn, scikit-learn, and a notebook kernel such as ipykernel. The notebook prints package versions for reproducibility. Its calculations use `numpy.trapezoid`, available in NumPy 2 and later.

The notebook contains all its own functions. It does not need separate helper modules or cached results. It reads only labelled training recordings and ends at model selection; final model saving, the web app, and submission export are the next stage.

## Previous work

The previous numbered notebooks, helper modules, tests, and cached experiment results were archived locally in `.archive/legacy_before_cleanup.zip` before cleanup. The archive is ignored by Git and is not required to run the consolidated notebook. Extract it into a separate folder if you need to review the earlier work.

Six representative experiments in the consolidated notebook reproduce the main comparisons. The archived notebooks retain the full set of earlier experiments, including rejected approaches.
