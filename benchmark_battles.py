#!/usr/bin/env python
"""Quick benchmark for battle simulation performance.

Run with: python benchmark_battles.py [--setup PATH] [--runs N] [--workers W]

Example:
  python benchmark_battles.py --setup vr_game_sim/setups/HATTERINF.json --runs 100 --workers 4
"""
import argparse
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vr_game_sim.main import run_batch_return_winners, load_setup_from_file


def main():
    parser = argparse.ArgumentParser(description="Benchmark battle simulation")
    parser.add_argument(
        "--setup",
        default="vr_game_sim/setups/HATTERINF.json",
        help="Path to setup JSON file",
    )
    parser.add_argument("--runs", type=int, default=100, help="Number of battles to run")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    args = parser.parse_args()

    path = args.setup
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(__file__), path)
    loaded = load_setup_from_file(path)
    if not loaded:
        print(f"Failed to load setup from {path}")
        sys.exit(1)

    print(f"Running {args.runs} battles with {args.workers} worker(s)...")
    t0 = time.perf_counter()
    a1_wins, a2_wins, draws = run_batch_return_winners(
        loaded, args.runs, num_workers=args.workers
    )
    t1 = time.perf_counter()
    elapsed = t1 - t0
    print(f"Completed in {elapsed:.2f}s ({args.runs / elapsed:.0f} battles/sec)")
    print(f"Results: Army1={a1_wins}, Army2={a2_wins}, Draws={draws}")


if __name__ == "__main__":
    main()
