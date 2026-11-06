import os
import zipfile

def package_submission(roll_number="230101085"):
    zip_filename = f"{roll_number}.zip"
    print(f"Creating submission package: {zip_filename}...")

    # Exclusions
    exclude_prefixes = [".git", "__pycache__", ".pytest_cache", ".venv", "venv"]
    exclude_extensions = [".pyc", ".pyo", ".bin", ".safetensors", ".pt", ".pth", ".zip"]

    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk("."):
            # Skip excluded dirs
            dirs[:] = [d for d in dirs if not any(d.startswith(ex) for ex in exclude_prefixes)]

            for file in sorted(files):
                # Don't include the zip file inside itself
                if file == zip_filename:
                    continue
                if any(file.endswith(ext) for ext in exclude_extensions):
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, ".")

                # Check if relative path starts with excluded prefix
                if any(rel_path.startswith(ex) for ex in exclude_prefixes):
                    continue

                zipf.write(full_path, rel_path)
                print(f"  Added: {rel_path}")

    zip_size = os.path.getsize(zip_filename)
    print(f"\nSuccessfully created {zip_filename} ({zip_size / 1024 / 1024:.2f} MB)")

if __name__ == "__main__":
    package_submission()
