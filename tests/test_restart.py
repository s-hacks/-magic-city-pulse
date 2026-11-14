import signal
import unittest
from unittest.mock import patch
from scripts import restart_app


class Restart(unittest.TestCase):
    def test_unrelated_listener_is_never_killed(self):
        with patch.object(restart_app,'listeners',return_value={123}),patch.object(restart_app,'is_project_server',return_value=False),patch.object(restart_app.os,'kill') as kill:
            with self.assertRaises(RuntimeError): restart_app.stop_existing(8000)
        kill.assert_not_called()
    def test_waits_for_socket_release(self):
        with patch.object(restart_app,'listeners',side_effect=[{123},{123},set()]),patch.object(restart_app,'is_project_server',return_value=True),patch.object(restart_app,'port_available',return_value=True),patch.object(restart_app.os,'kill') as kill,patch.object(restart_app.time,'sleep') as sleep:
            restart_app.stop_existing(8000)
        kill.assert_called_once_with(123,signal.SIGTERM);sleep.assert_called_once()
    def test_no_listener_is_already_ready_to_start(self):
        with patch.object(restart_app,'listeners',return_value=set()),patch.object(restart_app,'port_available',return_value=True),patch.object(restart_app.os,'kill') as kill:
            restart_app.stop_existing(8000)
        kill.assert_not_called()

if __name__=='__main__':unittest.main()
