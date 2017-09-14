import logging
import os
import sys
import time

import pytest
from click.testing import CliRunner


class TestCli(object):

    @pytest.mark.order1
    def test_help(self, capsys):
        # --help
        runner = CliRunner()
        sys.argv = ['fakedaemon', '-I', 'intents/', '-w', 'tests/workdir/', '-D', 'bad_dialogs']
        with pytest.raises(SystemExit):
            from tuxeatpi_nlu_nuance.common import cli
