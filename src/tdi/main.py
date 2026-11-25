
import argparse
from pathlib import Path
import sys
from pdf_extractor import extract_dataset
from section_retrieval import metadata_retrieval
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def load_config():
    """Load project configuration from settings.yaml."""

    config_path = PROJECT_ROOT / "config" / "settings.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise ValueError("Invalid configuration file.")

    return config


def project_info(config, debug: bool = False):
    dataset_dir = PROJECT_ROOT / config["paths"]["dataset"]
    if debug:
        print(f"Project root: {PROJECT_ROOT}")
        print("Dataset Path [FOUND!]:")

    for category in config["dataset"]["categories"]:
        category_dir = dataset_dir / category

        if not category_dir.exists():
            raise FileNotFoundError(f"Category directory not found: {category_dir}")

        if debug:
            print("=" * 50)
            print(f"Category: {category}, Path: [FOUND!]")
            pdf_files = [
                file for file in category_dir.rglob("*")
                if file.is_file() and file.suffix.lower() == ".pdf"
            ]
            print(f"Number of PDF files in '{category}': {len(pdf_files)}")

    summary = extract_dataset(
        dataset_dir=dataset_dir,
        categories=config["dataset"]["categories"],
        project_root=PROJECT_ROOT,
        debug=debug,
    )
    output_dir = summary.get("Output_directory")

    if not isinstance(output_dir, (str, Path)):
        raise ValueError("Dataset extraction did not provide a valid output directory")

    output_dir = Path(output_dir)
    return output_dir, summary


def main(debug: bool = False):
    """Application entry point."""
    print(f"debug is {debug}")
    try:
        config = load_config()
        project = config["project"]

        if debug:
            print("=" * 50)
            print(project["name"])
            print(f"Version: {project['version']}")
            print(f"Author: {project['author']}")
            print("=" * 50)

        output_dir, summary = project_info(config, debug=debug)
        documents = metadata_retrieval(metadata_dir = output_dir, categories=config["dataset"]["categories"])
        if debug:
            print(f"MetaData retrieved: {len(documents)}\n")


    except (FileNotFoundError, ValueError, KeyError, TypeError, yaml.YAMLError) as error:
        if debug:
            print(f"\n[ERROR] {error}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Display progress and diagnostic messages.",
    )
    args = parser.parse_args()
    if len(sys.argv) == 1:
        choice = input("Type 'debug' or press Enter for normal: ").strip().lower()
        debug_mode = (choice == "debug")
    else:
        debug_mode = args.debug

    main(debug=debug_mode)
