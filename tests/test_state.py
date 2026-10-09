"""Tests for pet finite state machine."""

from desk_pet_grok.state import PetState, StateMachine


def test_send_goes_to_think():
    sm = StateMachine()
    assert sm.state is PetState.idle
    sm.on_send()
    assert sm.state is PetState.think


def test_first_token_leaves_think_to_idle():
    sm = StateMachine()
    sm.on_send()
    assert sm.state is PetState.think
    sm.on_first_token()
    assert sm.state is PetState.idle


def test_error_goes_to_error():
    sm = StateMachine()
    sm.on_send()
    sm.on_error()
    assert sm.state is PetState.error


def test_done_then_tick_returns_to_idle():
    sm = StateMachine()
    sm.on_send()
    sm.on_first_token()
    sm.on_stream_end()
    assert sm.state is PetState.done
    sm.tick_done_elapsed()
    assert sm.state is PetState.idle


def test_quiet_idle_becomes_sleep():
    sm = StateMachine()
    sm.enter_quiet()
    assert sm.state is PetState.sleep
    sm.leave_quiet()
    assert sm.state is PetState.idle


def test_tool_need_confirm_goes_to_wait():
    sm = StateMachine()
    sm.on_tool_need_confirm()
    assert sm.state is PetState.wait


def test_priority_wait_over_think():
    sm = StateMachine()
    sm.on_send()
    assert sm.state is PetState.think
    sm.on_tool_need_confirm()
    assert sm.state is PetState.wait


def test_cancel_returns_to_idle():
    sm = StateMachine()
    sm.on_send()
    assert sm.state is PetState.think
    sm.on_cancel()
    assert sm.state is PetState.idle


def test_cancel_in_quiet_returns_to_sleep():
    sm = StateMachine()
    sm.enter_quiet()
    sm.on_send()
    assert sm.state is PetState.think
    sm.on_cancel()
    assert sm.state is PetState.sleep

