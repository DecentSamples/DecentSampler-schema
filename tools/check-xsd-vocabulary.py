#!/usr/bin/env python3
"""Check that DecentSampler.xsd agrees with engine-vocabulary.json (Mantis 0000536).

The XSD is written by hand, so it drifts. This compares the lists it enumerates against what the
engine accepts and exits non-zero if they differ:
    binding parameter  (simpleType bindingParameterName; the engine ignores case, so every name
                        must appear in upper and lower case, and nothing else)
    binding type/level (the enumerations on complexType "binding")
    seqMode            (the enumeration on the seqMode attribute)

Usage: tools/check-xsd-vocabulary.py
"""

import json
import pathlib
import sys
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent.parent
XS = "{http://www.w3.org/2001/XMLSchema}"


def enumeration(node):
    return {e.get("value") for e in node.iter(XS + "enumeration")}


def compare(label, xsd_values, engine_values, problems):
    missing = sorted(set(engine_values) - set(xsd_values))
    extra = sorted(set(xsd_values) - set(engine_values))
    if missing:
        problems.append(f"{label}: the engine accepts these but the XSD doesn't: {', '.join(missing)}")
    if extra:
        problems.append(f"{label}: the XSD accepts these but the engine doesn't: {', '.join(extra)}")


def main():
    vocabulary = json.loads((HERE / "engine-vocabulary.json").read_text(encoding="utf-8"))
    root = ET.parse(HERE / "DecentSampler.xsd").getroot()
    problems = []

    parameter_type = root.find(f"{XS}simpleType[@name='bindingParameterName']")
    xsd_parameters = enumeration(parameter_type)
    engine_parameters = vocabulary["binding"]["parameters"]
    compare("binding parameter", xsd_parameters,
            engine_parameters + [p.lower() for p in engine_parameters], problems)

    binding = root.find(f"{XS}complexType[@name='binding']")
    for attribute, key in (("type", "types"), ("level", "levels")):
        node = binding.find(f".//{XS}attribute[@name='{attribute}']")
        compare(f"binding {attribute}", enumeration(node), vocabulary["binding"][key], problems)

    seq_modes = set()
    for node in root.iter(XS + "attribute"):
        if node.get("name") == "seqMode":
            seq_modes |= enumeration(node)
    compare("seqMode", seq_modes, vocabulary["seqModes"], problems)

    if problems:
        print("DecentSampler.xsd disagrees with engine-vocabulary.json:")
        for problem in problems:
            print("  - " + problem)
        sys.exit(1)
    print(f"DecentSampler.xsd agrees with engine-vocabulary.json (engine {vocabulary['engine']['version']}).")


if __name__ == "__main__":
    main()
