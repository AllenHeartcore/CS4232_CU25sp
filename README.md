# Diff-SVC
Singing Voice Conversion via diffusion model

## Preprocessing
```
export PYTHONPATH=.
CUDA_VISIBLE_DEVICES=0 python preprocessing/binarize.py --config training/config.yaml
```

## Training
```
CUDA_VISIBLE_DEVICES=0 python run.py --config training/config.yaml --exp_name [your project name] --reset 
```
