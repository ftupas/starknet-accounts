import sys
import json
import asyncio

sys.path.append('./')

from console import blue_strong, blue, red
from utils import deploy_account, invoke_tx_hash, print_n_wait, fund_account, get_evaluator, get_client
from starkware.starknet.public.abi import get_selector_from_name
from starkware.crypto.signature.signature import private_to_stark_key, sign

with open("./hints.json", "r") as f:
  data = json.load(f)

async def main():
    blue_strong.print("Your mission:")
    blue.print("\t 1) implement account execution similar to OpenZeppelin w/ AccountCallArray")
    blue.print("\t 2) deploy account contract")
    blue.print("\t 3) format and sign invocations and calldata")
    blue.print("\t 4) invoke multiple contracts in the same block\n")

    private_key = data['PRIVATE_KEY']
    stark_key = private_to_stark_key(private_key)

    client = get_client()

    multicall, multicall_addr = await deploy_account(client=client, contract_path=data['MULTICALL'], constructor_args=[stark_key])
    
    reward_account = await fund_account(multicall_addr)
    if reward_account == "":
      red.print("Account must have ETH to cover transaction fees")
      return

    _, evaluator_address = await get_evaluator(client)
    

    selector = get_selector_from_name("validate_multicall")
    
    #
    # ACTION ITEM 1: format the 'CallArray'
    #
    call_array = [
        {
            "to": evaluator_address,
            "selector": selector,
            "data_offset": 0,
            "data_len": 1
        },
        {
            "to": evaluator_address,
            "selector": selector,
            "data_offset": 1,
            "data_len": 1
        },
        {
            "to": evaluator_address,
            "selector": selector,
            "data_offset": 2,
            "data_len": 1
        },
    ]
    
    (nonce, ) = await multicall.functions["get_nonce"].call()

    #
    # ACTION ITEM 2: format the 'CalldataArray'
    #
    inner_calldata = [reward_account, reward_account, reward_account]
    calldata = [
        nonce, len(call_array),
        evaluator_address, selector, 0, 1,
        evaluator_address, selector, 1, 1,
        evaluator_address, selector, 2, 1,
        len(inner_calldata), *inner_calldata
    ]

    hash = invoke_tx_hash(multicall_addr, calldata)
    signature = sign(hash, private_key)

    prepared = multicall.functions["__execute__"].prepare(
        nonce=nonce,
        call_array_len=len(call_array),
        call_array=call_array,
        calldata_len=len(inner_calldata),
        calldata=inner_calldata,
    )

    invocation = await prepared.invoke(signature=signature, max_fee=data['MAX_FEE'])

    await print_n_wait(client, invocation)


asyncio.run(main())
