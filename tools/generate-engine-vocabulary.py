#!/usr/bin/env python3
"""Generate engine-vocabulary.json from the Decent Sampler source (Mantis 0000536).

The store's upload validator reads engine-vocabulary.json to check presets against the names the
engine actually accepts: binding levels, types and parameters, seqMode values and note names. Decent
Sampler's own Validate Preset reads the same tables directly, so the two can't drift as long as this
file is regenerated whenever those tables change.

Usage:
    tools/generate-engine-vocabulary.py [path/to/DecentSampler] [--exclude REGEX ...]
        (default source: ../DecentSampler)

    --exclude leaves out binding parameters whose name matches REGEX (the whole name, upper
    case). Use it for parameters that are in the source but not yet released.

It reads these tables, each written one { "name", value } entry per line:
    Source/Models/DSBinding.cpp        kLevelNames, kTypeNames, kParameterMap
    Source/Utilities/DSHelpers.cpp     kSeqModeNames, kNoteNames
    Source/Libraries/DSPresetLint.cpp  kParameterAliases, kTypeAliases, kLevelAliases
"""

import argparse
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent
OUTPUT = HERE / "engine-vocabulary.json"


def block(text, start_marker, path):
    start = text.find(start_marker)
    if start < 0:
        sys.exit(f"{path}: couldn't find {start_marker!r}")
    end = text.find("};", start)
    return text[start:end]


def names(text, start_marker, path, pattern=r'\{\s*"([^"]*)",'):
    found = re.findall(pattern, block(text, start_marker, path))
    if not found:
        sys.exit(f"{path}: {start_marker!r} has no entries")
    return found


def pairs(text, start_marker, path):
    found = re.findall(r'\{\s*"([^"]+)",\s*"([^"]+)"\s*\}', block(text, start_marker, path))
    return {wrong: right for wrong, right in found}


def main():
    parser = argparse.ArgumentParser(description="Generate engine-vocabulary.json from the Decent Sampler source.")
    parser.add_argument("source", nargs="?", default=str(HERE.parent / "DecentSampler"))
    parser.add_argument("--exclude", action="append", default=[], metavar="REGEX",
                        help="leave out binding parameters whose whole name matches REGEX")
    args = parser.parse_args()
    excluded = [re.compile(pattern) for pattern in args.exclude]

    source = pathlib.Path(args.source).resolve()
    binding_cpp = source / "Source/Models/DSBinding.cpp"
    helpers_cpp = source / "Source/Utilities/DSHelpers.cpp"
    lint_cpp = source / "Source/Libraries/DSPresetLint.cpp"
    binding = binding_cpp.read_text(encoding="utf-8")
    helpers = helpers_cpp.read_text(encoding="utf-8")
    lint = lint_cpp.read_text(encoding="utf-8")

    jucer = (source / "DecentSampler.jucer").read_text(encoding="utf-8")
    version = re.search(r'<JUCERPROJECT[^>]*\sversion="([^"]+)"', jucer).group(1)
    try:
        commit = subprocess.run(["git", "-C", str(source), "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"

    note_names = re.search(r'kNoteNames\[\]\s*=\s*\{([^}]*)\}', helpers)
    if not note_names:
        sys.exit(f"{helpers_cpp}: couldn't find kNoteNames")

    vocabulary = {
        "about": "Names the Decent Sampler engine accepts, generated from its source by "
                 "tools/generate-engine-vocabulary.py. Don't edit by hand.",
        "engine": {"version": version, "commit": commit},
        "binding": {
            "levels": names(binding, "kLevelNames[]", binding_cpp),
            "types": names(binding, "kTypeNames[]", binding_cpp),
            # Upper case: the engine upper-cases the parameter attribute before looking it up.
            "parameters": sorted(name for name in set(names(binding, "kParameterMap {", binding_cpp))
                                 if not any(pattern.fullmatch(name) for pattern in excluded)),
        },
        "seqModes": names(helpers, "kSeqModeNames[]", helpers_cpp),
        # Note names parseMIDINote() accepts before the octave number, upper case.
        "noteNames": [n for n in re.findall(r'"([^"]*)"', note_names.group(1)) if n],
        "suggestions": {
            "parameters": pairs(lint, "kParameterAliases[]", lint_cpp),
            "types": pairs(lint, "kTypeAliases[]", lint_cpp),
            "levels": pairs(lint, "kLevelAliases[]", lint_cpp),
        },
    }

    OUTPUT.write_text(json.dumps(vocabulary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.name}: engine {version} ({commit}), "
          f"{len(vocabulary['binding']['parameters'])} parameters, "
          f"{len(vocabulary['binding']['types'])} types, {len(vocabulary['binding']['levels'])} levels, "
          f"{len(vocabulary['seqModes'])} seqModes")


if __name__ == "__main__":
    main()
