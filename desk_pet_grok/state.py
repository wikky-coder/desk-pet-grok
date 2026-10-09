"""Pet finite state machine (display / animation slots)."""

from __future__ import annotations

from enum import Enum


class PetState(Enum):
    idle = "idle"
    think = "think"
    work = "work"
    wait = "wait"
    done = "done"
    error = "error"
    sleep = "sleep"


# Higher number wins when set() is contested.
_PRIORITY: dict[PetState, int] = {
    PetState.wait: 6,
    PetState.error: 5,
    PetState.work: 4,
    PetState.think: 3,
    PetState.done: 2,
    PetState.sleep: 1,
    PetState.idle: 0,
}


class StateMachine:
    """Drives pet visual state from chat / quiet events."""

    def __init__(self) -> None:
        self._state = PetState.idle
        self._quiet = False

    @property
    def state(self) -> PetState:
        return self._state

    @property
    def quiet(self) -> bool:
        return self._quiet

    def set(self, next_state: PetState) -> bool:
        """Request a state; succeeds if priority >= current."""
        if _PRIORITY[next_state] < _PRIORITY[self._state]:
            return False
        self._state = next_state
        return True

    def _force(self, next_state: PetState) -> None:
        self._state = next_state

    def _rest_state(self) -> PetState:
        return PetState.sleep if self._quiet else PetState.idle

    def on_send(self) -> None:
        self._force(PetState.think)

    def on_first_token(self) -> None:
        # v1: leave think; streaming continues in bubble under idle loop.
        if self._state is PetState.think:
            self._force(PetState.idle)

    def on_stream_end(self) -> None:
        self._force(PetState.done)

    def on_error(self) -> None:
        self._force(PetState.error)

    def on_cancel(self) -> None:
        """User stopped a stream; return to idle/sleep rest."""
        self._force(self._rest_state())

    def on_tool_need_confirm(self) -> None:
        # v2 stub: tool confirmation parks in wait.
        self._force(PetState.wait)

    def enter_quiet(self) -> None:
        self._quiet = True
        if self._state is PetState.idle:
            self._force(PetState.sleep)

    def leave_quiet(self) -> None:
        self._quiet = False
        if self._state is PetState.sleep:
            self._force(PetState.idle)

    def tick_done_elapsed(self) -> None:
        """Simulate ~1.2s done timer → rest (idle or sleep if quiet)."""
        if self._state is PetState.done:
            self._force(self._rest_state())
