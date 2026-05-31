#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streaming merger for Wan 2.1 I2V 14B safetensors shards.

Reads shard files in 64MB chunks — never loads more than ~64MB into RAM at once.
Output: D:\\wan2.1_i2v_14b_480p.safetensors (single file for ComfyUI WanVideoWrapper)

Usage:
    python scripts/merge_wan_i2v_shards.py
"""

import json, struct, os, time, glob

SHARD_DIR   = r"D:\Wan2.1-I2V-14B-480P"
OUTPUT_PATH = r"D:\wan2.1_i2v_14b_480p.safetensors"
CHUNK_SIZE  = 64 * 1024 * 1024  # 64 MB read/write chunks


def _read_shard_header(shard_path: str):
    """Return (header_dict, data_section_start_byte) for one shard."""
    with open(shard_path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(n))
    return header, 8 + n


def merge_shards_streaming(shard_dir: str, output_path: str):
    # ── Step 0: locate and sort shard files ──────────────────────────────────
    index_path = os.path.join(shard_dir, "diffusion_pytorch_model.safetensors.index.json")
    if os.path.exists(index_path):
        with open(index_path) as f:
            idx = json.load(f)
        # unique shards in index order (weight_map values are file names)
        seen = set(); ordered_shards = []
        for fname in idx.get("weight_map", {}).values():
            if fname not in seen:
                seen.add(fname); ordered_shards.append(fname)
        shard_paths = [os.path.join(shard_dir, fn) for fn in ordered_shards]
    else:
        shard_paths = sorted(glob.glob(os.path.join(shard_dir, "diffusion_pytorch_model-*.safetensors")))

    if not shard_paths:
        raise FileNotFoundError(f"No shard files found in {shard_dir}")

    print(f"[Merge] Found {len(shard_paths)} shards:")
    for p in shard_paths:
        print(f"   {os.path.basename(p)}: {os.path.getsize(p)/1e9:.2f} GB")

    # ── Step 1: collect tensor metadata from all shards (no data loaded) ─────
    print("\n[Merge] Pass 1 — collecting metadata…")
    # ordered_tensors: [(name, dtype, shape, shard_path, data_section_start, byte_start, byte_size)]
    ordered_tensors = []
    global_meta = {}

    for shard_path in shard_paths:
        header, data_start = _read_shard_header(shard_path)
        meta_entry = header.get("__metadata__", {})
        global_meta.update(meta_entry)

        for name, meta in header.items():
            if name == "__metadata__":
                continue
            start, end = meta["data_offsets"]
            ordered_tensors.append((
                name, meta["dtype"], meta["shape"],
                shard_path, data_start,
                start, end - start,
            ))

    print(f"[Merge] Total tensors: {len(ordered_tensors)}")

    # ── Step 2: build output header with sequential offsets ──────────────────
    print("[Merge] Building output header…")
    out_header = {"__metadata__": global_meta}
    offset = 0
    for name, dtype, shape, _, _, _, byte_size in ordered_tensors:
        out_header[name] = {
            "dtype": dtype,
            "shape": shape,
            "data_offsets": [offset, offset + byte_size],
        }
        offset += byte_size

    header_bytes = json.dumps(out_header, separators=(",", ":")).encode("utf-8")
    # safetensors header must be padded so data section starts on 8-byte boundary
    pad = (8 - len(header_bytes) % 8) % 8
    header_bytes += b" " * pad
    header_size_le = struct.pack("<Q", len(header_bytes))

    total_data = offset
    total_file = 8 + len(header_bytes) + total_data
    print(f"[Merge] Header size:    {len(header_bytes)/1e3:.1f} KB")
    print(f"[Merge] Data size:      {total_data/1e9:.2f} GB")
    print(f"[Merge] Output total:   {total_file/1e9:.2f} GB")

    # ── Step 3: stream tensor data into output file ───────────────────────────
    print(f"\n[Merge] Pass 2 — writing to {output_path}…")
    t0 = time.time()
    written = 0

    # Group tensors by shard so each shard file is opened exactly once
    from collections import defaultdict
    tensors_by_shard = defaultdict(list)
    for t in ordered_tensors:
        tensors_by_shard[t[3]].append(t)  # keyed by shard_path

    # We must write tensors in the ORDER defined in out_header (= ordered_tensors order).
    # To minimise seeks we track write position, but we output in tensor order regardless.

    with open(output_path, "wb") as out_f:
        # Write header
        out_f.write(header_size_le)
        out_f.write(header_bytes)

        # Write tensor data in the same order as ordered_tensors
        prev_shard = None
        shard_f = None
        for name, dtype, shape, shard_path, data_start, byte_start, byte_size in ordered_tensors:
            if shard_path != prev_shard:
                if shard_f is not None:
                    shard_f.close()
                shard_f = open(shard_path, "rb")
                prev_shard = shard_path

            shard_f.seek(data_start + byte_start)
            remaining = byte_size
            while remaining > 0:
                chunk = shard_f.read(min(CHUNK_SIZE, remaining))
                if not chunk:
                    break
                out_f.write(chunk)
                remaining -= len(chunk)
                written += len(chunk)

            elapsed = time.time() - t0
            pct = written / total_data * 100 if total_data else 0
            mb_s = written / elapsed / 1e6 if elapsed > 0 else 0
            eta = (total_data - written) * elapsed / written if written > 0 else 0
            print(f"\r  {pct:.1f}%  {written/1e9:.2f}/{total_data/1e9:.2f} GB  "
                  f"{mb_s:.0f} MB/s  ETA {eta:.0f}s      ", end="", flush=True)

        if shard_f is not None:
            shard_f.close()

    print(f"\n[Merge] Done in {time.time()-t0:.0f}s → {output_path}")
    final_size = os.path.getsize(output_path)
    print(f"[Merge] Output size: {final_size/1e9:.2f} GB")
    return output_path


if __name__ == "__main__":
    if os.path.exists(OUTPUT_PATH):
        size = os.path.getsize(OUTPUT_PATH)
        print(f"[Merge] Output already exists: {OUTPUT_PATH} ({size/1e9:.2f} GB)")
        print("[Merge] Delete it first if you want to re-merge.")
    else:
        merge_shards_streaming(SHARD_DIR, OUTPUT_PATH)
