"""
Airship CLI entrypoint and argument parser.
"""

import sys
import argparse
from pathlib import Path

# Ensure src is in sys.path
SRC_DIR = Path(__file__).resolve().parent.parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fintech_rl.cli.ui import (
    Ansi,
    print_banner,
    print_panel,
    c_bold,
    c_cyan,
    c_sky,
    c_green,
    c_yellow,
    c_gray,
    c_purple,
    badge,
)
from fintech_rl.cli.commands import (
    cmd_demo,
    cmd_benchmark,
    cmd_generate,
    cmd_inspect,
    cmd_play,
    cmd_check,
)


def print_custom_help():
    print_banner()
    help_body = (
        f"{c_bold('USAGE:')}\n"
        f"  airship <command> [options]\n\n"
        f"{c_bold('COMMANDS:')}\n"
        f"  {c_cyan('demo')}        [--episode ID]     Run step-by-step interactive audit demo\n"
        f"  {c_cyan('benchmark')}   [--dataset SPLIT]  Evaluate 4 policies across all 20 episodes\n"
        f"  {c_cyan('generate')}                       Synthesize 10 train and 10 dev audit episodes\n"
        f"  {c_cyan('inspect')}     <episode_id>       Inspect episode ledger, invoices, or truth\n"
        f"  {c_cyan('play')}        [--episode ID]     Play as a Human Auditor interactively\n"
        f"  {c_cyan('check')}                          Run full verification pipeline (tests + gen + eval)\n\n"
        f"{c_bold('EXAMPLES:')}\n"
        f"  {c_gray('$ airship demo')}\n"
        f"  {c_gray('$ airship benchmark --dataset all')}\n"
        f"  {c_gray('$ airship inspect train_ep_03 --table ledger --limit 10')}\n"
        f"  {c_gray('$ airship play train_ep_03')}\n"
        f"  {c_gray('$ airship check')}\n"
    )
    print_panel(help_body, title="AIRSHIP COMMAND LINE INTERFACE", border_color=Ansi.BRAND_SKY)
    print()


def _configure_output_streams():
    """Keep the Unicode CLI usable when Windows redirects legacy-encoded IO."""
    for stream in (sys.stdout, sys.stderr):
        encoding = getattr(stream, "encoding", None)
        reconfigure = getattr(stream, "reconfigure", None)
        if not isinstance(encoding, str) or not callable(reconfigure):
            continue
        if encoding.lower().replace("-", "").replace("_", "") in {"utf8", "utf8sig"}:
            continue
        reconfigure(encoding="utf-8")


def main(argv=None):
    _configure_output_streams()
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help", "help"):
        print_custom_help()
        return 0

    cmd = argv[0].lower()

    if cmd == "demo":
        ep_id = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else "train_ep_03"
        return cmd_demo(episode_id=ep_id)

    elif cmd in ("benchmark", "eval", "run-policies"):
        dataset = "all"
        out_traj = None
        for i, a in enumerate(argv):
            if a in ("--dataset", "-d") and i + 1 < len(argv):
                dataset = argv[i + 1]
            if a in ("--output", "-o") and i + 1 < len(argv):
                out_traj = argv[i + 1]
        return cmd_benchmark(dataset=dataset, out_trajectories=out_traj)

    elif cmd in ("generate", "episodes", "make-episodes"):
        return cmd_generate()

    elif cmd == "inspect":
        if len(argv) < 2 or argv[1].startswith("-"):
            print(f" {badge('ERROR', 'red')} Missing required argument: <episode_id>")
            print(f" Usage: airship inspect <episode_id> [--table ledger|invoices|truth] [--limit N]")
            return 1
        ep_id = argv[1]
        table = "manifest"
        limit = 15
        show_truth = "--show-truth" in argv
        for i, a in enumerate(argv):
            if a in ("--table", "-t") and i + 1 < len(argv):
                table = argv[i + 1]
            if a in ("--limit", "-l") and i + 1 < len(argv):
                try:
                    limit = int(argv[i + 1])
                except ValueError:
                    pass
        return cmd_inspect(episode_id=ep_id, table=table, limit=limit, show_truth=show_truth)

    elif cmd in ("play", "interactive"):
        ep_id = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else "train_ep_03"
        return cmd_play(episode_id=ep_id)

    elif cmd == "check":
        return cmd_check()

    else:
        print_custom_help()
        print(f" {badge('UNKNOWN COMMAND', 'red')} '{cmd}'. See commands above.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
