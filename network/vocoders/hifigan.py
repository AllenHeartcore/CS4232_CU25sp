import glob
import json
import os
import re

import librosa
import torch

import utils
from modules.hifigan.hifigan import HifiGanGenerator
from utils.hparams import hparams, set_hparams
from network.vocoders.base_vocoder import register_vocoder
from network.vocoders.pwg import PWG
from network.vocoders.vocoder_utils import denoise


def load_model(config_path, file_path):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ext = os.path.splitext(file_path)[-1]
    if ext == ".pth":
        if ".yaml" in config_path:
            config = set_hparams(config_path, global_hparams=False)
        elif ".json" in config_path:
            config = json.load(open(config_path, "r", encoding="utf-8"))
        model = torch.load(file_path, map_location="cpu")
    elif ext == ".ckpt":
        ckpt_dict = torch.load(file_path, map_location="cpu")
        if ".yaml" in config_path:
            config = set_hparams(config_path, global_hparams=False)
            state = ckpt_dict["state_dict"]["model_gen"]
        elif ".json" in config_path:
            config = json.load(open(config_path, "r", encoding="utf-8"))
            state = ckpt_dict["generator"]
        model = HifiGanGenerator(config)
        model.load_state_dict(state, strict=True)
        model.remove_weight_norm()
    model = model.eval().to(device)
    print(f"| Loaded model parameters from {file_path}.")
    print(f"| HifiGAN device: {device}.")
    return model, config, device


total_time = 0


@register_vocoder
class HifiGAN(PWG):
    def __init__(self):
        base_dir = hparams["vocoder_ckpt"]
        config_path = f"{base_dir}/config.yaml"
        if os.path.exists(config_path):
            file_path = sorted(
                glob.glob(f"{base_dir}/model_ckpt_steps_*.*"),
                key=lambda x: int(
                    re.findall(
                        f"{base_dir}/model_ckpt_steps_(\d+).*", x.replace("\\", "/")
                    )[0]
                ),
            )[-1]
            print("| load HifiGAN: ", file_path)
            self.model, self.config, self.device = load_model(
                config_path=config_path, file_path=file_path
            )
        else:
            config_path = f"{base_dir}/config.json"
            ckpt = f"{base_dir}/generator_v1"
            if os.path.exists(config_path):
                self.model, self.config, self.device = load_model(
                    config_path=config_path, file_path=file_path
                )

    def spec2wav(self, mel, **kwargs):
        device = self.device
        with torch.no_grad():
            c = torch.FloatTensor(mel).unsqueeze(0).transpose(2, 1).to(device)
            with utils.Timer("hifigan", print_time=hparams["profile_infer"]):
                f0 = kwargs.get("f0")
                if f0 is not None and hparams.get("use_nsf"):
                    f0 = torch.FloatTensor(f0[None, :]).to(device)
                    y = self.model(c, f0).view(-1)
                else:
                    y = self.model(c).view(-1)
        wav_out = y.cpu().numpy()
        if hparams.get("vocoder_denoise_c", 0.0) > 0:
            wav_out = denoise(wav_out, v=hparams["vocoder_denoise_c"])
        return wav_out
