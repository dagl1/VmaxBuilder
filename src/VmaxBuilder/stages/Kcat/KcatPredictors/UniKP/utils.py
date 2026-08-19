import hashlib
import sys
import urllib.request
import zipfile
from pathlib import Path

from VmaxBuilder.stages.Kcat.KcatPredictors.UniKP.mock import mock_infer_kcats
from VmaxBuilder.utils.file_handling import get_project_root

external_dir = get_project_root() / "external"
submodule_dir = external_dir / "UniKP"
target_file = submodule_dir / "infer_Kcats.py"
if str(submodule_dir.resolve()) not in sys.path:
    sys.path.insert(0, str(submodule_dir.resolve()))
try:
    # print(f"[VmaxBuilder] Attempting to import UniKP from {submodule_dir}")
    import infer_Kcats as infer_Kcats_module  # ty: ignore

    infer_kcats = infer_Kcats_module.run_kcat_inference_lean

    # print(f"[VmaxBuilder] Successfully imported UniKP from {submodule_dir}")
except (ImportError, ModuleNotFoundError):
    import traceback

    traceback.print_exc()

    print(
        f"[VmaxBuilder] Failed to import UniKP from {submodule_dir}. "
        "Using mock implementation instead."
        "Note that you may need to run `git submodule update --init --recursive` "
        "to fetch the UniKP submodule."
    )
    # diagnose, ensure filepath exist etc.
    print(f"[VmaxBuilder] Checking if {target_file} exists...")
    print(f"[VmaxBuilder] Path exists: {target_file.exists()}")
    print(f"[VmaxBuilder] Path is file: {target_file.is_file()}")
    print(f"[VmaxBuilder] Path is dir: {target_file.is_dir()}")

    infer_Kcats = mock_infer_kcats


def _download_file(  # noqa C901
    url: str,
    target_path: Path,
    *,
    expected_min_size_mb: float,
    expected_md5: str | None = None,
) -> None:
    """Download a file and perform basic sanity checks."""

    target_path.parent.mkdir(parents=True, exist_ok=True)

    print("\nDownloading:")
    print(f"  URL:    {url}")
    print(f"  Target: {target_path}")

    def progress_callback(
        block_num: int,
        block_size: int,
        total_size: int,
    ) -> None:
        downloaded = block_num * block_size

        if total_size > 0:
            percent = min(100.0, downloaded * 100 / total_size)
            print(
                f"\r  Progress: {percent:6.2f}% "
                f"({downloaded / 1024**2:.1f} MB / "
                f"{total_size / 1024**2:.1f} MB)",
                end="",
            )
        else:
            print(
                f"\r  Downloaded: {downloaded / 1024**2:.1f} MB",
                end="",
            )

    # Download to a temporary file first so a failed download doesn't leave
    # a corrupt model at the final path.
    temp_path = target_path.with_suffix(target_path.suffix + ".download")

    if temp_path.exists():
        temp_path.unlink()

    try:
        urllib.request.urlretrieve(
            url,
            str(temp_path),
            reporthook=progress_callback,
        )

        print()

    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    if not temp_path.exists():
        raise RuntimeError(f"Download reported success, but no file was created: {temp_path}")

    file_size = temp_path.stat().st_size
    min_size = expected_min_size_mb * 1024**2

    if file_size < min_size:
        temp_path.unlink()

        raise RuntimeError(
            f"Downloaded file is suspiciously small.\n"
            f"  URL: {url}\n"
            f"  Size: {file_size / 1024:.1f} KB\n"
            f"  Expected at least: {expected_min_size_mb:.1f} MB\n"
            f"This is probably an HTML/error response rather than the model."
        )

    # Optional MD5 validation.
    if expected_md5 is not None:
        print("  Calculating MD5...")

        md5 = hashlib.md5()

        with temp_path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                md5.update(chunk)

        actual_md5 = md5.hexdigest()

        if actual_md5.lower() != expected_md5.lower():
            temp_path.unlink()

            raise RuntimeError(
                f"MD5 checksum mismatch for {target_path.name}.\n"
                f"  Expected: {expected_md5}\n"
                f"  Actual:   {actual_md5}"
            )

        print("  MD5: OK")

    temp_path.replace(target_path)

    print(f"[Success] {target_path.name} ({file_size / 1024**2:.1f} MB)")


