#!/usr/bin/env python3
"""
manifest2kas.py - Convert a Foundries.io LmP `repo` manifest into a KAS project
configuration so a factory layer (e.g. meta-subscriber-overrides) can be built
with `kas` / `kas-container` without the lmp-manifest repo.

What it does
------------
* Parses the android-`repo` XML manifest (following <include>), collecting every
  <remote>, <default> and <project>.
* Reads the manifest's conf/bblayers*.inc (+ bblayers.conf) to learn which
  sub-layer of each repo must be enabled, and turns that into KAS `layers:`.
* Emits a KAS yaml with `repos:`, `machine:`, `distro:`, `target:` and a
  `local_conf_header:` reproducing conf/local.conf and the auto.conf tweaks that
  setup-environment-internal used to generate.
* Makes the factory signing keys optional and configurable via a single
  FACTORY_KEYS_DIR variable (vendored in the layer OR pointed at by an
  environment variable at build time). Optionally patches the factory's
  lmp-factory-custom.inc to use that variable (backwards compatible with the old
  `repo` + setup-environment flow).

The generic dev keys under lmp-manifest/conf/keys are LmP defaults; only the
factory-keys are handled here (per request). See --help.
"""
import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET

LAYER_TOKEN_RE = re.compile(r"\$\{OEROOT\}/layers/([^\s\"\\]+)")


class Project:
    def __init__(self, name, path, url, revision, is_layer):
        self.name = name
        self.path = path          # repo checkout path from manifest (may be None)
        self.url = url
        self.revision = revision
        self.is_layer = is_layer  # path starts with layers/
        self.layers = set()       # sub-layer dirs to enable ('.' == repo root)


def parse_manifest(manifest_dir, top):
    """Parse `top` and every file it <include>s. Returns (remotes, default, projects)."""
    remotes = {}
    default = {}
    projects = {}

    def _parse(fname):
        fpath = os.path.join(manifest_dir, fname)
        root = ET.parse(fpath).getroot()
        for el in root:
            if el.tag == "include":
                _parse(el.attrib["name"])
            elif el.tag == "remote":
                remotes[el.attrib["name"]] = el.attrib["fetch"].rstrip("/")
            elif el.tag == "default":
                default.update(el.attrib)
            elif el.tag == "project":
                projects[el.attrib["name"]] = el.attrib

    _parse(top)
    return remotes, default, projects


def build_projects(remotes, default, raw_projects):
    out = {}
    for name, attrs in raw_projects.items():
        path = attrs.get("path")  # may be None -> repo dir == name
        remote_name = attrs.get("remote", default.get("remote"))
        revision = attrs.get("revision", default.get("revision"))
        fetch = remotes.get(remote_name)
        if fetch is None:
            print(f"WARNING: project {name} has unknown remote {remote_name!r}", file=sys.stderr)
            url = None
        else:
            url = f"{fetch}/{name}"
        is_layer = bool(path) and path.startswith("layers/")
        out[name] = Project(name, path, url, revision, is_layer)
    return out


def layerdir_index(projects):
    """Map the first path segment under 'layers/' -> project name."""
    idx = {}
    for name, p in projects.items():
        if p.is_layer:
            seg = p.path.split("/", 1)[1].split("/")[0]  # layers/<seg>/...
            idx[seg] = name
    return idx


def collect_layers(manifest_dir, projects):
    """Read bblayers*.inc / bblayers.conf, attach enabled sub-layers to projects."""
    conf_dir = os.path.join(manifest_dir, "conf")
    idx = layerdir_index(projects)
    files = []
    if os.path.isdir(conf_dir):
        for f in sorted(os.listdir(conf_dir)):
            if f == "bblayers.conf" or (f.startswith("bblayers") and f.endswith(".inc")):
                files.append(os.path.join(conf_dir, f))
    for fpath in files:
        with open(fpath) as fh:
            for line in fh:
                if line.lstrip().startswith("#"):
                    continue
                for token in LAYER_TOKEN_RE.findall(line):
                    seg = token.split("/")[0]
                    sub = token[len(seg):].lstrip("/") or "."
                    proj = idx.get(seg)
                    if proj is None:
                        print(f"WARNING: layer {token!r} maps to no project", file=sys.stderr)
                        continue
                    projects[proj].layers.add(sub)


