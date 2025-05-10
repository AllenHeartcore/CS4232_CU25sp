import asyncio
import os
from pathlib import Path

import ffmpeg

TARGET_DIR = Path("data/raw/")


async def resample_task(p: Path):
    temp = p.with_name(f"{p.stem}_44100{p.suffix}")
    await asyncio.to_thread(
        ffmpeg.input(str(p)).output(str(temp), ar=44100).run,
        quiet=True,
    )
    os.replace(temp, p)
    print(f"Processed {p}")


async def main():
    await asyncio.gather(
        *[resample_task(p) for p in TARGET_DIR.rglob("*.wav")],
    )


if __name__ == "__main__":
    asyncio.run(main())
