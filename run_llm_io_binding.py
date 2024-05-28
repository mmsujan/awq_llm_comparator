# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# --------------------------------------------------------------------------

# This program will run the ONNX version of the LLM.
import argparse
import os
import time

import numpy as np
import onnxruntime
from transformers import AutoTokenizer
from chat_templates import get_chat_template
from model_type_mapping import get_supported_llm_models, get_model_dir


np.random.seed(1024)
def run_llm_io_binding(
    model_type: str,
    prompt: str,
    prompt_size: int = 256,
    max_seq_len: int = 2048,
    max_gen_len: int = 256,
    device: str = "dml",
    device_id: int = 0,
    ignore_eos: bool = False,
) -> str:
    onnxruntime.set_default_logger_severity(3)

    execution_provider = {
        "dml": "DmlExecutionProvider",
        "cuda": "CUDAExecutionProvider",
    }[device]

    # Create the ONNX session
    providers = [
        (
            execution_provider,
            {
                "device_id": device_id,
            },
        )
    ]

    model_dir = get_model_dir(model_type)
    llm_session_options = onnxruntime.SessionOptions()
    llm_session_options.add_free_dimension_override_by_name("batch_size", 1)
    llm_session_options.add_free_dimension_override_by_name("max_seq_len", max_seq_len)
    llm_session_options.add_free_dimension_override_by_name("seq_len_increment", 1)

    llm_session = onnxruntime.InferenceSession(
        os.path.join(model_dir, "decoder_model_merged.onnx"),
        sess_options=llm_session_options,
        providers=providers,
    )
    data_type = np.float16
    num_layers = 0
    for inputs_meta in llm_session._inputs_meta:
        if inputs_meta.name.startswith("cache.") and inputs_meta.name.endswith(".key"):
            num_layers += 1
            num_key_value_heads = inputs_meta.shape[1]
            head_dim = inputs_meta.shape[3]

    # Initialize the tokenizer and produce the initial tokens.
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    tokenizer.chat_template = get_chat_template(model_type) or tokenizer.chat_template

    tokens = tokenizer.apply_chat_template([{"role": "user", "content": prompt}], return_tensors="np")
    tokens = np.asarray(tokens, dtype=np.int64)
    if model_type == "llama-2-7b-chat" or  model_type == " mistral-7b-chat":
        tokens = np.resize(tokens, (1, prompt_size))
    
    tokens = onnxruntime.OrtValue.ortvalue_from_numpy(tokens, device)
    tokens_increment = onnxruntime.OrtValue.ortvalue_from_shape_and_type((1, 1), np.int64, device)

    past_seq_len = 0
    seq_len = tokens.shape()[1]

    # Create the LLM model's I/O binding
    llm_io_binding = llm_session.io_binding()

    # Create the K and V caches.
    cache_shape = (1, num_key_value_heads, max_seq_len, head_dim)
    initial_cache = np.zeros(cache_shape, dtype=data_type)
    k_caches = []
    v_caches = []

    for _ in range(num_layers):
        k_caches.append(onnxruntime.OrtValue.ortvalue_from_numpy(initial_cache, device))
        v_caches.append(onnxruntime.OrtValue.ortvalue_from_numpy(initial_cache, device))

    llm_io_binding.bind_cpu_input("use_cache_branch", np.zeros([1], dtype=np.bool_))
    llm_io_binding.bind_output("logits", device)
    llm_io_binding.bind_ortvalue_input("tokens", tokens)
    llm_io_binding.bind_ortvalue_input("tokens_increment", tokens_increment)

    before_time = time.perf_counter()
    before_time_first_token = time.perf_counter()  
    # Iteratively generate tokens.
    output_tokens = []
    for idx in range(max_gen_len):
        if idx == 0:
            position_ids = np.arange(seq_len, dtype=np.int64).reshape((1, seq_len))
            llm_io_binding.bind_cpu_input("position_ids", position_ids)
        else:
            position_ids_increment = np.array(seq_len - 1, dtype=np.int64, ndmin=2)
            llm_io_binding.bind_cpu_input("position_ids_increment", position_ids_increment)

        seqlens_k = np.array(past_seq_len, dtype=np.int32, ndmin=1)
        llm_io_binding.bind_cpu_input("seqlens_k", seqlens_k)

        for layer_idx in range(num_layers):
            llm_io_binding.bind_ortvalue_input(f"cache.{layer_idx}.key", k_caches[layer_idx])
            llm_io_binding.bind_ortvalue_input(f"cache.{layer_idx}.value", v_caches[layer_idx])
            llm_io_binding.bind_ortvalue_output(f"cache_out.{layer_idx}.key", k_caches[layer_idx])
            llm_io_binding.bind_ortvalue_output(f"cache_out.{layer_idx}.value", v_caches[layer_idx])

        # Run the LLM
        llm_session.run_with_iobinding(llm_io_binding)

        # Decide the next token using your preferred sampling strategy.
        logits = llm_io_binding.get_outputs()[0].numpy()[:, -1, :]
        next_token = np.argmax(logits, axis=-1, keepdims=True)
        output_tokens.append(next_token.item())

        # Set the token for the next iteration
        llm_io_binding.bind_cpu_input("tokens_increment", next_token)

        # Stop if/when we get an ENDOFTEXT token before reaching maximum sequence length
        if not ignore_eos and output_tokens[-1] == tokenizer.eos_token_id:
            break

        if idx == 0:
            llm_io_binding.bind_cpu_input("use_cache_branch", np.ones([1], dtype=np.bool_))
            llm_io_binding.bind_output("logits", device)
            after_time_first_token = time.perf_counter()

        past_seq_len = seq_len
        seq_len += 1

    after_time = time.perf_counter()
    duration = after_time - before_time
    #tokens_per_second = idx / duration
    first_token_latency = after_time_first_token - before_time_first_token
    tokens_per_second = (idx - 1) / (duration - first_token_latency)
    
    if model_type == "phi-2":
        tokens_per_second = idx / duration

    # Only print the tokens/s when ignore_eos is provided for benchmarking purposes
    if ignore_eos:
        if model_type == "llama-2-7b-chat" or  model_type == "mistral-7b-chat":
            print(f"Execution took {duration:0.4f} seconds (generated {tokens_per_second:0.2f} tokens per second for 2nd+ token). First token latency: {first_token_latency:0.2f} seconds.")
        else:
            print(f"Execution took {duration:0.4f} seconds (generated {tokens_per_second:0.2f} tokens per second)")

    output_str = tokenizer.decode(output_tokens, skip_special_tokens=True)
    
    f = open("./generatedOutput/"+ model_type +"/output.txt", "w")
    f.write(output_str)
    f.close()
    print(output_str)
    
    
