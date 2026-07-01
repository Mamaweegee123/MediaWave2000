"""Smoke tests for local playback path synchronization helpers."""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mediawave.playback_state import (
    active_playback_path,
    expected_frame_path,
    media_paths_match,
    playback_frame_matches,
    tune_context_matches,
)


PASS = []
FAIL = []


def check(name, expression):
    (PASS if expression else FAIL).append(name)
    print(f"{'  OK  ' if expression else 'FAIL  '}{name}")


channel = object()
context = {
    "generation": 7,
    "channel_index": 3,
    "channel_object_id": id(channel),
    "path": "/Media/Moomin/S01E01.mkv",
}

check("matching tune context is accepted", tune_context_matches(context, 7, 3, channel, "/Media/Moomin/S01E01.mkv"))
check("stale generation is rejected", not tune_context_matches(context, 6, 3, channel, "/Media/Moomin/S01E01.mkv"))
check("different channel object is rejected", not tune_context_matches(context, 7, 3, object(), "/Media/Moomin/S01E01.mkv"))
check("wrong media path is rejected", not tune_context_matches(context, 7, 3, channel, "/Media/Are You Afraid/S01E01.mkv"))
check("equivalent local paths match", media_paths_match("/Media/Moomin/../Moomin/S01E01.mkv", "/Media/Moomin/S01E01.mkv"))
check("different media paths do not match", not media_paths_match("/Media/Moomin/S01E01.mkv", "/Media/Other/S01E01.mkv"))
check("active path wins metadata selection", active_playback_path("actual.mkv", "expected.mkv", "scheduled.mkv") == "actual.mkv")
check("expected path wins before playback starts", active_playback_path("", "expected.mkv", "scheduled.mkv") == "expected.mkv")
check("live frames use scheduled live path", expected_frame_path("live", "live.mkv", "vault.mkv") == "live.mkv")
check("Vault frames use selected Vault path", expected_frame_path("ondemand", "live.mkv", "vault.mkv") == "vault.mkv")
check("Vault frame accepts selected episode", playback_frame_matches("ondemand", "/Media/Top Gear.mkv", "/Media/Samurai.mkv", "/Media/Top Gear.mkv"))
check("Vault frame rejects stale live episode", not playback_frame_matches("ondemand", "/Media/Samurai.mkv", "/Media/Samurai.mkv", "/Media/Top Gear.mkv"))

print(f"\nResults: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
