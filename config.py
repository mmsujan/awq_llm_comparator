# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# --------------------------------------------------------------------------

decoder_model = None
normalization_type = None
state_dict = None
strict_weights_loading = True
hidden_size = 4096
intermediate_size = 11008
num_heads = 32
num_key_value_heads = 32
num_layers = 32
vocab_size = 32000
epsilon = 1e-5
model_type = "llama"
apply_residual_connection_post_layernorm = True
model_id = "meta-llama/Llama-2-7b-chat-hf"
partial_rotary_factor = 1.0
max_position_embeddings = 4096
