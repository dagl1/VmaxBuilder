import hashlib
import logging
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

import requests
from tqdm import tqdm

from VmaxBuilder.stages.Kcat.KcatPredictors.UniKP.mock import mock_infer_kcats
from VmaxBuilder.utils.file_handling import get_project_root

logger = logging.getLogger(__name__)


logger = logging.getLogger(__name__)
PROT_T5_REQUIRED_FILES = {
    "config.json",
    "pytorch_model.bin",
    "spiece.model",
}

# ------------------------------------------------------------------
# Locate the actual UniKP source directory
# ------------------------------------------------------------------

project_root = get_project_root()
unikp_dir = project_root / "external" / "UniKP"

if not unikp_dir.is_dir():
    raise RuntimeError(f"UniKP directory not found: {unikp_dir}")

# UniKP uses legacy imports such as:
#
#     import build_vocab
#     import pretrain_trfm
#     import utils
#
# Therefore the UniKP directory itself MUST be on sys.path.
unikp_dir_str = str(unikp_dir.resolve())
unikp_parent_dir_str = str(unikp_dir.parent.resolve())

if unikp_dir_str not in sys.path:
    sys.path.insert(0, unikp_dir_str)
if unikp_parent_dir_str not in sys.path:
    sys.path.insert(0, unikp_parent_dir_str)


# ------------------------------------------------------------------
# Import UniKP
# ------------------------------------------------------------------

try:
    import infer_Kcats as infer_Kcats_module  # ty: ignore

    infer_kcats = infer_Kcats_module.run_kcat_inference_lean

    # print(f"[VmaxBuilder] Successfully imported UniKP from {submodule_dir}")

except (ImportError, ModuleNotFoundError):
    import traceback

    traceback.print_exc()

    print(
        f"[VmaxBuilder] Failed to import UniKP from {unikp_dir_str}. "
        "Using mock implementation instead."
        "Note that you may need to run `git submodule update --init --recursive` "
        "to fetch the UniKP submodule."
    )
    # diagnose, ensure filepath exist etc.

    infer_Kcats = mock_infer_kcats


def ensure_prot_t5_model(
    *,
    zip_path: Path,
    model_dir: Path,
    url: str,
    expected_md5: str,
    expected_min_size_mb: float = 5000,
) -> Path:
    """Ensure that a complete local ProtT5 model is available."""

    # Already extracted and complete.
    if is_prot_t5_model_complete(model_dir):
        logger.info("ProtT5 model already available at %s", model_dir)
        return model_dir

    # Download ZIP if necessary.
    if not zip_path.exists():
        _download_file(
            url,
            zip_path,
            expected_md5=expected_md5,
            expected_min_size_mb=expected_min_size_mb,
        )
    else:
        # Validate an existing ZIP too.
        if zip_path.stat().st_size < expected_min_size_mb * 1024**2:
            logger.warning("Existing ProtT5 ZIP appears incomplete; re-downloading.")
            zip_path.unlink()

            _download_file(
                url,
                zip_path,
                expected_md5=expected_md5,
                expected_min_size_mb=expected_min_size_mb,
            )

    # Validate the ZIP itself.
    if not zipfile.is_zipfile(zip_path):
        zip_path.unlink(missing_ok=True)

        _download_file(
            url,
            zip_path,
            expected_md5=expected_md5,
            expected_min_size_mb=expected_min_size_mb,
        )

    # Extract into a temporary directory.
    extraction_dir = model_dir.with_name(f"{model_dir.name}.tmp")

    if extraction_dir.exists():
        shutil.rmtree(extraction_dir)

    extraction_dir.mkdir(parents=True)

    logger.info("Extracting ProtT5 model from %s", zip_path)

    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(extraction_dir)

    # Handle ZIPs that contain a top-level directory.
    candidates = [
        extraction_dir,
        *[path for path in extraction_dir.iterdir() if path.is_dir()],
    ]

    source_dir = next(
        (path for path in candidates if is_prot_t5_model_complete(path)),
        None,
    )

    if source_dir is None:
        shutil.rmtree(extraction_dir)

        raise RuntimeError(
            "ProtT5 archive was downloaded/extracted, but the expected "
            "HuggingFace model files were not found."
        )

    if model_dir.exists():
        shutil.rmtree(model_dir)

    shutil.move(str(source_dir), str(model_dir))

    # Clean up temporary extraction directory.
    if extraction_dir.exists():
        shutil.rmtree(extraction_dir)

    if not is_prot_t5_model_complete(model_dir):
        raise RuntimeError(f"ProtT5 model extraction appears incomplete: {model_dir}")

    logger.info("ProtT5 model ready at %s", model_dir)


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
    if "zenodo" in url:
        print(
            "Note: This file is hosted on Zenodo and may take a while to download.\n"
            "Alternatively, you can download it manually from the following URL"
            "and place it at the target path:\n"
        )
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


def is_prot_t5_model_complete(model_dir: Path) -> bool:
    """Return True if the local ProtT5 model appears complete."""

    if not model_dir.is_dir():
        return False

    return all((model_dir / filename).is_file() for filename in PROT_T5_REQUIRED_FILES)