def llm_params(parser):
    parser.add_argument("--prompt", type=str, default="What is the lightest element?")
    parser.add_argument("--input_seq_len", type=int, default=256)
    parser.add_argument("--max_seq_len", type=int, default=2048)
    parser.add_argument("--max_gen_len", type=int, default=256)
    parser.add_argument("--ignore_eos", action="store_true")
    parser.add_argument("--device", type=str, choices=["dml", "cuda"], default="dml")
    parser.add_argument("--device_id", type=int, default=0)
    parser.add_argument(
        "--model_type",
        choices=get_supported_llm_models(),
        help="Which model to run.",
        required=True,
        type=str,
    )
def llm_main(args):
    if args.input_seq_len == 0:
        print("Input seq len cant be 0!")
    else:
    
        run_llm_io_binding(
            args.model_type,
            args.prompt,
            args.input_seq_len,
            args.max_seq_len,
            args.max_gen_len,
            args.device,
            args.device_id,
            args.ignore_eos,
        )

"""
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", type=str, default="What is the lightest element?")
    parser.add_argument("--max_seq_len", type=int, default=2048)
    parser.add_argument("--max_gen_len", type=int, default=256)
    parser.add_argument("--ignore_eos", action="store_true")
    parser.add_argument("--device", type=str, choices=["dml", "cuda"], default="dml")
    parser.add_argument("--device_id", type=int, default=0)
    parser.add_argument(
        "--model_type",
        choices=get_supported_llm_models(),
        help="Which model to run.",
        required=True,
        type=str,
    )

    args = parser.parse_args()
    run_llm_io_binding(
        args.model_type,
        args.prompt,
        args.max_seq_len,
        args.max_gen_len,
        args.device,
        args.device_id,
        args.ignore_eos,
    )
"""