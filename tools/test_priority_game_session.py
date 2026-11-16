import os
import unittest

import priority_game_session


class Base:
    def __init__(self):
        self.ticks = 0

    def tick(self):
        self.ticks += 1
        return self.ticks

    def summary(self):
        return dict(base=True)


class FakeWindow:
    def __init__(self):
        self.steps = 0

    def step(self, action):
        self.steps += 1
        return action()

    def summary(self):
        return dict(level='TIME_CRITICAL', enabled=True, steps=self.steps)


class Tests(unittest.TestCase):
    def setUp(self):
        self.saved = os.environ.get(priority_game_session.KEY)
        self.saved_window = priority_game_session.priority_window.PriorityWindow
        self.windows = []

        def factory():
            window = FakeWindow()
            self.windows.append(window)
            return window

        priority_game_session.priority_window.PriorityWindow = factory

    def tearDown(self):
        priority_game_session.priority_window.PriorityWindow = self.saved_window
        if self.saved is None:
            os.environ.pop(priority_game_session.KEY, None)
        else:
            os.environ[priority_game_session.KEY] = self.saved

    def test_switch_off_is_passthrough(self):
        os.environ.pop(priority_game_session.KEY, None)
        session = priority_game_session.wrap(Base)()
        self.assertEqual(session.tick(), 1)
        self.assertEqual(self.windows, [])
        self.assertNotIn('priority_window', session.summary())

    def test_switch_on_wraps_every_tick(self):
        os.environ[priority_game_session.KEY] = '1'
        session = priority_game_session.wrap(Base)()
        session.tick()
        session.tick()
        self.assertEqual(len(self.windows), 1)
        self.assertEqual(self.windows[0].steps, 2)
        self.assertEqual(session.summary()['priority_window']['steps'], 2)

    def test_tick_exception_propagates(self):
        os.environ[priority_game_session.KEY] = '1'

        class Boom(Base):
            def tick(self):
                raise RuntimeError('boom')

        session = priority_game_session.wrap(Boom)()
        with self.assertRaises(RuntimeError):
            session.tick()
        self.assertEqual(self.windows[0].steps, 1)

    def test_frozen_base_unchanged(self):
        os.environ.pop(priority_game_session.KEY, None)
        session = priority_game_session.wrap(Base)()
        self.assertEqual(session.summary(), dict(base=True))
        self.assertEqual(session.ticks, 0)

    def test_switch_reads_environment_at_construction(self):
        os.environ.pop(priority_game_session.KEY, None)
        off = priority_game_session.wrap(Base)()
        os.environ[priority_game_session.KEY] = '1'
        on = priority_game_session.wrap(Base)()
        self.assertIsNone(off._priority)
        self.assertIsNotNone(on._priority)


if __name__ == '__main__':
    unittest.main()
