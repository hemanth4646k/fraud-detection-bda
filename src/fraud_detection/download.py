from __future__ import annotations

import argparse

from .config import get_settings
from .dataset import download_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the public fraud dataset.")
    parser.add_argument("--force", action="store_true", help="Re-download even if file exists.")
    args = parser.parse_args()

    settings = get_settings()
    settings.ensure_local_dirs()
    output_path = download_dataset(
        dataset_url=settings.dataset_url,
        output_path=settings.raw_data_path,
        force=args.force,
    )
    print(f"Dataset ready at: {output_path}")


if __name__ == "__main__":
    main()
