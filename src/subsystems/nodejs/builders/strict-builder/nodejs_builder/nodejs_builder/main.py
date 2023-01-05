from .lib.checks import check_platform
from .lib.config import node_modules
from .lib.derivation import (
    is_main_package,
    get_outputs,
    get_self,
    InstallMethod,
    get_install_method,
)
from .lib.node_modules import create_node_modules
from .lib.package import get_package_json, has_scripts, get_bins, create_binary
from .lib.dependencies import Dependency
import shutil
import os
from pathlib import Path


def checkPlatform():
    """
    Checks if the package can be installed.
    - platform must have compatible: os + cpu
    """
    if not check_platform():
        exit(3)


def d2nNodeModules():
    """
    generate the node_modules folder.
    - on main packages
    - on packages with scripts that could need them
    """
    package_json = get_package_json()
    if is_main_package() or has_scripts(package_json):
        create_node_modules()


def makeOutputs():
    """
    build the outputs:
    - $lib
    - $out

    > note: with installMethod == "copy" the symlinks sources are copied over.
    > note: binaries always reference their source.

    The following structured outputs are created.

    # package - consumable as bare package
    # containing all files from the source
    $lib:
    /nix/store/...-pname-1.0.0-lib
    ├── ....
    └── package.json

    # standard composition - consumable by most users
    $out:
    /nix/store/...-pname-1.0.0
    ├── bin
    │   └── cli -> ../lib/cli.js
    └── lib
        ├── cli.js -> /nix/store/...-pname-1.0.0-lib/cli.js
        ├── ...
        ├── package.json -> /nix/store/...-pname-1.0.0-lib/package.json
        └── node_modules -> /nix/store/...-pname-1.0.0-deps
    """

    # get the outputs from env ($out, $lib, $deps)
    outputs = get_outputs()

    # create empty deps path for packages without dependencies
    if node_modules.exists():
        # copy the tree and preserve symlinks
        # copytree also checks for dangling symlinks and fails on broken links
        shutil.copytree(node_modules, outputs.deps, symlinks=True)
    else:
        outputs.deps.mkdir(parents=True, exist_ok=True)

    # copy package content only
    # TODO: apply filter logic from npm ('files' entry in package-json)

    # remove the leftover symlink from d2nNodeModules phase
    Path("./node_modules").unlink(missing_ok=True)

    # TODO: run scripts ? (pre-, post-, install scripts)
    shutil.copytree(Path("."), outputs.lib)

    bin_out = outputs.out / Path("bin")
    lib_out = outputs.out / Path("lib")
    bin_out.mkdir(parents=True, exist_ok=True)

    install_method = get_install_method()

    if install_method == InstallMethod.copy:
        shutil.copytree(outputs.lib, lib_out, symlinks=True)
        shutil.copytree(outputs.deps, lib_out / Path("node_modules"), symlinks=True)

    elif install_method == InstallMethod.symlink:
        lib_out.mkdir(parents=True, exist_ok=True)
        for entry in os.listdir(outputs.lib):
            (lib_out / Path(entry)).symlink_to(outputs.lib / Path(entry))

        (lib_out / Path("node_modules")).symlink_to(outputs.deps)

    # create binaries
    pkg = get_self()
    dep = Dependency(name=pkg.name, version=pkg.version, derivation=outputs.lib)
    binaries = get_bins(dep)
    for name, rel_path in binaries.items():
        create_binary(bin_out / Path(name), Path("lib") / rel_path)
