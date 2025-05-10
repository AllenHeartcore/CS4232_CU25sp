set PYTHONPATH=.
set CUDA_VISIBLE_DEVICES=0 

for %%a in (hski ttmr fktn amao kllj ssmk shro kcna hrnm) do (
    python preprocessing/binarize.py --config training/config_%%a.yaml
)

pause