def setup_vmaxbuilder_dependencies() -> bool:  # noqa: C901
    # ------------------------------------------------------------------
    # 1. Locate UniKP submodule
    # ------------------------------------------------------------------
    root = get_project_root()
    submodule_path = root / "external" / "UniKP"

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

    prot_t5_zip = submodule_path / "pretrained_models" / "prot_t5_xl_uniref50.zip"

    # ------------------------------------------------------------------
    # 3. UniKP model definitions
    # ------------------------------------------------------------------

    download_targets = {
        "UniKP kcat Model": {
            "local_path": unikp_model_dir / "kcat" / "UniKP for kcat.pkl",
            "url": (
                "https://huggingface.co/HanselYu/UniKP/"
                "resolve/main/UniKP%20for%20kcat.pkl?download=true"
            ),
            "expected_min_size_mb": 100,
            "expected_md5": "bf4e2c87deec0da8359ecb767e562bf2",  # pragma: allowlist secret
        },
        "UniKP Km Model": {
            "local_path": unikp_model_dir / "Km" / "UniKP for Km.pkl",
            "url": (
                "https://huggingface.co/HanselYu/UniKP/"
                "resolve/main/UniKP%20for%20Km.pkl?download=true"  # pragma: allowlist secret
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
    # 4. ProtT5 definition
    # ------------------------------------------------------------------

    PROT_T5_URL = (
        "https://zenodo.org/records/4644188/files/prot_t5_xl_uniref50.zip?download=1"
    )

    PROT_T5_MD5 = "ab11a7eddfbaff5784effd41380b482a"  # pragma: allowlist secret
    PROT_T5_MIN_SIZE_MB = 5000

    # ------------------------------------------------------------------
    # 5. Determine what is missing
    # ------------------------------------------------------------------

    missing_unikp_assets = {}

    for name, info in download_targets.items():
        local_path = info["local_path"]

        if (
            not local_path.exists()
            or local_path.stat().st_size < info["expected_min_size_mb"] * 1024**2
        ):
            missing_unikp_assets[name] = info

    prot_t5_missing = not is_prot_t5_model_complete(prot_t5_model_dir)

    # Nothing needs to be installed.
    if not missing_unikp_assets and not prot_t5_missing:
        logger.info("[VmaxBuilder] All UniKP and ProtT5 model assets are already present.")
        return False

    # ------------------------------------------------------------------
    # 6. Tell the user what is missing
    # ------------------------------------------------------------------

    print("\n[VmaxBuilder] Missing ML model assets:")

    for name, info in missing_unikp_assets.items():
        print(f"  - {name}")
        print(f"    {info['local_path']}")

    if prot_t5_missing:
        print("  - ProtT5-XL-UniRef50 Model")
        print(f"    {prot_t5_model_dir}")

    print()

    user_choice = (
        input("Would you like to download the missing models automatically? (y/n): ")
        .strip()
        .lower()
    )

    if user_choice not in {"y", "yes"}:
        print("\n[Cancelled] VmaxBuilder requires these model assets.")
        sys.exit(1)

    installed_something = False

    # ------------------------------------------------------------------
    # 7. Download missing UniKP models
    # ------------------------------------------------------------------

    for name, info in missing_unikp_assets.items():
        logger.info("Downloading %s", name)

        try:
            _download_file(
                url=str(info["url"]),
                destination=Path(info["local_path"]),
                expected_md5=str(info["expected_md5"]),
                expected_min_size_mb=float(info["expected_min_size_mb"]),
            )
        except Exception as e:
            raise RuntimeError(f"Failed downloading {name}: {e}") from e

        installed_something = True

    # ------------------------------------------------------------------
    # 8. Download and extract ProtT5 if necessary
    # ------------------------------------------------------------------

    if prot_t5_missing:
        try:
            ensure_prot_t5_model(
                zip_path=prot_t5_zip,
                model_dir=prot_t5_model_dir,
                url=PROT_T5_URL,
                expected_md5=PROT_T5_MD5,
                expected_min_size_mb=PROT_T5_MIN_SIZE_MB,
            )
        except Exception as e:
            raise RuntimeError(f"Failed installing ProtT5-XL-UniRef50: {e}") from e

        installed_something = True

    # ------------------------------------------------------------------
    # 9. Final validation
    # ------------------------------------------------------------------

    validation_errors = []

    for name, info in download_targets.items():
        path = Path(info["local_path"])

        if not path.exists() or path.stat().st_size < info["expected_min_size_mb"] * 1024**2:
            validation_errors.append(f"{name}: {path}")

    if not is_prot_t5_model_complete(prot_t5_model_dir):
        validation_errors.append(f"ProtT5-XL-UniRef50: {prot_t5_model_dir}")

    if validation_errors:
        raise RuntimeError(
            "Dependency installation completed, but the following "
            "assets are still missing or incomplete:\n"
            + "\n".join(f"  - {error}" for error in validation_errors)
        )

    # ------------------------------------------------------------------
    # 10. Report success
    # ------------------------------------------------------------------

    print("\n" + "=" * 70)
    print("[VmaxBuilder] Dependency setup complete.")
    print("=" * 70)

    for name, info in download_targets.items():
        path = Path(info["local_path"])
        print(f"  ✓ {name}: {path.stat().st_size / 1024**2:.1f} MB")

    print(f"  ✓ ProtT5: {prot_t5_model_dir}")
    print("=" * 70)

    return installed_something


if __name__ == "__main__":
    setup_vmaxbuilder_dependencies()
