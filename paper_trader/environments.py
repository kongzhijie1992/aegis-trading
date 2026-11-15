"""Explicit environment selection; selecting an account never authorizes an order."""

import json
from pathlib import Path

from trading_contracts import Config, SafetyError


def load_config(args):
    config = Config(**json.loads(Path(args.config).read_text(encoding="utf-8")))
    config.validate()
    if config.mode != args.environment:
        raise SafetyError("Selected environment does not match the account configuration")
    if config.mode == "live" and args.command == "trade" and not args.enable_live:
        raise SafetyError("Starting a live trading session requires --enable-live")
    if args.enable_live and (config.mode != "live" or args.command != "trade"):
        raise SafetyError(
            "--enable-live is only valid for an explicitly selected live trade session"
        )
    return config
