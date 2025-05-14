import pickle

import numpy as np

CHARACTERS = [
    "hski",
    "ttmr",
    "fktn",
    "amao",
    "kllj",
    "kcna",
    "ssmk",
    "shro",
    "hrnm",
]


if __name__ == "__main__":
    for c in CHARACTERS:

        data_c = pickle.load(open(f"gkms{c}_crepe.pkl", "rb"))
        data_p = pickle.load(open(f"gkms{c}_parselmouth.pkl", "rb"))

        metadata = data_c["metadata"]
        assert (metadata == data_p["metadata"]).all().all()

        assert data_c["pitch"].max() <= 255
        assert data_c["pitch"].min() >= 0
        assert data_p["pitch"].max() <= 255
        assert data_p["pitch"].min() >= 0
        assert (data_c["spec_min"] == data_p["spec_min"]).all()
        assert (data_c["spec_max"] == data_p["spec_max"]).all()

        assert data_c["mel2ph"].max() <= 65535
        assert data_c["mel2ph"].min() >= 0
        assert (data_c["mel"] == data_p["mel"]).all()
        assert (data_c["mel2ph"] == data_p["mel2ph"]).all()
        assert (data_c["hubert"] == data_p["hubert"]).all()

        data = {
            "pitch_crepe": data_c["pitch"].astype("uint8"),
            "pitch_parselmouth": data_p["pitch"].astype("uint8"),
            "f0_crepe": data_c["f0"],
            "f0_parselmouth": data_p["f0"],
            "spec_min": data_c["spec_min"],
            "spec_max": data_c["spec_max"],
            "mel": data_c["mel"],
            "mel2ph": data_c["mel2ph"].astype("uint16"),
            "hubert": data_c["hubert"],
        }

        metadata.to_csv(f"gkms{c}.csv")
        np.savez_compressed(f"gkms{c}.npz", **data)

        print(f"Repacked gkms{c}")
