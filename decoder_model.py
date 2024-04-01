# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# --------------------------------------------------------------------------

import numpy as np
import torch

import config

class DecoderModel(torch.nn.Module):
    def __init__(
        self,
        model_type: str,
        n_layers: int,
        vocab_size: int,
        hidden_size: int,
        intermediate_size: int,
        num_heads: int,
        num_key_value_heads: int,
        scale_type: str,
        normalization_type: str,
        epsilon: float,
        apply_residual_connection_post_layernorm: bool,
        use_embeddings: bool = False,
    ) -> None:
        super().__init__()
        self.use_embeddings = use_embeddings
        self.model = Model(
            model_type,
            n_layers,
            vocab_size,
            hidden_size,
            intermediate_size,
            num_heads,
            num_key_value_heads,
            scale_type,
            normalization_type,
            epsilon,
            apply_residual_connection_post_layernorm,
            use_embeddings,
        )
        self.lm_head = torch.nn.Linear(hidden_size, vocab_size, bias=config.partial_rotary_factor!=1.0)

    def forward_common(self, use_cache, tokens_or_embeddings, position_ids_increment, attention_mask, cache):
        hidden_states, k_caches, v_caches = self.model(
            use_cache, tokens_or_embeddings, position_ids_increment, attention_mask, cache
        )
        logits = self.lm_head(hidden_states)

        return_values = [logits]

        for k_cache, v_cache in zip(k_caches, v_caches):
            return_values.append(k_cache)
            return_values.append(v_cache)

        return return_values

    def forward_no_cache_tokens(self, tokens, position_ids, attention_mask, cache):
        use_cache = False
        return self.forward_common(use_cache, tokens, position_ids, attention_mask, cache)

    def forward_no_cache_embeddings(self, embeddings, position_ids, attention_mask, cache):
        use_cache = False
        return self.forward_common(use_cache, embeddings, position_ids, attention_mask, cache)

    def forward_use_cache_tokens(self, tokens_increment, position_ids_increment, attention_mask, cache):
        use_cache = True
        return self.forward_common(use_cache, tokens_increment, position_ids_increment, attention_mask, cache)

    def forward_use_cache_embeddings(self, embeddings_increment, position_ids_increment, attention_mask, cache):
        use_cache = True
        return self.forward_common(use_cache, embeddings_increment, position_ids_increment, attention_mask, cache)

    def set_use_cache(self, use_cache):
        if self.use_embeddings:
            self.forward = self.forward_use_cache_embeddings if use_cache else self.forward_no_cache_embeddings
        else:
            self.forward = self.forward_use_cache_tokens if use_cache else self.forward_no_cache_tokens

    def get_embeddings(self):
        return self.model.embed_tokens


class Model(torch.nn.Module):
    def __init__(
        self,
        model_type: str,
        n_layers: int,
        vocab_size: int,
        hidden_size: int,
        intermediate_size: int,
        num_heads: int,
        num_key_value_heads: int,
        scale_type: str,
        normalization_type: str,
        epsilon: float,
        apply_residual_connection_post_layernorm: bool,
        use_embeddings: bool,
    ) -> None:
        super().__init__()
        self.use_embeddings = use_embeddings
        self.embed_tokens = torch.nn.Embedding(vocab_size, hidden_size)

        self.norm = {
            "layer_norm": torch.nn.LayerNorm(hidden_size, epsilon),
            "rms": RMSNorm(hidden_size, epsilon),
        }[normalization_type]

        self.layers = torch.nn.ModuleList()
        for _ in range(n_layers):
            layer = TransformerLayer(
                model_type,
                hidden_size,
                intermediate_size,
                num_heads,
                num_key_value_heads,
                scale_type,
                normalization_type,
                epsilon,
                apply_residual_connection_post_layernorm,
            )
            self.layers.append(layer)

    def forward(self, use_cache, tokens_or_embeddings, position_ids, attention_mask, cache):
        k_caches = []
        v_caches = []

        x = tokens_or_embeddings if self.use_embeddings else self.embed_tokens(tokens_or_embeddings)

        for layer_idx, layer in enumerate(self.layers):
            k_cache = cache[layer_idx]["key"].clone().detach()
            v_cache = cache[layer_idx]["value"].clone().detach()

            x, k_cache, v_cache = layer(use_cache, x, position_ids, attention_mask, k_cache, v_cache)

            k_caches.append(k_cache)
            v_caches.append(v_cache)

        return self.norm(x), k_caches, v_caches


