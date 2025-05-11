import pickle

import numpy as np
import pandas as pd
from tqdm import tqdm

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

STAT_NAMES = [
    "pitch",
    "f0",
    "spec_min",
    "spec_max",
    "mel",
    "mel2ph",
    "hubert",
]


def read_pickle(file):

    objs = []
    prog = tqdm(desc=f"Reading {file}", unit="item")

    with open(file, "rb") as fin:
        while True:
            try:
                obj = pickle.load(fin)
                objs.append(obj)
                prog.update(1)
            except EOFError:
                break

    prog.close()
    print(f"Read {len(objs)} items from {file}")

    return objs


def consolidate_and_save(objs, file):

    all_stats = {key: [] for key in STAT_NAMES}
    metadata = []

    for obj in objs:

        nframe = obj["len"]
        nphone = obj["mel2ph"].max()

        assert obj["pitch"].shape == (nframe,)
        assert obj["f0"].shape == (nframe,)
        assert obj["spec_min"].shape == (128,)
        assert obj["spec_max"].shape == (128,)
        assert obj["mel"].shape == (nframe, 128)
        assert obj["mel2ph"].shape == (nframe,)
        assert obj["hubert"].shape == (nphone, 256)

        for field in STAT_NAMES:
            all_stats[field].append(obj[field])

        metadata.append(
            {
                "name": obj["item_name"].split("\\")[-1],
                "sec": obj["sec"],
                "nframe": nframe,
                "nphone": nphone,
            }
        )

    result = {"metadata": pd.DataFrame(metadata).set_index("name")}
    for field in STAT_NAMES:
        result[field] = np.concatenate(all_stats[field])

    print(f"Saving {len(objs)} items to {file}")

    with open(file, "wb") as f:
        pickle.dump(result, f)


if __name__ == "__main__":
    for c in CHARACTERS:

        objs_p = read_pickle(f"gkms{c}_parselmouth.data")
        objs_c = read_pickle(f"gkms{c}_crepe.data")

        names_p = set([o["item_name"] for o in objs_p])
        names_c = set([o["item_name"] for o in objs_c])
        valid_names = names_p.intersection(names_c)

        objs_p = list(filter(lambda x: x["item_name"] in valid_names, objs_p))
        consolidate_and_save(objs_p[::-1], f"gkms{c}_parselmouth.pkl")

        objs_c = list(filter(lambda x: x["item_name"] in valid_names, objs_c))
        consolidate_and_save(objs_c[::-1], f"gkms{c}_crepe.pkl")