def yaml_quote(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def emit_repos(projects, this_repo, lines):
    lines.append("repos:")
    ordered = []
    if this_repo in projects:
        ordered.append(this_repo)
    if "bitbake" in projects:
        ordered.append("bitbake")
    for name in sorted(projects):
        if name not in ordered:
            ordered.append(name)

    for name in ordered:
        p = projects[name]
        lines.append(f"  {name}:")
        if name == this_repo:
            lines.append("    # No url: kas uses the repo it was invoked from.")
        else:
            if p.url:
                lines.append(f"    url: {p.url}")
            if p.revision and re.fullmatch(r"[0-9a-fA-F]{40}", p.revision):
                lines.append(f"    commit: {p.revision}")
            elif p.revision:
                lines.append(f"    branch: {p.revision}")

        # layers
        if p.is_layer or name == this_repo:
            sublayers = sorted(p.layers) if p.layers else (["."] if name == this_repo else [])
            if sublayers:
                lines.append("    layers:")
                for sub in sublayers:
                    lines.append(f"      {sub}:")
            else:
                # a layer repo that is never referenced in bblayers -> disable
                lines.append("    layers:")
                lines.append("      .: excluded")
        else:
            # non-layer repo (bitbake provides the binary; lmp-tools is a helper)
            lines.append("    layers:")
            lines.append("      .: excluded")
        lines.append("")


def emit_local_conf(manifest_dir, lines):
    lines.append("local_conf_header:")
    # 1) auto.conf equivalent produced by setup-environment-internal
    lines.append("  10-lmp-auto: |")
    for l in [
        'INHERIT += "rm_work"',
        'INHERIT += "buildstats buildstats-summary"',
        'INHERIT += "buildhistory"',
        'BUILDHISTORY_COMMIT = "1"',
        '',
        '# LmP public sstate mirror. Replace <N> with your LMP cache version',
        '# (setup-environment-internal derived it from the lmp-manifest git tag).',
        '#SSTATE_MIRRORS ??= "file://.* https://storage.googleapis.com/lmp-cache/v<N>-sstate-cache/PATH"',
    ]:
        lines.append(f"    {l}")
    lines.append("")
    # 2) verbatim conf/local.conf
    local_conf = os.path.join(manifest_dir, "conf", "local.conf")
    if os.path.isfile(local_conf):
        lines.append("  20-lmp-local: |")
        with open(local_conf) as fh:
            for raw in fh.read().splitlines():
                lines.append(f"    {raw}" if raw else "")
    lines.append("")


def emit_env(mode, extra_env, lines):
    """Emit the KAS `env:` block: factory-keys var + any user --env vars.

    Variables listed here are passed through to bitbake (kas adds them to
    BB_ENV_PASSTHROUGH_ADDITIONS) and are usable as ${VAR} in the metadata.
    A `null` value means "pass through only if set in the environment".
    """
    if mode == "none" and not extra_env:
        return
    lines.append("env:")
    if mode != "none":
        lines.append("  # Directory holding this factory's signing keys (factory-keys).")
        if mode == "env":
            lines.append("  # Set FACTORY_KEYS_DIR in your environment at build time; kas passes")
            lines.append("  # it through to bitbake. For kas-container also bind-mount that path.")
        elif mode == "vendored":
            lines.append("  # Keys vendored inside the layer. The patched lmp-factory-custom.inc")
            lines.append("  # auto-detects <layer>/factory-keys, so no value is required here, but")
            lines.append("  # you may still override FACTORY_KEYS_DIR from the environment.")
        lines.append("  FACTORY_KEYS_DIR:")
    for key, val in extra_env:
        if val is None:
            lines.append(f"  # Override {key} from the environment at build time.")
            lines.append(f"  {key}:")
        else:
            lines.append(f"  # {key} (default below; override from the environment at build time).")
            lines.append(f"  {key}: {yaml_quote(val)}")
    lines.append("")


FACTORY_INC_BLOCK = """# Factory signing keys location.
# Precedence: FACTORY_KEYS_DIR (env / kas var) > vendored <layer>/factory-keys
#             > legacy ${TOPDIR}/conf/factory-keys (repo + setup-environment flow).
FACTORY_KEYS_LAYERDIR := "${@os.path.normpath(os.path.dirname(d.getVar('FILE', True)) + '/../../..')}"
FACTORY_KEYS_DIR ??= "${@('%s/factory-keys' % d.getVar('FACTORY_KEYS_LAYERDIR')) if os.path.isdir('%s/factory-keys' % d.getVar('FACTORY_KEYS_LAYERDIR')) else (d.getVar('TOPDIR') + '/conf/factory-keys')}"

# kernel modules signing key
MODSIGN_KEY_DIR = "${FACTORY_KEYS_DIR}"
MODSIGN_PRIVKEY = "${MODSIGN_KEY_DIR}/privkey_modsign.pem"
MODSIGN_X509 = "${MODSIGN_KEY_DIR}/x509_modsign.crt"

# U-Boot signing key
UBOOT_SIGN_KEYDIR = "${FACTORY_KEYS_DIR}"
UBOOT_SIGN_KEYNAME = "ubootdev"

# OP-TEE: Custom TA signing key
OPTEE_TA_SIGN_KEY = "${FACTORY_KEYS_DIR}/opteedev.key"

# SPL / U-Boot proper signing key
UBOOT_SPL_SIGN_KEYDIR = "${FACTORY_KEYS_DIR}"
UBOOT_SPL_SIGN_KEYNAME = "spldev"

# UEFI keys and certificates
UEFI_SIGN_KEYDIR = "${FACTORY_KEYS_DIR}/uefi"

# TF-A Trusted Boot
TF_A_SIGN_KEY_PATH = "${FACTORY_KEYS_DIR}/tf-a/privkey_ec_prime256v1.pem"
"""


def patch_factory_inc(inc_path):
    if not os.path.isfile(inc_path):
        print(f"NOTE: {inc_path} not found; skipping key-indirection patch.", file=sys.stderr)
        return
    with open(inc_path) as fh:
        content = fh.read()
    if "FACTORY_KEYS_DIR" in content:
        print(f"NOTE: {inc_path} already uses FACTORY_KEYS_DIR; leaving as-is.")
        return
    if "${TOPDIR}/conf/factory-keys" not in content:
        print(f"NOTE: {inc_path} does not use the expected key paths; not patching.", file=sys.stderr)
        return
    # Drop the old hard-coded signing block, keep everything before it.
    marker = "# kernel modules signing key"
    head = content.split(marker)[0].rstrip() + "\n\n"
    with open(inc_path, "w") as fh:
        fh.write(head + FACTORY_INC_BLOCK)
    print(f"Patched {inc_path} to use FACTORY_KEYS_DIR (backwards compatible).")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest-dir", required=True, help="Path to the lmp-manifest checkout")
    ap.add_argument("--manifest", required=True, help="Top manifest xml (e.g. andy-corp.xml)")
    ap.add_argument("--output", required=True, help="Output KAS yaml path")
    ap.add_argument("--this-repo", default="meta-subscriber-overrides",
                    help="Repo kas is invoked from / built (no url emitted)")
    ap.add_argument("--machine", action="append", default=[],
                    help="MACHINE (repeatable: >1 emits a base + per-machine include files)")
    ap.add_argument("--distro", default="lmp")
    ap.add_argument("--target", default="lmp-factory-image")
    ap.add_argument("--kas-version", default="14")
    ap.add_argument("--factory-keys", choices=["env", "vendored", "none"], default="env",
                    help="How factory signing keys are supplied (default: env)")
    ap.add_argument("--env", action="append", default=[], metavar="KEY[=DEFAULT]",
                    help="Extra build-time variable to pass through to bitbake via kas "
                         "`env:` (repeatable). 'KEY' passes through only if set in the "
                         "environment; 'KEY=DEFAULT' provides a default. E.g. --env H_BUILD=0")
    ap.add_argument("--patch-factory-inc", dest="patch_inc", action="store_true", default=True,
                    help="Patch <this-repo>/conf/machine/include/lmp-factory-custom.inc (default)")
    ap.add_argument("--no-patch-factory-inc", dest="patch_inc", action="store_false")
    ap.add_argument("--this-repo-dir", default=None,
                    help="Path to <this-repo> checkout (for patching its inc). "
                         "Default: sibling of manifest-dir named <this-repo>.")
    args = ap.parse_args()

    extra_env = []
    for item in args.env:
        if "=" in item:
            k, v = item.split("=", 1)
            extra_env.append((k.strip(), v))
        else:
            extra_env.append((item.strip(), None))

    remotes, default, raw = parse_manifest(args.manifest_dir, args.manifest)
    projects = build_projects(remotes, default, raw)
    collect_layers(args.manifest_dir, projects)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    def base_body(include_machine):
        lines = []
        lines.append("# Generated by manifest2kas.py - do not hand-edit blindly.")
        lines.append("header:")
        lines.append(f"  version: {args.kas_version}")
        lines.append("")
        lines.append(f"distro: {yaml_quote(args.distro)}")
        if include_machine and len(args.machine) == 1:
            lines.append(f"machine: {yaml_quote(args.machine[0])}")
        lines.append(f"target: {yaml_quote(args.target)}")
        lines.append("")
        emit_env(args.factory_keys, extra_env, lines)
        emit_repos(projects, args.this_repo, lines)
        emit_local_conf(args.manifest_dir, lines)
        return "\n".join(lines).rstrip() + "\n"

    outputs = []
    if len(args.machine) <= 1:
        with open(args.output, "w") as fh:
            fh.write(base_body(include_machine=True))
        outputs.append(args.output)
    else:
        # base file without machine + one include per machine
        base_path = args.output
        with open(base_path, "w") as fh:
            fh.write(base_body(include_machine=False))
        outputs.append(base_path)
        base_name = os.path.basename(base_path)
        out_dir = os.path.dirname(os.path.abspath(base_path))
        stem = os.path.splitext(base_name)[0]
        for m in args.machine:
            mpath = os.path.join(out_dir, f"{stem}-{m}.yml")
            with open(mpath, "w") as fh:
                fh.write(
                    f"header:\n  version: {args.kas_version}\n"
                    f"  includes:\n    - {base_name}\n\n"
                    f"machine: {yaml_quote(m)}\n"
                )
            outputs.append(mpath)

    # Optionally patch the factory inc for key indirection.
    if args.patch_inc and args.factory_keys != "none":
        this_dir = args.this_repo_dir or os.path.join(
            os.path.dirname(os.path.abspath(args.manifest_dir.rstrip("/"))), args.this_repo)
        patch_factory_inc(os.path.join(this_dir, "conf", "machine", "include",
                                       "lmp-factory-custom.inc"))

    print("\nWrote:")
    for o in outputs:
        print(f"  {o}")
    print("\nNext steps:")
    print("  kas-container build " + outputs[-1])
    if args.factory_keys == "env":
        print("\nFactory keys (env mode): before building, point FACTORY_KEYS_DIR at the")
        print("directory that holds spldev/ubootdev/opteedev/privkey_modsign keys, uefi/ and tf-a/:")
        print("  export FACTORY_KEYS_DIR=/abs/path/to/factory-keys")
        print("  kas-container --runtime-args \"-v $FACTORY_KEYS_DIR:$FACTORY_KEYS_DIR\" build " + outputs[-1])
    elif args.factory_keys == "vendored":
        print("\nFactory keys (vendored mode): copy the keys into the layer, e.g.")
        print(f"  cp -r <lmp-manifest>/factory-keys {args.this_repo}/factory-keys")
        print("The patched lmp-factory-custom.inc auto-detects <layer>/factory-keys.")


if __name__ == "__main__":
    main()