def rotary_mat(
    hidden_size: int,
    num_heads: int,
    max_seq_len: int,
    theta: float = 10000.0,
    head_scale=1.0,
    dtype=torch.float32,
) -> tuple[torch.Tensor, torch.Tensor]:
    head_dim = head_scale * hidden_size / num_heads

    pos = torch.arange(0, head_dim, step=2, dtype=dtype)
    freqs = 1.0 / (theta ** (pos / head_dim))

    idx = torch.arange(max_seq_len)
    freqs = torch.outer(idx.to(dtype), freqs)
    freqs = torch.cat((freqs, freqs), dim=-1)

    cos = torch.cos(freqs)
    sin = torch.sin(freqs)
    dtype = torch.get_default_dtype()

    return cos.to(dtype), sin.to(dtype)


class RMSNorm(torch.nn.Module):
    def __init__(self, dim: int, eps: float) -> None:
        super().__init__()
        self.eps = eps
        self.weight = torch.nn.Parameter(torch.ones(dim))

    def forward(self, hidden_states):
        input_dtype = hidden_states.dtype
        hidden_states = hidden_states.to(torch.float32)
        variance = hidden_states.pow(2).mean(-1, keepdim=True)
        hidden_states = hidden_states * torch.rsqrt(variance + self.eps)
        return self.weight * hidden_states.to(input_dtype)


