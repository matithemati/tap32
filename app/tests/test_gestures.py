from __future__ import annotations

from tap32.core.gestures import Gesture, GestureConfig, GestureEngine, GestureEvent


def make_engine(
    assigned: dict[int, set[Gesture]] | None = None, **cfg: object
) -> tuple[GestureEngine, list[GestureEvent]]:
    events: list[GestureEvent] = []
    assigned = assigned if assigned is not None else {}

    def has(key: int, gesture: Gesture) -> bool:
        return gesture in assigned.get(key, {Gesture.TAP})

    engine = GestureEngine(GestureConfig(**cfg), emit=events.append, has_gesture=has)  # type: ignore[arg-type]
    return engine, events


def kinds(events: list[GestureEvent]) -> list[tuple[int | None, str]]:
    return [(e.key, str(e.gesture)) for e in events]


def test_tap_immediately_without_double_tap() -> None:
    engine, events = make_engine()
    engine.key_down(1, 0)
    engine.key_up(1, 100)
    assert kinds(events) == [(1, "tap")]


def test_hold_on_release() -> None:
    engine, events = make_engine({1: {Gesture.TAP, Gesture.HOLD}})
    engine.key_down(1, 0)
    engine.tick(600)  # bez trybu „na progu” nic się nie dzieje
    assert events == []
    engine.key_up(1, 700)
    assert kinds(events) == [(1, "hold")]


def test_hold_threshold_boundary() -> None:
    engine, events = make_engine({1: {Gesture.TAP, Gesture.HOLD}})
    engine.key_down(1, 0)
    engine.key_up(1, 499)
    engine.key_down(1, 1000)
    engine.key_up(1, 1500)
    assert kinds(events) == [(1, "tap"), (1, "hold")]


def test_long_press_without_hold_is_tap() -> None:
    engine, events = make_engine({1: {Gesture.TAP}})
    engine.key_down(1, 0)
    engine.key_up(1, 2000)
    assert kinds(events) == [(1, "tap")]


def test_hold_on_threshold_fires_once() -> None:
    engine, events = make_engine({2: {Gesture.HOLD}}, hold_on_threshold=True)
    engine.key_down(2, 0)
    assert engine.next_deadline() == 500
    engine.tick(499)
    assert events == []
    engine.tick(500)
    engine.tick(900)
    engine.key_up(2, 1000)
    assert kinds(events) == [(2, "hold")]


def test_double_tap_and_delayed_tap() -> None:
    engine, events = make_engine({3: {Gesture.TAP, Gesture.DOUBLE_TAP}})
    engine.key_down(3, 0)
    engine.key_up(3, 50)
    assert events == []  # czekamy na ewentualny drugi tap
    engine.key_down(3, 200)
    engine.key_up(3, 260)
    assert kinds(events) == [(3, "double_tap")]

    engine.key_down(3, 1000)
    engine.key_up(3, 1050)
    engine.tick(1350)  # dokładnie na granicy okna – jeszcze nie
    assert len(events) == 1
    engine.tick(1351)
    assert kinds(events) == [(3, "double_tap"), (3, "tap")]


def test_second_press_after_window_gives_two_taps() -> None:
    engine, events = make_engine({3: {Gesture.TAP, Gesture.DOUBLE_TAP}})
    engine.key_down(3, 0)
    engine.key_up(3, 50)
    engine.key_down(3, 400)  # 350 ms po puszczeniu > 300 ms, tick nie przyszedł
    engine.key_up(3, 450)
    engine.tick(800)
    assert kinds(events) == [(3, "tap"), (3, "tap")]


def test_double_tap_window_inclusive() -> None:
    engine, events = make_engine({3: {Gesture.TAP, Gesture.DOUBLE_TAP}})
    engine.key_down(3, 0)
    engine.key_up(3, 10)
    engine.key_down(3, 310)  # dokładnie 300 ms
    assert kinds(events) == [(3, "double_tap")]


def test_keys_are_independent() -> None:
    engine, events = make_engine()
    engine.key_down(1, 0)
    engine.key_down(2, 10)
    engine.key_up(1, 20)
    engine.key_up(2, 30)
    assert kinds(events) == [(1, "tap"), (2, "tap")]


def test_duplicate_events_are_ignored() -> None:
    engine, events = make_engine()
    engine.key_up(5, 0)  # up bez down
    engine.key_down(5, 10)
    engine.key_down(5, 20)
    engine.key_up(5, 30)
    engine.key_up(5, 40)
    assert kinds(events) == [(5, "tap")]


def test_rotation() -> None:
    engine, events = make_engine()
    engine.rotate(2, 0)
    engine.rotate(-1, 100)
    engine.rotate(0, 200)
    assert [(e.key, str(e.gesture), e.steps) for e in events] == [
        (None, "rotate_cw", 2),
        (None, "rotate_ccw", 1),
    ]


def test_press_rotate_suppresses_tap_and_hold() -> None:
    engine, events = make_engine({10: {Gesture.TAP, Gesture.HOLD}})
    engine.key_down(10, 0)
    engine.rotate(1, 100)
    engine.rotate(-2, 150)
    engine.key_up(10, 900)  # długo, ale był obrót – brak hold/tap
    assert [(e.key, str(e.gesture), e.steps) for e in events] == [
        (10, "press_rotate_cw", 1),
        (10, "press_rotate_ccw", 2),
    ]
    engine.key_down(10, 2000)
    engine.key_up(10, 2050)
    assert kinds(events)[-1] == (10, "tap")


def test_press_rotate_cancels_hold_threshold() -> None:
    engine, events = make_engine({10: {Gesture.HOLD}}, hold_on_threshold=True)
    engine.key_down(10, 0)
    engine.rotate(1, 100)
    engine.tick(600)
    engine.key_up(10, 700)
    assert kinds(events) == [(10, "press_rotate_cw")]
    assert engine.next_deadline() is None


def test_acceleration() -> None:
    engine, events = make_engine(accel_enabled=True, accel_window_ms=40, accel_multiplier=3)
    engine.rotate(1, 0)  # pierwszy krok bez mnożnika
    engine.rotate(1, 30)  # szybko → ×3
    engine.rotate(1, 200)  # wolno → ×1
    assert [e.steps for e in events] == [1, 3, 1]


def test_reset_clears_state() -> None:
    engine, events = make_engine({1: {Gesture.TAP, Gesture.DOUBLE_TAP}})
    engine.key_down(1, 0)
    engine.key_up(1, 10)
    engine.reset()
    engine.tick(1000)
    assert events == []
