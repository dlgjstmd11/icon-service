# -*- coding: utf-8 -*-

# Copyright 2017-2018 theloop Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from unittest.mock import Mock

from iconservice.base.address import Address, AddressPrefix, ZERO_SCORE_ADDRESS, generate_score_address
from iconservice.base.exception import ExceptionCode, InvalidRequestException, \
    InvalidParamsException
from iconservice.deploy.icon_score_manager import IconScoreManager
from iconservice.iconscore.icon_pre_validator import IconPreValidator
from iconservice.iconscore.icon_score_info_mapper import IconScoreInfoMapper
from iconservice.icx.icx_engine import IcxEngine
from tests import create_tx_hash, create_address


def f(key):
    return False


class TestTransactionValidator(unittest.TestCase):
    def setUp(self):
        self.icx_engine = Mock(spec=IcxEngine)
        self.score_manager = Mock(spec=IconScoreManager)

        # self.score_mapper = Mock(spec=IconScoreInfoMapper)
        self.score_mapper = {}

        self.validator = IconPreValidator(
            self.icx_engine, self.score_manager, self.score_mapper)

    def tearDown(self):
        self.icx_engine = None
        self.score_manager = None
        self.score_mapper = None
        self.validator = None

    def test_validate_success(self):
        params = {
            'version': 3,
            'txHash': create_tx_hash(b'tx'),
            'from': create_address(AddressPrefix.EOA, b'from'),
            'to': create_address(AddressPrefix.CONTRACT, b'to'),
            'value': 0,
            'stepLimit': 100,
            'timestamp': 123456,
            'nonce': 1
        }

        self.icx_engine.get_balance = Mock(return_value=100)
        self.validator.execute(params, step_price=1)

    def test_negative_balance(self):
        step_price = 0
        self.icx_engine.get_balance = Mock(return_value=0)

        params = {
            'version': 3,
            'txHash': create_tx_hash(b'tx'),
            'from': create_address(AddressPrefix.EOA, b'from'),
            'to': create_address(AddressPrefix.CONTRACT, b'to'),
            'value': -10,
            'stepLimit': 100,
            'timestamp': 123456,
            'nonce': 1
        }

        # too small balance
        with self.assertRaises(InvalidParamsException) as cm:
            self.validator.execute(params, step_price)

        self.assertEqual(ExceptionCode.INVALID_PARAMS, cm.exception.code)
        self.assertEqual('value < 0', cm.exception.message)

    def test_check_balance(self):
        step_price = 0
        self.icx_engine.get_balance = Mock(return_value=0)

        params = {
            'version': 3,
            'txHash': create_tx_hash(b'tx'),
            'from': create_address(AddressPrefix.EOA, b'from'),
            'to': create_address(AddressPrefix.CONTRACT, b'to'),
            'value': 10,
            'stepLimit': 100,
            'timestamp': 123456,
            'nonce': 1
        }

        # too small balance
        with self.assertRaises(InvalidRequestException) as cm:
            self.validator.execute(params, step_price)

        self.assertEqual(ExceptionCode.INVALID_REQUEST, cm.exception.code)
        self.assertEqual('Out of balance', cm.exception.message)

        # balance is enough
        self.icx_engine.get_balance = Mock(return_value=100)
        self.validator.execute(params, step_price)

        # too expensive fee
        step_price = 1
        with self.assertRaises(InvalidRequestException) as cm:
            self.validator.execute(params, step_price)

        self.assertEqual(ExceptionCode.INVALID_REQUEST, cm.exception.code)
        self.assertEqual('Out of balance', cm.exception.message)

    def test_transfer_to_invalid_score_address(self):
        self.icx_engine.get_balance = Mock(return_value=1000)
        self.score_manager.is_score_status_active = Mock(return_value=False)
        to = create_address(AddressPrefix.CONTRACT, b'to')

        params = {
            'version': 3,
            'txHash': create_tx_hash(b'tx'),
            'from': create_address(AddressPrefix.EOA, b'from'),
            'to': to,
            'value': 10,
            'stepLimit': 100,
            'timestamp': 123456,
            'nonce': 1
        }

        # The SCORE indicated by to is not installed
        # Invalid SCORE address
        with self.assertRaises(InvalidRequestException) as cm:
            self.validator.execute(params, step_price=1)

        self.assertEqual(ExceptionCode.INVALID_REQUEST, cm.exception.code)
        self.assertEqual(f'Invalid address: {to}', cm.exception.message)

    # TODO FIXME
    # def test_transfer_to_invalid_eoa_address(self):
    #     self.icx_engine.balance = 1000
    #     self.deploy_storage.score_installed = True
    #
    #     to = create_address(AddressPrefix.EOA, b'to')
    #
    #     params = {
    #         'version': 3,
    #         'txHash': create_tx_hash(b'tx'),
    #         'from': create_address(AddressPrefix.EOA, b'from'),
    #         'to': to,
    #         'value': 10,
    #         'stepLimit': 100,
    #         'timestamp': 123456,
    #         'nonce': 1
    #     }
    #
    #     self.validator.execute(params, step_price=1)
    #
    #     self.assertEqual(ExceptionCode.INVALID_REQUEST, cm.exception.code)
    #     self.assertEqual(f'Invalid address: {to}', cm.exception.message)

    def test_execute_to_check_out_of_balance(self):
        step_price = 10 ** 12
        value = 2 * 10 ** 18
        step_limit = 20000

        self.icx_engine.get_balance = Mock(return_value=0)
        self.score_manager.is_score_status_active = Mock(return_value=False)

        to = create_address(AddressPrefix.EOA, b'to')

        params = {
            'version': 3,
            'from': create_address(AddressPrefix.EOA, b'from'),
            'to': to,
            'value': value,
            'stepLimit': step_limit,
            'timestamp': 1234567890,
            'nonce': 1
        }

        # balance is 0
        with self.assertRaises(InvalidRequestException) as cm:
            self.validator.execute_to_check_out_of_balance(params, step_price)

        self.assertEqual(ExceptionCode.INVALID_REQUEST, cm.exception.code)
        self.assertEqual('Out of balance', cm.exception.message)

        # balance(value) < value + fee
        self.icx_engine.get_balance = Mock(return_value=value)

        with self.assertRaises(InvalidRequestException) as cm:
            self.validator.execute_to_check_out_of_balance(params, step_price)

        self.assertEqual(ExceptionCode.INVALID_REQUEST, cm.exception.code)
        self.assertEqual('Out of balance', cm.exception.message)

        # balance is enough to pay coin and fee
        self.icx_engine.get_balance = Mock(return_value=value + step_limit * step_price)
        self.validator.execute_to_check_out_of_balance(params, step_price)

    def test_validate_generated_score_address(self):

        from_ = Address.from_data(AddressPrefix.EOA, b'from')
        timestamp = 1234567890
        nonce = None

        params = {
            'from': from_,
            'to': ZERO_SCORE_ADDRESS,
            'timestamp': timestamp,
            'nonce': nonce,
            'dataType': 'deploy',
            'data': {
                'contentType': 'application/zip',
                'content': '0x1234'
            }
        }

        self.validator._validate_new_score_address_on_deploy_transaction(params)

        score_address: 'Address' =\
            generate_score_address(from_, timestamp, nonce)
        self.score_mapper[score_address] = None

        with self.assertRaises(InvalidRequestException) as cm:
            self.validator._validate_new_score_address_on_deploy_transaction(
                params)

        self.assertEqual(
            cm.exception.message,
            f'SCORE address already in use: {score_address}')

        params['to'] = score_address
        self.validator._validate_new_score_address_on_deploy_transaction(params)


