"""
config.py — Config file support for psiwatch.

Searches for config in order:
    1. Explicit path passed via --config / load_config(path=...)
    2. psiwatch.toml in current directory, then parent directories
    3. .psiwatchrc in current directory, then parent directories

CLI flags always override config file values.

psiwatch.toml example:
    psi_threshold = 0.15
    ignore_columns = ["id", "timestamp"]
    fail_on_drift = true
    webhook = "https://hooks.slack.com/services/XXX/YYY/ZZZ"

    [thresholds]
    mean_shift_high = 0.6
    psi_high = 0.3

.psiwatchrc example (plain JSON):
    {
      "psi_threshold": 0.2,
      "ignore_columns": ["id", "timestamp"],
      "fail_on_drift": true,
      "thresholds": {"mean_shift_high": 0.6}
    }

NOTE: TOML parser here is a minimal subset — flat key=value pairs plus
a single [thresholds] table. Zero dependencies, not a general-purpose parser.
"""

import json
import os

CONFIG_FILENAMES = ["psiwatch.toml", ".psiwatchrc"]

RECOGNIZED_KEYS = {
    "psi_threshold", "columns", "ignore_columns", "format",
    "output", "fail_on_drift", "silent", "webhook", "thresholds",
    "interval", "output_dir",
}


def _find_config(start_dir="."):
    """Walk from start_dir up to filesystem root looking for a config file."""
    directory = os.path.abspath(start_dir)
    while True:
        for name in CONFIG_FILENAMES:
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                return candidate
        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent
    return None


def _parse_scalar(raw):
    raw = raw.strip()
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    if (raw.startswith('"') and raw.endswith('"')) or \
       (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    try:
        return float(raw) if ("." in raw or "e" in raw.lower()) else int(raw)
    except ValueError:
        return raw


def _parse_value(raw):
    """Parse a TOML-ish value including single-line arrays."""
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(p.strip()) for p in inner.split(",") if p.strip()]
    return _parse_scalar(raw)


def _parse_toml(text):
    """
    Parse the minimal TOML subset psiwatch supports.
    Returns a dict where [thresholds] becomes a nested dict.
    """
    root = {}
    current = root
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            current = root.setdefault(name, {})
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        current[key.strip()] = _parse_value(value)
    return root


def load_config(explicit_path=None, start_dir=".", silent=False):
    """
    Load a psiwatch config file.

    Args:
        explicit_path: user-specified path (raises FileNotFoundError if missing)
        start_dir: directory to start searching from (walks up to root)
        silent: suppress "Config loaded" message

    Returns:
        dict of recognized config values, empty dict if none found.
    """
    if explicit_path:
        if not os.path.exists(explicit_path):
            raise FileNotFoundError(f"Config file not found: {explicit_path}")
        path = explicit_path
    else:
        path = _find_config(start_dir)

    if not path:
        return {}

    if path.endswith(".toml"):
        with open(path, "r", encoding="utf-8") as f:
            raw = _parse_toml(f.read())
        # Support both flat keys and [psiwatch] section wrapper
        if "psiwatch" in raw and isinstance(raw["psiwatch"], dict):
            flat = dict(raw["psiwatch"])
        else:
            flat = {k: v for k, v in raw.items() if not isinstance(v, dict)}
        config = flat
        # [thresholds] section — can live at top level or under [psiwatch]
        if isinstance(raw.get("thresholds"), dict):
            config["thresholds"] = raw["thresholds"]
        elif isinstance(flat.get("thresholds"), dict):
            pass  # already included
    else:
        # .psiwatchrc — plain JSON
        with open(path, "r", encoding="utf-8") as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in {path}: {e}")
        if not isinstance(config, dict):
            raise ValueError(f"{path} must contain a JSON object")

    config = {k: v for k, v in config.items() if k in RECOGNIZED_KEYS}
    config["_source"] = path

    if not silent and config:
        print(f"  Config loaded: {path}")

    return config


def apply_config(args, config):
    """
    Fill in unset argparse Namespace attributes from a config dict.
    CLI flags always win — only None / False attributes get filled.
    Returns args (mutated in place).
    """
    if not config:
        return args

    _str_opt = lambda k, a: (
        setattr(args, a, config[k])
        if getattr(args, a, None) is None and k in config else None
    )
    _bool_opt = lambda k, a: (
        setattr(args, a, True)
        if not getattr(args, a, False) and config.get(k) else None
    )

    if getattr(args, "psi_threshold", None) is None and "psi_threshold" in config:
        try:
            args.psi_threshold = float(config["psi_threshold"])
        except (TypeError, ValueError):
            raise ValueError(
                f"Invalid psi_threshold in {config.get('_source')}: "
                f"{config['psi_threshold']!r}"
            )

    if getattr(args, "columns", None) is None and "columns" in config:
        cols = config["columns"]
        args.columns = ",".join(str(c) for c in cols) if isinstance(cols, list) else str(cols)

    if getattr(args, "ignore_columns", None) is None and "ignore_columns" in config:
        cols = config["ignore_columns"]
        args.ignore_columns = (
            ",".join(str(c) for c in cols) if isinstance(cols, list) else str(cols)
        )

    _str_opt("format", "format")
    _str_opt("output", "output")
    _str_opt("webhook", "webhook")
    _str_opt("output_dir", "output_dir")
    _bool_opt("fail_on_drift", "fail_on_drift")
    _bool_opt("silent", "silent")

    if getattr(args, "interval", None) is None and "interval" in config:
        try:
            args.interval = int(config["interval"])
        except (TypeError, ValueError):
            pass

    if isinstance(config.get("thresholds"), dict):
        args.config_thresholds = config["thresholds"]
    else:
        args.config_thresholds = getattr(args, "config_thresholds", None)

    return args


def write_example_config(path="psiwatch.toml"):
    """Write an example psiwatch.toml to disk."""
    content = """\
# psiwatch.toml — project-level defaults
# CLI flags always override these values.
# Run `psiwatch init` to regenerate this file.

# PSI threshold for HIGH drift (default: 0.25)
# psi_threshold = 0.15

# Columns to compare (default: all)
# columns = ["age", "score", "city"]

# Columns to always skip
# ignore_columns = ["id", "timestamp", "row_num"]

# Default output format: terminal, json, txt, html
# format = "html"

# Default output file path
# output = "reports/drift.html"

# Exit with code 1 if drift detected
# fail_on_drift = false

# Watch mode poll interval in seconds
# interval = 60

# Output directory for watch mode HTML reports
# output_dir = "reports/"

# Webhook URL for drift alerts (Slack / Discord / generic JSON)
# webhook = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Fine-grained threshold overrides
# [thresholds]
# mean_shift_high = 0.6
# psi_high = 0.3
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Config file created: {path}")
    print("  Edit it to set your project defaults.")


# Legacy alias
def merge_config_with_args(cfg, args_dict):
    """Dict-based merge — kept for backwards compatibility."""
    import argparse
    ns = argparse.Namespace(**args_dict)
    apply_config(ns, cfg)
    return vars(ns)