class TransformerLayer(torch.nn.Module):
    def __init__(
        self,
        model_type: str,
        hidden_size: int,
        intermediate_size: int,
        num_heads: int,
        num_key_value_heads: int,
        scale_type: str,
        normalization_type: str,
        epsilon: float,
        apply_residual_connection_post_layernorm: bool,
    ) -> None:
        super().__init__()

        self.apply_residual_connection_post_layernorm = apply_residual_connection_post_layernorm

        self.input_layernorm = {
            "layer_norm": torch.nn.LayerNorm(hidden_size, epsilon),
            "rms": RMSNorm(hidden_size, epsilon),
        }[normalization_type]

        if apply_residual_connection_post_layernorm:
            self.post_attention_layernorm = {
                "layer_norm": torch.nn.LayerNorm(hidden_size, epsilon),
                "rms": RMSNorm(hidden_size, epsilon),
            }[normalization_type]

        self.cos, self.sin = rotary_mat(hidden_size, num_heads, config.max_position_embeddings, head_scale=config.partial_rotary_factor)

        self.self_attn = SelfAttention(
            hidden_size,
            num_heads,
            num_key_value_heads,
            scale_type,
        )

        if config.partial_rotary_factor != 1.0:
            self.mlp = PhiMLP(hidden_size, intermediate_size)
        else:
            self.mlp = MLP(model_type, hidden_size, intermediate_size)

    def forward(
        self,
        use_cache: bool,
        x: torch.Tensor,
        position_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        k_cache: torch.Tensor,
        v_cache: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        # Dimension of x is [batch_size, seq_len, hidden_size] Dimension of
        # k_cache and v_cache is [batch_size, n_layers, pos, num_heads, head_dim]
        attn_norm_output = self.input_layernorm(x)
        h, k_out, v_out = self.self_attn(
            use_cache, attn_norm_output, position_ids, attention_mask, self.cos, self.sin, k_cache, v_cache
        )

        h = x + h

        if self.apply_residual_connection_post_layernorm:
            attn_norm_output = self.post_attention_layernorm(h)

        return h + self.mlp(attn_norm_output), k_out, v_out


class ApplyMask(torch.nn.Module):
    def __init__(
        self,
    ) -> None:
        super().__init__()

    def forward(self, use_cache, score, attention_mask, seq_len, num_heads, dtype=torch.float32):
        # The mask contains 1's for values that should stay intact, and 0's for values that should get added to -10000
        expanded_mask = attention_mask[:, None, None, :].expand(-1, 1, seq_len, -1).to(dtype)
        inverted_mask = 1.0 - expanded_mask
        mask_score = inverted_mask.masked_fill(inverted_mask.to(torch.bool), torch.finfo(torch.float16).min)

        if not use_cache:
            batch_size, max_seq_len = attention_mask.size()
            causal_mask = torch.tril(torch.ones((batch_size, 1, seq_len, max_seq_len)), diagonal=max_seq_len - seq_len)
            inverted_causal_mask = 1.0 - causal_mask
            mask_score += inverted_causal_mask.masked_fill(inverted_causal_mask.to(torch.bool), torch.finfo(torch.float16).min)

        mask_score = mask_score.expand(-1, num_heads, -1, -1)

        return score + mask_score


def rotate_half(x):
    """Rotates half the hidden dims of the input."""
    half_dim = x.shape[-1] // 2
    x1 = x[..., :half_dim]
    x2 = x[..., half_dim:]
    return torch.cat((-x2, x1), dim=-1)


def apply_rope(x, cos, sin, position_ids):
    head_dim = x.shape[-1]
    cos = cos[:, :head_dim]
    sin = sin[:, :head_dim]
    cos = cos[position_ids].unsqueeze(1)  # [bs, 1, seq_len, dim]
    sin = sin[position_ids].unsqueeze(1)  # [bs, 1, seq_len, dim]
    return (x * cos) + (rotate_half(x) * sin)


class RotaryEmbedding(torch.nn.Module):
    def __init__(
        self,
    ) -> None:
        super().__init__()

    def forward(
        self,
        x: torch.Tensor,
        cos: torch.Tensor,
        sin: torch.Tensor,
        position_ids: torch.Tensor,
    ) -> torch.Tensor:
        return apply_rope(x, cos, sin, position_ids)


def broadcast_key_value(hidden_states: torch.Tensor, n_rep: int) -> torch.Tensor:
    batch, num_key_value_heads, slen, head_dim = hidden_states.shape
    hidden_states = hidden_states[:, :, None, :, :].expand(batch, num_key_value_heads, n_rep, slen, head_dim)
    return hidden_states.reshape(batch, num_key_value_heads * n_rep, slen, head_dim)

class SelfAttention(torch.nn.Module):
    def __init__(
        self,
        hidden_size: int,
        num_heads: int,
        num_key_value_heads: int,
        scale_type: str,
    ) -> None:
        super().__init__()
        self.head_dim = int(hidden_size / num_heads)
        self.partial_dim = int(config.partial_rotary_factor * self.head_dim)
        key_value_hidden_size = num_key_value_heads * self.head_dim
        self.q_proj = torch.nn.Linear(hidden_size, hidden_size, bias = config.partial_rotary_factor!=1.0)
        self.k_proj = torch.nn.Linear(hidden_size, key_value_hidden_size, bias = config.partial_rotary_factor!=1.0)
        self.v_proj = torch.nn.Linear(hidden_size, key_value_hidden_size, bias = config.partial_rotary_factor!=1.0)
        self.o_proj = torch.nn.Linear(hidden_size, hidden_size, bias = config.partial_rotary_factor!=1.0)
        self.apply_mask = ApplyMask()
        self.rotary_embedding = RotaryEmbedding()

        self.hidden_size = hidden_size
        self.num_heads = num_heads
        self.num_key_value_heads = num_key_value_heads

        if scale_type == "HeadDim":
            self.scale = self.head_dim
        elif scale_type == "SquareRootHeadDim":
            self.scale = np.sqrt(self.head_dim)
        else:
            raise ValueError(f"Unknown scale type {scale_type}")

    def forward(
        self,
        use_cache: bool,
        x: torch.Tensor,
        position_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        cos: torch.Tensor,
        sin: torch.Tensor,
        k_cache: torch.Tensor,
        v_cache: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        query = self.q_proj(x)
        key = self.k_proj(x)
        value = self.v_proj(x)

        batch_size = x.shape[0]
        seq_len = x.shape[1]

        # Split the attention heads
        query = torch.reshape(query, [batch_size, seq_len, self.num_heads, self.head_dim]).transpose(1, 2)
        key = torch.reshape(key, [batch_size, seq_len, self.num_key_value_heads, self.head_dim]).transpose(1, 2)
        value = torch.reshape(value, [batch_size, seq_len, self.num_key_value_heads, self.head_dim]).transpose(1, 2)

        # Partial rotary embedding for phi-2
        if config.partial_rotary_factor != 1.0:
            query_rot, query_pass = (
                query[..., : self.partial_dim],
                query[..., self.partial_dim:],
            )
            key_rot, key_pass = (
                key[..., : self.partial_dim],
                key[..., self.partial_dim:],
            )

            query_rot = self.rotary_embedding(query_rot, cos, sin, position_ids)
            key_rot = self.rotary_embedding(key_rot, cos, sin, position_ids)

            query = torch.cat((query_rot, query_pass), dim=-1)
            key = torch.cat((key_rot, key_pass), dim=-1)
        
        
        # Apply rotary positional embedding
        else:
            query = self.rotary_embedding(query, cos, sin, position_ids)
            key = self.rotary_embedding(key, cos, sin, position_ids)

        # Append new entries to the end of k, v cache
        k_cache = torch.cat((k_cache, key), dim=2)
        v_cache = torch.cat((v_cache, value), dim=2)

        key = k_cache
        value = v_cache

        # Broadcast key and value from num_key_value_heads to match the query's num_heads
        if self.num_heads != self.num_key_value_heads:
            n_reps = self.num_heads // self.num_key_value_heads
            key = broadcast_key_value(key, n_reps)
            value = broadcast_key_value(value, n_reps)

        key = key.permute([0, 1, 3, 2])

        # Calculate attention scores
        score = torch.matmul(query.to(torch.float32), key.to(torch.float32)) / self.scale

        # Apply the mask
        score = self.apply_mask(use_cache, score, attention_mask, seq_len, self.num_heads)

        # Calculate attention values
        prob = torch.nn.functional.softmax(score, dim=-1).to(query.dtype)

        attn = torch.matmul(prob, value)

        # Merge attention heads
        attn = attn.permute([0, 2, 1, 3]).reshape([batch_size, seq_len, self.hidden_size])

        return self.o_proj(attn), k_cache, v_cache


class MLP(torch.nn.Module):
    def __init__(
        self,
        model_type: str,
        hidden_size: int,
        intermediate_size: int,
    ) -> None:
        super().__init__()
        self.gate_proj = torch.nn.Linear(hidden_size, intermediate_size, bias=False)
        self.down_proj = torch.nn.Linear(intermediate_size, hidden_size, bias=False)
        self.model_type = model_type
        if model_type == "falcon":
            self.act = torch.nn.GELU()
        else:
            self.up_proj = torch.nn.Linear(hidden_size, intermediate_size, bias=False)

    def forward(self, x):
        w1x = self.gate_proj(x)

        if self.model_type == "falcon":
            return self.down_proj(self.act(w1x))
        else:
            return self.down_proj(w1x * torch.sigmoid(w1x) * self.up_proj(x))

import math
class NewGELUActivation(torch.nn.Module):
    """
    Implementation of the GELU activation function currently in Google BERT repo (identical to OpenAI GPT). Also see
    the Gaussian Error Linear Units paper: https://arxiv.org/abs/1606.08415
    """

    def forward(self, input):
        return 0.5 * input * (1.0 + torch.tanh(math.sqrt(2.0 / math.pi) * (input + 0.044715 * torch.pow(input, 3.0))))

class PhiMLP(torch.nn.Module):
    def __init__(self,
                hidden_size: int,
                intermediate_size: int,):
        super().__init__()
        self.activation_fn = NewGELUActivation()
        self.fc1 = torch.nn.Linear(hidden_size, intermediate_size)
        self.fc2 = torch.nn.Linear(intermediate_size, hidden_size)

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        hidden_states = self.fc1(hidden_states)
        hidden_states = self.activation_fn(hidden_states)
        hidden_states = self.fc2(hidden_states)
        return hidden_states
