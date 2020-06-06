#!/usr/bin/python3
import brownie
import pytest
from brownie import *
from brownie.test import given
from hypothesis import settings, strategies as st


ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
FEE_MODIFIER = 995
ADDITIONAL_TOKENS_MINTED = 60
TOKENS_ADDED_TO_LIQUIDITY = 80
ETHER_ADDED_TO_LIQUIDITY = Wei("5 ether")

st_amount_eth_to_sell = st.integers(min_value=int(Wei("1 gwei")), max_value=int(Wei("10 ether")))
st_amount_token_to_buy = st.integers(min_value=1, max_value=int(TOKENS_ADDED_TO_LIQUIDITY * 0.9))


def eth_to_token_input(eth_to_sell: int) -> "Wei":
    """ Constant Price Model implementation with fee. """
    input_amount_with_fee = eth_to_sell * FEE_MODIFIER
    numerator = input_amount_with_fee * TOKENS_ADDED_TO_LIQUIDITY
    denominator = ETHER_ADDED_TO_LIQUIDITY * 1000 + input_amount_with_fee
    return Wei(numerator // denominator)


def eth_to_token_output(tokens_to_buy: int) -> "Wei":
    """ Constant Price Model implementation with fee. """
    numerator = ETHER_ADDED_TO_LIQUIDITY * tokens_to_buy * 1000
    denominator = (TOKENS_ADDED_TO_LIQUIDITY - tokens_to_buy) * FEE_MODIFIER
    return Wei(numerator // denominator + 1)


@pytest.fixture(scope="module")
def liquid_lgt(lgt, accounts):
    lgt.mint(ADDITIONAL_TOKENS_MINTED, {'from': accounts[0]})
    lgt.addLiquidity(0, TOKENS_ADDED_TO_LIQUIDITY, 99999999999, {'from': accounts[0], 'value': ETHER_ADDED_TO_LIQUIDITY})
    yield lgt


@given(eth_to_sell=st_amount_eth_to_sell)
@settings(max_examples=50)
def test_swap_input(liquid_lgt, accounts, eth_to_sell):
    initial_balance = accounts[2].balance()
    initial_reserve = liquid_lgt.balance()
    correct_tokens_received = eth_to_token_input(eth_to_sell)
    lgt_tokens_received = liquid_lgt.getEthToTokenInputPrice(eth_to_sell)
    assert correct_tokens_received == lgt_tokens_received
    if correct_tokens_received >= 1:
        tx = liquid_lgt.ethToTokenSwapInput(1, 99999999999, {'from': accounts[2], 'value': eth_to_sell})
        assert liquid_lgt.balanceOf(accounts[2]) == int(correct_tokens_received)
        assert tx.return_value == int(correct_tokens_received)
        assert initial_balance - eth_to_sell == accounts[2].balance()
        assert initial_reserve + eth_to_sell == liquid_lgt.balance()
    else:
        with brownie.reverts("dev: not enough eth to buy tokens"):
            liquid_lgt.ethToTokenSwapInput(1, 99999999999, {'from': accounts[2], 'value': eth_to_sell})


@given(eth_to_sell=st_amount_eth_to_sell)
@settings(max_examples=5)
def test_transfer_input(liquid_lgt, accounts, eth_to_sell):
    correct_tokens_received = eth_to_token_input(eth_to_sell)
    lgt_tokens_received = liquid_lgt.getEthToTokenInputPrice(eth_to_sell)
    assert correct_tokens_received == lgt_tokens_received
    if correct_tokens_received >= 1:
        tx = liquid_lgt.ethToTokenTransferInput(1, 99999999999, accounts[3], {'from': accounts[2], 'value': eth_to_sell})
        assert tx.return_value == correct_tokens_received
        assert liquid_lgt.balanceOf(accounts[3]) == correct_tokens_received
    else:
        with brownie.reverts("dev: not enough eth to buy tokens"):
            liquid_lgt.ethToTokenTransferInput(1, 99999999999, accounts[3], {'from': accounts[2], 'value': eth_to_sell})


def test_input_deadline_reverts(liquid_lgt, accounts):
    with brownie.reverts("dev: deadline passed"):
        liquid_lgt.ethToTokenTransferInput(1, 1, accounts[3], {'from': accounts[2], 'value': "0.2 ether"})


def test_input_no_eth_reverts(liquid_lgt, accounts):
    with brownie.reverts("dev: no eth to sell"):
        liquid_lgt.ethToTokenTransferInput(1, 99999999999, accounts[3], {'from': accounts[2], 'value': "0 ether"})


def test_input_no_min_tokens_reverts(liquid_lgt, accounts):
    with brownie.reverts("dev: must buy one or more tokens"):
        liquid_lgt.ethToTokenTransferInput(0, 99999999999, accounts[3], {'from': accounts[2], 'value': "0.2 ether"})


def test_input_not_enough_eth_reverts(liquid_lgt, accounts):
    with brownie.reverts("dev: not enough eth to buy tokens"):
        liquid_lgt.ethToTokenTransferInput(25, 99999999999, accounts[3], {'from': accounts[2], 'value': "0.2 ether"})


def test_input_to_lgt_eth_reverts(liquid_lgt, accounts):
    with brownie.reverts("dev: can't send to liquid token contract"):
        liquid_lgt.ethToTokenTransferInput(25, 99999999999, liquid_lgt, {'from': accounts[2], 'value': "0.2 ether"})


def test_input_to_zero_eth_reverts(liquid_lgt, accounts):
    with brownie.reverts("dev: can't send to zero address"):
        liquid_lgt.ethToTokenTransferInput(25, 99999999999, ZERO_ADDRESS, {'from': accounts[2], 'value': "0.2 ether"})


@given(tokens_to_buy=st_amount_token_to_buy)
@settings(max_examples=10)
def test_swap_output(liquid_lgt, accounts, tokens_to_buy):
    initial_balance = accounts[2].balance()
    correct_eth_paid = eth_to_token_output(tokens_to_buy)
    lgt_eth_paid = liquid_lgt.getEthToTokenOutputPrice(tokens_to_buy)
    assert correct_eth_paid == lgt_eth_paid
    tx = liquid_lgt.ethToTokenSwapOutput(tokens_to_buy, 99999999999, {'from': accounts[2], 'value': "50 ether"})
    assert liquid_lgt.balanceOf(accounts[2]) == tokens_to_buy
    assert tx.return_value == lgt_eth_paid
    assert initial_balance - tx.return_value == accounts[2].balance()


@given(tokens_to_buy=st_amount_token_to_buy)
@settings(max_examples=5)
def test_transfer_output(liquid_lgt, accounts, tokens_to_buy):
    initial_balance = accounts[2].balance()
    correct_eth_paid = eth_to_token_output(tokens_to_buy)
    lgt_eth_paid = liquid_lgt.getEthToTokenOutputPrice(tokens_to_buy)
    assert correct_eth_paid == lgt_eth_paid
    tx = liquid_lgt.ethToTokenTransferOutput(tokens_to_buy, 99999999999, accounts[3], {'from': accounts[2], 'value': "50 ether"})
    assert liquid_lgt.balanceOf(accounts[3]) == tokens_to_buy
    assert tx.return_value == correct_eth_paid
    assert initial_balance - tx.return_value == accounts[2].balance()


def test_output_deadline_reverts(liquid_lgt, accounts):
    with brownie.reverts("dev: deadline passed"):
        liquid_lgt.ethToTokenTransferOutput(1, 1, accounts[3], {'from': accounts[2], 'value': "0.2 ether"})


def test_output_no_max_eth_reverts(liquid_lgt, accounts):
    with brownie.reverts("dev: maxEth must greater than 0"):
        liquid_lgt.ethToTokenTransferOutput(1, 99999999999, accounts[3], {'from': accounts[2], 'value': "0 ether"})


def test_output_no_min_tokens_reverts(liquid_lgt, accounts):
    with brownie.reverts("dev: must buy one or more tokens"):
        liquid_lgt.ethToTokenTransferOutput(0, 99999999999, accounts[3], {'from': accounts[2], 'value': "0.2 ether"})


def test_output_not_enough_eth_reverts(liquid_lgt, accounts):
    with brownie.reverts("LGT: not enough ETH to buy tokens"):
        liquid_lgt.ethToTokenTransferOutput(25, 99999999999, accounts[3], {'from': accounts[2], 'value': "0.01 ether"})


def test_output_to_lgt_reverts(liquid_lgt, accounts):
    with brownie.reverts("dev: can't send to liquid token contract"):
        liquid_lgt.ethToTokenTransferOutput(1, 1, liquid_lgt, {'from': accounts[2], 'value': "0.2 ether"})


def test_output_to_zero_reverts(liquid_lgt, accounts):
    with brownie.reverts("dev: can't send to zero address"):
        liquid_lgt.ethToTokenTransferOutput(1, 1, ZERO_ADDRESS, {'from': accounts[2], 'value': "0.2 ether"})
