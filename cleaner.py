from pathlib import Path
import shutil


def main():
    paths = Path.cwd().rglob("*")
    keywords = {"uv", "run_benchmark.bin", "venv", "egg-info"}

    for path in paths:
        name = path.name
        if any(keyword in name for keyword in keywords):
            if path.is_dir():
                shutil.rmtree(path)
            elif path.is_file():
                path.unlink()


if __name__ == "__main__":
    main()