def _extract_zip(
    zip_path: Path,
    target_dir: Path,
) -> None:
    """Extract a ZIP archive into target_dir."""

    print(f"\nExtracting {zip_path.name}...")

    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(target_dir)

    print(f"[Success] Extracted ProtT5 model to {target_dir}")


def setup_vmaxbuilder_dependencies() -> bool:  # Noqa C901
    # ------------------------------------------------------------------
    # 1. Locate UniKP submodule
    # ------------------------------------------------------------------

    root = get_project_root()
    submodule_path = root / "external" / "UniKP"
    installed_something = False

    if not submodule_path.exists() or not any(submodule_path.iterdir()):
        print("=" * 70)
        print("ERROR: UniKP submodule folder is missing or empty.")
        print("=" * 70)
        print("Please run:")
        print()
        print("  git submodule update --init --recursive")
        print()
        print("=" * 70)
        sys.exit(1)

    submodule_str = str(submodule_path)

    if submodule_str not in sys.path:
        sys.path.append(submodule_str)

    # ------------------------------------------------------------------
    # 2. Paths
    # ------------------------------------------------------------------

    unikp_model_dir = submodule_path / "models"

    prot_t5_model_dir = submodule_path / "pretrained_models" / "prot_t5_xl_uniref50"

    # ------------------------------------------------------------------
    # 3. Actual UniKP model URLs
    #
    # Hugging Face supports /resolve/main/<filename>
    # ------------------------------------------------------------------

    download_targets = {
        "UniKP kcat Model": {
            "local_path": unikp_model_dir / "kcat" / "UniKP for kcat.pkl",
            "url": (
                "https://huggingface.co/HanselYu/UniKP/"
                "resolve/main/UniKP%20for%20kcat.pkl?download=true"
            ),
            "expected_min_size_mb": 100,  # we need to ignore secrets
            "expected_md5": "bf4e2c87deec0da8359ecb767e562bf2",  # pragma: allowlist secret
        },
        "UniKP Km Model": {
            "local_path": unikp_model_dir / "Km" / "UniKP for Km.pkl",
            "url": (
                "https://huggingface.co/HanselYu/UniKP/"
                "resolve/main/UniKP%20for%20Km.pkl?download=true"
            ),
            "expected_min_size_mb": 100,
            "expected_md5": "3e5e29dfabb0648448cb2fcd6f7cedd5",  # pragma: allowlist secret
        },
        "UniKP kcat/Km Model": {
            "local_path": (unikp_model_dir / "kcat_Km" / "UniKP for kcat_Km.pkl"),
            "url": (
                "https://huggingface.co/HanselYu/UniKP/"
                "resolve/main/UniKP%20for%20kcat_Km.pkl?download=true"
            ),
            "expected_min_size_mb": 5,
            "expected_md5": "bc598e880e0893bf25f8bfb27074ccac",  # pragma: allowlist secret
        },
    }

    # ------------------------------------------------------------------
    # 4. ProtT5 model
    #
    # Zenodo provides the complete model as one 5.3 GB ZIP.
    # ------------------------------------------------------------------

    prot_t5_zip = submodule_path / "pretrained_models" / "prot_t5_xl_uniref50.zip"

    prot_t5_target = {
        "ProtT5-XL-UniRef50 Model": {
            "local_path": prot_t5_zip,
            "url": (
                "https://zenodo.org/records/4644188/files/prot_t5_xl_uniref50.zip?download=1"
            ),
            "expected_min_size_mb": 5000,
            "expected_md5": "ab11a7eddfbaff5784effd41380b482a",  # pragma: allowlist secret
        }
    }

    # ------------------------------------------------------------------
    # 5. Determine missing assets
    # ------------------------------------------------------------------

    missing_assets = {
        name: info
        for name, info in {
            **download_targets,
            **prot_t5_target,
        }.items()
        if not info["local_path"].exists()  # ty: ignore
    }

    # Check whether the extracted ProtT5 directory already exists.
    prot_t5_already_extracted = prot_t5_model_dir.exists() and any(
        prot_t5_model_dir.iterdir()
    )

    if "ProtT5-XL-UniRef50 Model" in missing_assets:
        if prot_t5_already_extracted:
            # Don't download the 5.3 GB archive if the model is already
            # extracted.
            del missing_assets["ProtT5-XL-UniRef50 Model"]

    # ------------------------------------------------------------------
    # 6. Nothing missing
    # ------------------------------------------------------------------

    if not missing_assets:
        return installed_something
        print("[VmaxBuilder] All UniKP and ProtT5 model assets are already present.")

    # ------------------------------------------------------------------
    # 7. Ask user
    # ------------------------------------------------------------------

    print("\n[VmaxBuilder] Missing ML model assets:")

    for name, info in missing_assets.items():
        print(f"  - {name}\n    {info['local_path']}")

    print()

    user_choice = (
        input("Would you like to download these models automatically? (y/n): ")
        .strip()
        .lower()
    )

    if user_choice not in {"y", "yes"}:
        print("\n[Cancelled] VmaxBuilder requires these model assets.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 8. Configure HTTP client
    # ------------------------------------------------------------------

    opener = urllib.request.build_opener()

    opener.addheaders = [
        (
            "User-Agent",
            "VmaxBuilder/1.0 (https://github.com/HanselYu/UniKP)",
        )
    ]

    urllib.request.install_opener(opener)

    # ------------------------------------------------------------------
    # 9. Download UniKP models
    # ------------------------------------------------------------------

    for name, info in download_targets.items():
        target_path = info["local_path"]
        if not isinstance(target_path, Path):
            target_path = Path(str(target_path))

        if target_path.exists():
            print(f"\n[Already present] {target_path}")
            continue

        print(f"\nFetching {name}...")

        try:
            _download_file(
                url=str(info["url"]),
                target_path=target_path,
                expected_min_size_mb=info["expected_min_size_mb"],  # ty: ignore
                expected_md5=str(info["expected_md5"]),
            )

        except Exception as e:
            print(f"\n[Error] Failed downloading {name}:\n{e}")
            sys.exit(1)

    # ------------------------------------------------------------------
    # 10. Download ProtT5 ZIP
    # ------------------------------------------------------------------

    if not prot_t5_already_extracted:
        info = prot_t5_target["ProtT5-XL-UniRef50 Model"]
        if not isinstance(info["local_path"], Path):
            info["local_path"] = Path(str(info["local_path"]))

        if not prot_t5_zip.exists():
            print("\nFetching ProtT5-XL-UniRef50.")

            try:
                _download_file(
                    url=str(info["url"]),
                    target_path=info["local_path"],
                    expected_min_size_mb=info["expected_min_size_mb"],  # ty: ignore
                    expected_md5=str(info["expected_md5"]),
                )

            except Exception as e:
                print(f"\n[Error] Failed downloading ProtT5:\n{e}")
                sys.exit(1)

        # --------------------------------------------------------------
        # Extract
        # --------------------------------------------------------------

        try:
            _extract_zip(
                zip_path=prot_t5_zip,
                target_dir=prot_t5_model_dir,
            )

        except Exception as e:
            print(f"\n[Error] Failed extracting ProtT5:\n{e}")
            sys.exit(1)

        # The ZIP is no longer necessary after extraction.
        # Keep it if you want caching; otherwise uncomment:
        #
        # prot_t5_zip.unlink()

    # ------------------------------------------------------------------
    # 11. Final validation
    # ------------------------------------------------------------------

    print("\n" + "=" * 70)
    print("[VmaxBuilder] Dependency setup complete.")
    print("=" * 70)

    for name, info in download_targets.items():
        path = info["local_path"]
        if not isinstance(path, Path):
            path = Path(str(path))

        if not path.exists():
            raise RuntimeError(f"Expected UniKP model is missing: {path}")

        print(f"  ✓ {name}: {path.stat().st_size / 1024**2:.1f} MB")

    if not prot_t5_model_dir.exists():
        raise RuntimeError(f"ProtT5 directory is missing: {prot_t5_model_dir}")

    print(f"  ✓ ProtT5: {prot_t5_model_dir}")
    print("=" * 70)
    return True


if __name__ == "__main__":
    setup_vmaxbuilder_dependencies()
