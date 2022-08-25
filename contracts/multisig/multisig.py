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
    blue.print("\t 1) implement a 2/3 multisig contract")
    blue.print("\t 2) implement the following interfaces expected by the validator:")
    blue.print("\t\t - get_confirmations")
    blue.print("\t\t - get_owner_confirmed")
    blue.print("\t\t - get_num_owners")
    blue.print("\t\t - get_owners")
    blue.print("\t 3) implement function for contract owner to submit a tx for the owners to sign")
    blue.print("\t 4) implement function for contract owner confirm a submitted tx")
    blue.print("\t 5) implement function to execute a transaction that has ben confirmed by at least two unique owners")
    blue.print("\t 6) deploy the signers for the multisig")
    blue.print("\t 7) deploy the multisig")
    blue.print("\t 8) submit a transaction to the multisig")
    blue.print("\t 9) confirm the tx")
    blue.print("\t 10) execute the tx\n")

    client = get_client()

    #
    # Deploy first signer
    #
    private_key = data['PRIVATE_KEY']
    stark_key = private_to_stark_key(private_key)
    sig1, sig1_addr = await deploy_account(client=client, contract_path=data['SIGNATURE_BASIC'], constructor_args=[stark_key], additional_data=1)
    reward_account = await fund_account(sig1_addr)
    if reward_account == "":
      red.print("Account must have ETH to cover transaction fees")
      return

    #
    # Deploy second signer
    #
    private_key_2 = private_key + 1
    stark_key_2 = private_to_stark_key(private_key_2)
    sig2, sig2_addr = await deploy_account(client=client, contract_path=data['SIGNATURE_BASIC'], constructor_args=[stark_key_2], additional_data=2)
    reward_account = await fund_account(sig2_addr)
    
    #
    # Deploy thrid signer
    #
    private_key_3 = private_key + 2
    stark_key_3 = private_to_stark_key(private_key_3)
    sig3, sig3_addr = await deploy_account(client=client, contract_path=data['SIGNATURE_BASIC'], constructor_args=[stark_key_3], additional_data=3)
    reward_account = await fund_account(sig3_addr)

    _, evaluator_address = await get_evaluator(client)

    #
    # Deploy multisig constract
    #
    _, multi_addr = await deploy_account(client=client, contract_path=data['MULTISIG'], constructor_args=[[sig1_addr, sig2_addr, sig3_addr]])
    

    validator_selector = get_selector_from_name("validate_multisig")
    submit_selector = get_selector_from_name("submit_tx")

    #
    # ACTION ITEM 3: submit a transaction to the multisig
    #
    (nonce_1, ) = await sig1.functions["get_nonce"].call()
    inner_calldata=[evaluator_address, validator_selector, 2, 1, reward_account]
    outer_calldata=[multi_addr, submit_selector, nonce_1, len(inner_calldata), *inner_calldata]

    hash = invoke_tx_hash(sig1_addr, outer_calldata)
    sub_signature = sign(hash, private_key)

    sub_prepared = sig1.functions["__execute__"].prepare(
      contract_address=multi_addr,
      selector=submit_selector,
      nonce=nonce_1,
      calldata_len=len(inner_calldata),
      calldata=inner_calldata
    )
    #
    # <CODE>
    #
    
    sub_invocation = await sub_prepared.invoke(signature=sub_signature, max_fee=data['MAX_FEE'])

    eventData = await print_n_wait(client, sub_invocation)

    #
    # ACTION ITEM 4: provide first tx confirmation
    #
    confirm_selector = get_selector_from_name("confirm_tx")

    #
    # <CODE>
    #
    (nonce_2, ) = await sig2.functions["get_nonce"].call()
    conf_calldata = [multi_addr, confirm_selector, nonce_2, 1, eventData[1]]
    conf_hash = invoke_tx_hash(sig2_addr, conf_calldata)

    conf_signature = sign(conf_hash, private_key_2)

    conf_prepared = sig2.functions["__execute__"].prepare(
        contract_address=multi_addr,
        selector=confirm_selector,
        nonce=nonce_2,
        calldata_len=1,
        calldata=[eventData[1]])
    conf_invocation = await conf_prepared.invoke(signature=conf_signature, max_fee=data['MAX_FEE'])

    await print_n_wait(client, conf_invocation)

    #
    # Provide second tx confirmation
    #
    (nonce_3, ) = await sig3.functions["get_nonce"].call()
    conf_2_calldata=[multi_addr, confirm_selector, nonce_3, 1, eventData[1]]

    conf_2_hash = invoke_tx_hash(sig3_addr, conf_2_calldata)

    conf_2_signature = sign(conf_2_hash, private_key_3)

    conf_2_prepared = sig3.functions["__execute__"].prepare(
        contract_address=multi_addr,
        selector=confirm_selector,
        nonce=nonce_3,
        calldata_len=1,
        calldata=[eventData[1]])
    conf_2_invocation = await conf_2_prepared.invoke(signature=conf_2_signature, max_fee=data['MAX_FEE'])

    await print_n_wait(client, conf_2_invocation)

    #
    # Execute a submitted confirmed transaction
    #
    execute_selector = get_selector_from_name("__execute__")
    exec_calldata=[multi_addr, execute_selector, nonce_1+1, 1, eventData[1]]

    exec_hash = invoke_tx_hash(sig1_addr, exec_calldata)
    exec_signature = sign(exec_hash, private_key)
    
    exec_prepared = sig1.functions["__execute__"].prepare(
        contract_address=multi_addr,
        selector=execute_selector,
        nonce=nonce_1+1,
        calldata_len=1,
        calldata=[eventData[1]])
    exec_invocation = await exec_prepared.invoke(signature=exec_signature, max_fee=data['MAX_FEE'])

    await print_n_wait(client, exec_invocation)

asyncio.run(main())