class TestTransactionValidatorV2(unittest.TestCase):
    def setUp(self):
        self.icx_engine = Mock(spec=IcxEngine)
        self.score_manager = Mock(spec=IconScoreManager)
        self.score_mapper = Mock(spec=IconScoreInfoMapper)
        self.validator = IconPreValidator(self.icx_engine, self.score_manager, self.score_mapper)

    def tearDown(self):
        self.icx_engine = None
        self.score_manager = None
        self.score_mapper = None
        self.validator = None

    def test_out_of_balance(self):
        self.icx_engine.get_balance = Mock(return_value=0)
        self.score_manager.is_score_status_active = Mock(return_value=False)

        to = create_address(AddressPrefix.EOA, b'to')

        tx = {
            'txHash': create_tx_hash(b'tx'),
            'from': create_address(AddressPrefix.EOA, b'from'),
            'to': to,
            'value': 10 * 10 ** 18,
            'fee': 10 ** 16,
            'timestamp': 1234567890,
            'nonce': 1
        }

        # too small balance
        with self.assertRaises(InvalidRequestException) as cm:
            self.validator.execute(tx, step_price=0)

        self.assertEqual(ExceptionCode.INVALID_REQUEST, cm.exception.code)
        self.assertEqual('Out of balance', cm.exception.message)

        # too expensive fee
        self.icx_engine.get_balance = Mock(return_value=10 * 10 ** 18)

        with self.assertRaises(InvalidRequestException) as cm:
            self.validator.execute(tx, step_price=0)

        self.assertEqual(ExceptionCode.INVALID_REQUEST, cm.exception.code)
        self.assertEqual('Out of balance', cm.exception.message)

        # balance is enough to pay coin and fee
        self.icx_engine.get_balance = Mock(return_value=10 * 10 ** 18 + 10 ** 16)
        self.validator.execute(tx, step_price=0)

    def test_execute_to_check_out_of_balance(self):
        step_price = 10 ** 12
        self.icx_engine.get_balance = Mock(return_value=0)
        self.score_manager.is_score_status_active = Mock(return_value=False)

        to = create_address(AddressPrefix.EOA, b'to')

        tx = {
            'txHash': create_tx_hash(b'tx'),
            'from': create_address(AddressPrefix.EOA, b'from'),
            'to': to,
            'value': 10 * 10 ** 18,
            'fee': 10 ** 16,
            'timestamp': 1234567890,
            'nonce': 1
        }

        # too small balance
        with self.assertRaises(InvalidRequestException) as cm:
            self.validator.execute_to_check_out_of_balance(tx, step_price)

        self.assertEqual(ExceptionCode.INVALID_REQUEST, cm.exception.code)
        self.assertEqual('Out of balance', cm.exception.message)

        # too expensive fee
        self.icx_engine.get_balance = Mock(return_value=10 * 10 ** 18)

        with self.assertRaises(InvalidRequestException) as cm:
            self.validator.execute_to_check_out_of_balance(tx, step_price)

        self.assertEqual(ExceptionCode.INVALID_REQUEST, cm.exception.code)
        self.assertEqual('Out of balance', cm.exception.message)

        # balance is enough to pay coin and fee
        self.icx_engine.get_balance = Mock(return_value=10 * 10 ** 18 + 10 ** 16)
        self.validator.execute_to_check_out_of_balance(tx, step_price)
