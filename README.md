# Diff-SVC
Singing Voice Conversion via diffusion model


## Preprocessing
```
export PYTHONPATH=.
CUDA_VISIBLE_DEVICES=0 python preprocessing/binarize.py --config training/config_CHAR.yaml
```

### Utterance Statistics

| Character | # Raw Samples | # Accepted by<br>CREPE | # Accepted by<br>Parselmouth | # Valid Samples | Total Length (s) | # Frames | # Phones |
| - | - | - | - | - | - | - | - |
| hski | 4978 | 4978 | 4938 | 4938 | 17431.678 | 1498962 | 869088 |
| ttmr | 4277 | **4276** | 4209 | **4208** | 14267.206 | 1226786 | 711294 |
| fktn | 4723 | 4723 | 4706 | 4706 | 18315.583 | 1575131 | 913470 |
| amao | 3191 | **3190** | 3177 | 3177 | 11854.865 | 1019499 | 591154 |
| kllj | 3110 | 3110 | 3075 | 3075 | 12964.298 | 1115122 | 646680 |
| kcna | 3650 | 3650 | 3645 | 3645 | 15227.025 | 1309748 | 759557 |
| ssmk | 3255 | 3255 | 3240 | 3240 | 12269.807 | 1055218 | 611846 |
| shro | 3020 | 3020 | 2995 | 2995 | 9210.402 | 791829 | 459046 |
| hrnm | 3294 | 3294 | 3246 | 3246 | 12741.517 | 1095850 | 635436 |


## Training
```
CUDA_VISIBLE_DEVICES=0 python run.py --config training/config.yaml --exp_name [your project name] --reset 
```
