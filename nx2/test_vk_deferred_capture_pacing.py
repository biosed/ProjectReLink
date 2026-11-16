"""Guard deferred replay's submitter-side late-page pacing; no GPU/game."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def block(text: str, marker: str) -> str:
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def main() -> None:
    replay = (ROOT / "gpu/vk/vk_replay.cpp").read_text(encoding="utf-8")
    memory = (ROOT / "gpu/vk/vk_memory.cpp").read_text(encoding="utf-8")
    internal = (ROOT / "gpu/vk/vk_internal.h").read_text(encoding="utf-8")

    submit = block(replay, "void submit_q(")
    deferred = submit[submit.index("if (sync_waits_on() && defer_main_replay_on())"):]
    deferred = deferred[: deferred.index("        std::lock_guard order(sync_order_mu);")]
    assert "memory_capture_submit(true);" in deferred
    assert deferred.index("memory_capture_submit(true);") < deferred.index("defer_jobs.push_back")

    # Every other capture path retains the old replay-side default. New callers
    # must choose deliberately instead of silently inheriting deferred pacing.
    assert replay.count("memory_capture_submit(true);") == 1
    assert replay.count("memory_capture_submit(false);") == 2
    assert "void memory_capture_submit(bool wait_late_on_submitter);" in internal

    capture = block(memory, "std::unique_ptr<Capture> capture_make(bool wait_late_on_submitter) {")
    assert "cap_wait_set ? cap_wait_value : wait_late_on_submitter ? 1 : 2" in capture
    assert capture.index("const int cap_wait =") < capture.index("if (cap_wait && this_waits)")
    assert "An explicit RX_VK_CAPTURE_WAIT still wins" in internal
    print("vk_deferred_capture_pacing: submitter pacing and explicit override ordering ok")


if __name__ == "__main__":
    main()
