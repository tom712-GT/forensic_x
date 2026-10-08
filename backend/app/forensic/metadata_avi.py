import struct

MAX_HDRL_BYTES = 1 * 1024 * 1024
MAX_STREAMS = 16
MAX_CHUNKS = 10000
MAX_DEPTH = 4

def _fourcc(b):
    if all(0x20 <= byte <= 0x7E for byte in b):
        try:
            return b.decode("ascii")
        except Exception:
            pass
    return "hex:" + b.hex()

def parse_avi(f, file_size):
    result = {
        "container": "AVI",
        "parser_version": "1",
        "status": "OK",
        "fields": [],
        "errors": []
    }
    
    def add_field(name, raw, interp, source, offset, note=None):
        result["fields"].append({
            "field": name,
            "raw_value": raw,
            "interpreted_value": interp,
            "source": source,
            "byte_offset": offset,
            "note": note
        })

    try:
        f.seek(0)
        riff_hdr = f.read(12)
    except Exception:
        result["status"] = "PARSE_ERROR"
        result["errors"].append("read error")
        return result
        
    if len(riff_hdr) < 12:
        result["status"] = "PARSE_ERROR"
        result["errors"].append("file too small")
        return result
        
    try:
        chunk_id, chunk_size, riff_type = struct.unpack("<4sI4s", riff_hdr)
    except struct.error:
        result["status"] = "PARSE_ERROR"
        result["errors"].append("struct error")
        return result
        
    if chunk_id != b"RIFF" or riff_type != b"AVI ":
        result["status"] = "PARSE_ERROR"
        result["errors"].append("not AVI")
        return result
        
    offset = 12
    end_offset = min(file_size, chunk_size + 8)
    
    chunks_read = 0
    stream_idx = 0
    
    current_stype = None
    def walk_list(l_offset, l_end, is_hdrl=False, depth=1):
        nonlocal chunks_read, stream_idx, current_stype
        if depth > MAX_DEPTH:
            result["errors"].append("MAX_DEPTH exceeded")
            result["status"] = "PARTIAL"
            return
        c_off = l_offset
        while c_off < l_end:
            if chunks_read >= MAX_CHUNKS:
                result["status"] = "PARTIAL"
                result["errors"].append("MAX_CHUNKS exceeded")
                break
                
            try:
                f.seek(c_off)
                hdr = f.read(8)
            except Exception:
                result["status"] = "PARSE_ERROR"
                result["errors"].append("read error")
                return
                
            if len(hdr) < 8:
                break
                
            try:
                cid, csize = struct.unpack("<4sI", hdr)
            except struct.error:
                result["status"] = "PARSE_ERROR"
                result["errors"].append("struct error")
                return
                
            if csize < 0 or c_off + 8 + csize > l_end or c_off + 8 + csize > file_size:
                result["status"] = "PARTIAL"
                result["errors"].append("invalid size bounds")
                return
                
            payload_off = c_off + 8
            
            if cid == b"LIST":
                try:
                    f.seek(payload_off)
                    ltype = f.read(4)
                except Exception:
                    result["status"] = "PARSE_ERROR"
                    result["errors"].append("read error")
                    return
                    
                if ltype == b"hdrl":
                    if csize > MAX_HDRL_BYTES:
                        result["status"] = "PARTIAL"
                        result["errors"].append("MAX_HDRL_BYTES exceeded")
                    else:
                        walk_list(payload_off + 4, payload_off + csize, True, depth + 1)
                elif ltype == b"strl" and is_hdrl:
                    current_stype = None
                    if stream_idx >= MAX_STREAMS:
                        result["status"] = "PARTIAL"
                        result["errors"].append("MAX_STREAMS exceeded")
                    else:
                        walk_list(payload_off + 4, payload_off + csize, True, depth + 1)
                        stream_idx += 1
                else:
                    # skip movi, idx1 etc
                    pass
            else:
                if is_hdrl:
                    if cid == b"avih" and csize >= 56:
                        try:
                            f.seek(payload_off)
                            data = f.read(56)
                            if len(data) == 56:
                                microsec, _, _, _, frames, _, streams, _, w, h, _, _, _, _ = struct.unpack("<IIIIIIIIIIIIII", data)
                                fps_interp = None
                                if microsec > 0:
                                    fps_interp = 1000000 / microsec
                                add_field("frames_per_second", microsec, fps_interp, "avi:hdrl/avih", payload_off)
                                add_field("width", w, None, "avi:hdrl/avih", payload_off + 32)
                                add_field("height", h, None, "avi:hdrl/avih", payload_off + 36)
                                add_field("total_frames", frames, None, "avi:hdrl/avih", payload_off + 16)
                                add_field("stream_count", streams, None, "avi:hdrl/avih", payload_off + 24)
                        except Exception:
                            pass
                    elif cid == b"strh" and csize >= 56:
                        try:
                            f.seek(payload_off)
                            data = f.read(12) # only need type and handler
                            if len(data) == 12:
                                stype, shandler = struct.unpack("<4s4s", data[:8])
                                current_stype = stype
                                add_field(f"stream{stream_idx}.stream_type", _fourcc(stype), None, "avi:hdrl/strl/strh", payload_off)
                                add_field(f"stream{stream_idx}.handler", _fourcc(shandler), None, "avi:hdrl/strl/strh", payload_off + 4)
                        except Exception:
                            pass
                    elif cid == b"strf":
                        if current_stype != b"vids":
                            pass
                        elif csize >= 40:
                            try:
                                f.seek(payload_off)
                                data = f.read(40)
                                if len(data) == 40:
                                    vsize, w, h, planes, bcount, comp = struct.unpack("<IiiHH4s", data[:20])
                                    if vsize >= 40: # looks like BITMAPINFOHEADER
                                        add_field(f"stream{stream_idx}.width", w, None, "avi:hdrl/strl/strf", payload_off + 4)
                                        add_field(f"stream{stream_idx}.height", h, None, "avi:hdrl/strl/strf", payload_off + 8)
                                        add_field(f"stream{stream_idx}.bit_count", bcount, None, "avi:hdrl/strl/strf", payload_off + 14)
                                        
                                        add_field(f"stream{stream_idx}.compression", _fourcc(comp), None, "avi:hdrl/strl/strf", payload_off + 16)
                            except Exception:
                                pass
                                
            # chunks are padded to even size
            c_off += 8 + csize
            if csize % 2 != 0:
                c_off += 1
            chunks_read += 1
            
    try:
        walk_list(offset, end_offset, False, 1)
    except Exception:
        result["status"] = "PARSE_ERROR"
        result["errors"].append("internal parse error")

    if not result["fields"]:
        result["status"] = "PARSE_ERROR"
    elif len(result["errors"]) > 0:
        result["status"] = "PARTIAL"
        
    return result
