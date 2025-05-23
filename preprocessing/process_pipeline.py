"""
file -> temporary_dict -> processed_input -> batch
"""

from utils.hparams import hparams
from network.vocoders.base_vocoder import VOCODERS
import numpy as np
import traceback
from pathlib import Path
from .data_gen_utils import get_pitch_parselmouth, get_pitch_crepe
from .base_binarizer import BinarizationError
import torch
import utils


class File2Batch:
    """
    pipeline: file -> temporary_dict -> processed_input -> batch
    """

    @staticmethod
    def file2temporary_dict():
        """
        read from file, store data in temporary dicts
        """
        raw_data_dir = Path(hparams["raw_data_dir"])

        utterance_labels = []
        utterance_labels.extend(list(raw_data_dir.rglob(f"*.wav")))
        utterance_labels.extend(list(raw_data_dir.rglob(f"*.ogg")))

        all_temp_dict = {}
        for utterance_label in utterance_labels:
            item_name = str(utterance_label)  # raw_item_name = song_info[0]
            temp_dict = {}
            temp_dict["wav_fn"] = str(
                utterance_label
            )  # f'{raw_data_dir}/wavs/{item_name}.wav'

            temp_dict["spk_id"] = hparams["speaker_id"]

            all_temp_dict[item_name] = temp_dict

        return all_temp_dict

    @staticmethod
    def temporary_dict2processed_input(
        item_name, temp_dict, encoder, binarization_args
    ):
        """
        process data in temporary_dicts
        """

        def get_pitch(wav, mel):
            # get ground truth f0 by self.get_pitch_algorithm
            if hparams["use_crepe"]:
                gt_f0, gt_pitch_coarse = get_pitch_crepe(wav, mel, hparams)
            else:
                gt_f0, gt_pitch_coarse = get_pitch_parselmouth(wav, mel, hparams)
            if sum(gt_f0) == 0:
                raise BinarizationError("Empty **gt** f0")
            processed_input["f0"] = gt_f0
            processed_input["pitch"] = gt_pitch_coarse

        def get_align(
            meta_data,
            mel,
            phone_encoded,
            hop_size=hparams["hop_size"],
            audio_sample_rate=hparams["audio_sample_rate"],
        ):
            mel2ph = np.zeros([mel.shape[0]], int)
            start_frame = 0
            ph_durs = mel.shape[0] / phone_encoded.shape[0]
            if hparams["debug"]:
                print(
                    mel.shape,
                    phone_encoded.shape,
                    mel.shape[0] / phone_encoded.shape[0],
                )
            for i_ph in range(phone_encoded.shape[0]):

                end_frame = int(i_ph * ph_durs + ph_durs + 0.5)
                mel2ph[start_frame : end_frame + 1] = i_ph + 1
                start_frame = end_frame + 1

            processed_input["mel2ph"] = mel2ph

        if hparams["vocoder"] in VOCODERS:
            wav, mel = VOCODERS[hparams["vocoder"]].wav2spec(temp_dict["wav_fn"])
        else:
            wav, mel = VOCODERS[hparams["vocoder"].split(".")[-1]].wav2spec(
                temp_dict["wav_fn"]
            )
        processed_input = {
            "item_name": item_name,
            "mel": mel,
            "wav": wav,
            "sec": len(wav) / hparams["audio_sample_rate"],
            "len": mel.shape[0],
        }
        processed_input = {**temp_dict, **processed_input}  # merge two dicts
        processed_input["spec_min"] = np.min(mel, axis=0)
        processed_input["spec_max"] = np.max(mel, axis=0)
        try:
            if binarization_args["with_f0"]:
                get_pitch(wav, mel)
            if binarization_args["with_hubert"]:
                try:
                    hubert_encoded = processed_input["hubert"] = encoder.encode(
                        temp_dict["wav_fn"]
                    )
                except:
                    traceback.print_exc()
                    raise Exception(f"hubert encode error")
                if binarization_args["with_align"]:
                    get_align(temp_dict, mel, hubert_encoded)
        except Exception as e:
            print(
                f"| Skip item ({e}). item_name: {item_name}, wav_fn: {temp_dict['wav_fn']}"
            )
            return None
        return processed_input

    @staticmethod
    def processed_input2batch(samples):
        """
        Args:
            samples: one batch of processed_input
        NOTE:
            the batch size is controlled by hparams['max_sentences']
        """
        if len(samples) == 0:
            return {}
        id = torch.LongTensor([s["id"] for s in samples])
        item_names = [s["item_name"] for s in samples]
        hubert = utils.collate_2d([s["hubert"] for s in samples], 0.0)
        f0 = utils.collate_1d([s["f0"] for s in samples], 0.0)
        pitch = utils.collate_1d([s["pitch"] for s in samples])
        uv = utils.collate_1d([s["uv"] for s in samples])
        energy = utils.collate_1d([s["energy"] for s in samples], 0.0)
        mel2ph = (
            utils.collate_1d([s["mel2ph"] for s in samples], 0.0)
            if samples[0]["mel2ph"] is not None
            else None
        )
        mels = utils.collate_2d([s["mel"] for s in samples], 0.0)
        hubert_lengths = torch.LongTensor([s["hubert"].shape[0] for s in samples])
        mel_lengths = torch.LongTensor([s["mel"].shape[0] for s in samples])

        batch = {
            "id": id,
            "item_name": item_names,
            "nsamples": len(samples),
            "hubert": hubert,
            "mels": mels,
            "mel_lengths": mel_lengths,
            "mel2ph": mel2ph,
            "energy": energy,
            "pitch": pitch,
            "f0": f0,
            "uv": uv,
        }

        return batch
