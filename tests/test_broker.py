import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from paper_trader.broker import PaperBroker
from paper_trader.core import Config, Proposal, SafetyError
from paper_trader.journal import Journal


class BrokerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.journal = Journal(Path(self.tmp.name) / "journal.sqlite")
        self.cfg = Config(account="DU123", kill_file=str(Path(self.tmp.name) / "STOP"))
        self.broker = PaperBroker(self.cfg, self.journal)
        self.broker.ib = SimpleNamespace(
            managedAccounts=lambda: ["DU123"], isConnected=lambda: True, placeOrder=Mock()
        )

    async def asyncTearDown(self):
        self.journal.db.close()
        self.tmp.cleanup()

    async def test_account_gate(self):
        self.broker.guard()
        for accounts in ([], ["U123"], ["DU999"], ["DU123", "U123"], ["DU123", "DU999"]):
            self.broker.ib.managedAccounts = lambda accounts=accounts: accounts
            with self.subTest(accounts=accounts), self.assertRaises(SafetyError):
                self.broker.guard()

    async def test_disconnect_and_restore_require_restart(self):
        for code in (1100, 1101, 1102, 1300, 2103, 2105, 2110):
            self.broker.fault = False
            self.broker._error(-1, code, "test")
            with self.assertRaises(SafetyError):
                self.broker.guard()
        self.broker.fault = False
        self.broker._disconnect()
        with self.assertRaises(SafetyError):
            self.broker.guard()

    async def test_readonly_adapter_cannot_place(self):
        self.broker.contract = AsyncMock(return_value=object())
        p = Proposal("test", "SPY", "BUY", 1, 500, datetime.now(UTC))
        with self.assertRaises(SafetyError):
            await self.broker.send_approved(p)
        self.broker.ib.placeOrder.assert_not_called()

    async def test_final_adapter_kill_gate(self):
        self.broker.writable = True
        self.broker.contract = AsyncMock(return_value=object())
        Path(self.cfg.kill_file).touch()
        p = Proposal("test", "SPY", "BUY", 1, 500, datetime.now(UTC))
        with self.assertRaises(SafetyError):
            await self.broker.send_approved(p)
        self.broker.ib.placeOrder.assert_not_called()
