from modules.commons.common_layers import *
from modules.commons.common_layers import Embedding
from modules.fastspeech.tts_modules import (
    FastspeechDecoder,
    DurationPredictor,
    LengthRegulator,
    PitchPredictor,
    EnergyPredictor,
    FastspeechEncoder,
)
from utils.cwt import cwt2f0
from utils.hparams import hparams
from utils.pitch_utils import f0_to_coarse, denorm_f0, norm_f0

FS_ENCODERS = {
    "fft": lambda hp: FastspeechEncoder(
        hp["hidden_size"],
        hp["enc_layers"],
        hp["enc_ffn_kernel_size"],
        num_heads=hp["num_heads"],
    ),
}

FS_DECODERS = {
    "fft": lambda hp: FastspeechDecoder(
        hp["hidden_size"], hp["dec_layers"], hp["dec_ffn_kernel_size"], hp["num_heads"]
    ),
}


class FastSpeech2(nn.Module):
    def __init__(self, dictionary, out_dims=None):
        super().__init__()
        self.padding_idx = 0
        if not hparams["no_fs2"] if "no_fs2" in hparams.keys() else True:
            self.enc_layers = hparams["enc_layers"]
            self.dec_layers = hparams["dec_layers"]
            self.encoder = FS_ENCODERS[hparams["encoder_type"]](hparams)
            self.decoder = FS_DECODERS[hparams["decoder_type"]](hparams)
        self.hidden_size = hparams["hidden_size"]
        self.out_dims = out_dims
        if out_dims is None:
            self.out_dims = hparams["audio_num_mel_bins"]
        self.mel_out = Linear(self.hidden_size, self.out_dims, bias=True)
        predictor_hidden = (
            hparams["predictor_hidden"]
            if hparams["predictor_hidden"] > 0
            else self.hidden_size
        )
        if hparams["use_pitch_embed"]:
            self.pitch_embed = Embedding(300, self.hidden_size, self.padding_idx)
            if hparams["pitch_type"] == "cwt":
                h = hparams["cwt_hidden_size"]
                cwt_out_dims = 10
                if hparams["use_uv"]:
                    cwt_out_dims = cwt_out_dims + 1
                self.cwt_predictor = nn.Sequential(
                    nn.Linear(self.hidden_size, h),
                    PitchPredictor(
                        h,
                        n_chans=predictor_hidden,
                        n_layers=hparams["predictor_layers"],
                        dropout_rate=hparams["predictor_dropout"],
                        odim=cwt_out_dims,
                        padding=hparams["ffn_padding"],
                        kernel_size=hparams["predictor_kernel"],
                    ),
                )
                self.cwt_stats_layers = nn.Sequential(
                    nn.Linear(self.hidden_size, h),
                    nn.ReLU(),
                    nn.Linear(h, h),
                    nn.ReLU(),
                    nn.Linear(h, 2),
                )
            else:
                self.pitch_predictor = PitchPredictor(
                    self.hidden_size,
                    n_chans=predictor_hidden,
                    n_layers=hparams["predictor_layers"],
                    dropout_rate=hparams["predictor_dropout"],
                    odim=2 if hparams["pitch_type"] == "frame" else 1,
                    padding=hparams["ffn_padding"],
                    kernel_size=hparams["predictor_kernel"],
                )
        if hparams["use_energy_embed"]:
            self.energy_embed = Embedding(256, self.hidden_size, self.padding_idx)

    def forward(
        self,
        hubert,
        mel2ph=None,
        spk_embed=None,
        ref_mels=None,
        f0=None,
        uv=None,
        energy=None,
        skip_decoder=True,
        spk_embed_dur_id=None,
        spk_embed_f0_id=None,
        infer=False,
        **kwargs
    ):
        ret = {}
        if not hparams["no_fs2"] if "no_fs2" in hparams.keys() else True:
            encoder_out = self.encoder(hubert)  # [B, T, C]
        else:
            encoder_out = hubert
        src_nonpadding = (hubert != 0).any(-1)[:, :, None]

        # add ref style embed
        # Not implemented
        # variance encoder
        var_embed = 0

        # encoder_out_dur denotes encoder outputs for duration predictor
        # in speech adaptation, duration predictor use old speaker embedding
        if hparams["use_spk_embed"]:
            spk_embed_dur = spk_embed_f0 = spk_embed = self.spk_embed_proj(spk_embed)[
                :, None, :
            ]
        elif hparams["use_spk_id"]:
            spk_embed_id = spk_embed
            if spk_embed_dur_id is None:
                spk_embed_dur_id = spk_embed_id
            if spk_embed_f0_id is None:
                spk_embed_f0_id = spk_embed_id
            spk_embed = self.spk_embed_proj(spk_embed_id)[:, None, :]
            spk_embed_dur = spk_embed_f0 = spk_embed
            if hparams["use_split_spk_id"]:
                spk_embed_dur = self.spk_embed_dur(spk_embed_dur_id)[:, None, :]
                spk_embed_f0 = self.spk_embed_f0(spk_embed_f0_id)[:, None, :]
        else:
            spk_embed_dur = spk_embed_f0 = spk_embed = 0

        ret["mel2ph"] = mel2ph

        decoder_inp = F.pad(encoder_out, [0, 0, 1, 0])

        mel2ph_ = mel2ph[..., None].repeat([1, 1, encoder_out.shape[-1]])
        decoder_inp_origin = decoder_inp = torch.gather(
            decoder_inp, 1, mel2ph_
        )  # [B, T, H]

        tgt_nonpadding = (mel2ph > 0).float()[:, :, None]

        # add pitch and energy embed
        pitch_inp = (decoder_inp_origin + var_embed + spk_embed_f0) * tgt_nonpadding
        if hparams["use_pitch_embed"]:
            pitch_inp_ph = (encoder_out + var_embed + spk_embed_f0) * src_nonpadding
            decoder_inp = decoder_inp + self.add_pitch(
                pitch_inp, f0, uv, mel2ph, ret, encoder_out=pitch_inp_ph
            )
        if hparams["use_energy_embed"]:
            decoder_inp = decoder_inp + self.add_energy(pitch_inp, energy, ret)

        ret["decoder_inp"] = decoder_inp = (decoder_inp + spk_embed) * tgt_nonpadding
        if not hparams["no_fs2"] if "no_fs2" in hparams.keys() else True:
            if skip_decoder:
                return ret
            ret["mel_out"] = self.run_decoder(
                decoder_inp, tgt_nonpadding, ret, infer=infer, **kwargs
            )

        return ret

    def add_dur(self, dur_input, mel2ph, hubert, ret):
        src_padding = (hubert == 0).all(-1)
        dur_input = dur_input.detach() + hparams["predictor_grad"] * (
            dur_input - dur_input.detach()
        )
        if mel2ph is None:
            dur, xs = self.dur_predictor.inference(dur_input, src_padding)
            ret["dur"] = xs
            ret["dur_choice"] = dur
            mel2ph = self.length_regulator(dur, src_padding).detach()
        else:
            ret["dur"] = self.dur_predictor(dur_input, src_padding)
        ret["mel2ph"] = mel2ph
        return mel2ph

    def run_decoder(self, decoder_inp, tgt_nonpadding, ret, infer, **kwargs):
        x = decoder_inp  # [B, T, H]
        x = self.decoder(x)
        x = self.mel_out(x)
        return x * tgt_nonpadding

    def cwt2f0_norm(self, cwt_spec, mean, std, mel2ph):
        f0 = cwt2f0(cwt_spec, mean, std, hparams["cwt_scales"])
        f0 = torch.cat([f0] + [f0[:, -1:]] * (mel2ph.shape[1] - f0.shape[1]), 1)
        f0_norm = norm_f0(f0, None, hparams)
        return f0_norm

    def out2mel(self, out):
        return out

    def add_pitch(self, decoder_inp, f0, uv, mel2ph, ret, encoder_out=None):

        decoder_inp = decoder_inp.detach() + hparams["predictor_grad"] * (
            decoder_inp - decoder_inp.detach()
        )

        pitch_padding = mel2ph == 0

        ret["f0_denorm"] = f0_denorm = denorm_f0(
            f0, uv, hparams, pitch_padding=pitch_padding
        )
        if pitch_padding is not None:
            f0[pitch_padding] = 0

        pitch = f0_to_coarse(f0_denorm, hparams)  # start from 0
        ret["pitch_pred"] = pitch.unsqueeze(-1)
        pitch_embedding = self.pitch_embed(pitch)
        return pitch_embedding

    def add_energy(self, decoder_inp, energy, ret):
        decoder_inp = decoder_inp.detach() + hparams["predictor_grad"] * (
            decoder_inp - decoder_inp.detach()
        )
        ret["energy_pred"] = energy
        energy = torch.clamp(energy * 256 // 4, max=255).long()  # energy_to_coarse
        energy_embedding = self.energy_embed(energy)
        return energy_embedding

    @staticmethod
    def mel_norm(x):
        return (x + 5.5) / (6.3 / 2) - 1

    @staticmethod
    def mel_denorm(x):
        return (x + 1) * (6.3 / 2) - 5.5
