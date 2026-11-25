
from pathlib import Path
import sys
from pdf_extractor import extract_dataset
from tdi.section_retrieval import metadata_retrieval
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
print("" * 50)
print(f"Project root: {PROJECT_ROOT}")
print("" * 50)


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

def project_info(config):
        dataset_dir = PROJECT_ROOT / config["paths"]["dataset"]
        print(f"Dataset Path [FOUND!]:")
        
        for category in config["dataset"]["categories"]:
            print("=" * 50)
            category_dir = dataset_dir / category
            
            if not category_dir.exists():
                raise FileNotFoundError(f"Category directory not found: {category_dir}")
            
            print(f"Category: {category}, Path: [FOUND!]")
            pdf_files = [file for file in category_dir.rglob("*") 
                        if file.is_file() and file.suffix.lower() == ".pdf"]
            print(f"Number of PDF files in '{category}': {len(pdf_files)}")

        summary = extract_dataset(dataset_dir=dataset_dir, categories=config["dataset"]["categories"], project_root=PROJECT_ROOT, debug=False)
        output_dir = summary.get("Output_directory")

        if not isinstance(output_dir, (str, Path)):
            raise ValueError("Dataset extraction did not provide a valid output directory")

        output_dir = Path(output_dir)
        return output_dir, summary

def main():
    """Application entry point."""

    try:
        config = load_config()
        project = config["project"]

        print("=" * 50)
        print(project["name"])
        print(f"Version: {project['version']}")
        print(f"Author: {project['author']}")
        print("=" * 50)

        output_dir, summary = project_info(config)
        documents = metadata_retrieval(metadata_dir = output_dir, categories=config["dataset"]["categories"])
        print (f"MetaData retrieved: {len(documents)}\n")


    except (FileNotFoundError, ValueError, KeyError, TypeError, yaml.YAMLError) as error:
        print(f"\n[ERROR] {error}")
        sys.exit(1)

if __name__ == "__main__":
    main()