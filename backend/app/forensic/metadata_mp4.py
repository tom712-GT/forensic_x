import struct
from datetime import datetime, timezone, timedelta

MAX_DEPTH = 8
MAX_BOXES = 10000
MAX_MOOV_BYTES = 16 * 1024 * 1024
MAX_BRANDS = 16

def _interpret_timestamp(raw):
    if raw == 0:
        return None, "NOT_SET: container value is zero"
    try:
        dt = datetime(1904, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=raw)
        if 1904 <= dt.year <= 2100:
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "Value stored in the container; not proof of when the recorded event happened."
    except (OverflowError, ValueError):
        pass
    except OSError:
        pass
    except Exception:
        pass
    return None, "OUT_OF_RANGE"
    
def _fourcc(b):
    if all(0x20 <= byte <= 0x7E for byte in b):
        try:
            return b.decode("ascii")
        except Exception:
            pass
    return "hex:" + b.hex()

def parse_mp4(f, file_size):
    result = {
        "container": "MP4",
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

    def walk_boxes(start_offset, end_offset, depth, track_id=None):
        if depth > MAX_DEPTH:
            result["errors"].append("MAX_DEPTH exceeded")
            result["status"] = "PARTIAL"
            return
            
        offset = start_offset
        boxes_read = 0
        
        while offset < end_offset:
            if boxes_read >= MAX_BOXES:
                result["errors"].append("MAX_BOXES exceeded")
                result["status"] = "PARTIAL"
                break
                
            try:
                f.seek(offset)
                header_data = f.read(8)
            except Exception:
                result["status"] = "PARSE_ERROR"
                result["errors"].append("read error")
                return
                
            if len(header_data) < 8:
                result["errors"].append("file too small")
                break
                
            try:
                size, btype = struct.unpack(">I4s", header_data)
            except struct.error:
                result["status"] = "PARSE_ERROR"
                result["errors"].append("struct error")
                return
                
            header_size = 8
            
            if size == 1:
                try:
                    header_data_ext = f.read(8)
                    if len(header_data_ext) < 8:
                        break
                    size = struct.unpack(">Q", header_data_ext)[0]
                    header_size = 16
                except Exception:
                    result["status"] = "PARSE_ERROR"
                    result["errors"].append("struct error ext")
                    return
            elif size == 0:
                if depth == 1:
                    size = file_size - offset
                else:
                    result["status"] = "PARSE_ERROR"
                    result["errors"].append("size 0 not at top level")
                    return
            
            if size < header_size or offset + size > end_offset or offset + size > file_size:
                result["status"] = "PARSE_ERROR"
                result["errors"].append("invalid size bounds")
                return

            payload_size = size - header_size
            payload_offset = offset + header_size
            
            # Process box
            if btype == b"ftyp":
                read_size = min(payload_size, 4096)
                try:
                    f.seek(payload_offset)
                    data = f.read(read_size)
                    if len(data) >= 8:
                        major_brand = data[0:4]
                        add_field("major_brand", _fourcc(major_brand), None, "mp4:ftyp", payload_offset)
                        minor = struct.unpack(">I", data[4:8])[0]
                        add_field("minor_version", minor, None, "mp4:ftyp", payload_offset + 4)
                        
                        comp_brands = []
                        br_offset = 8
                        while br_offset + 4 <= len(data) and len(comp_brands) < MAX_BRANDS:
                            br = data[br_offset:br_offset+4]
                            comp_brands.append(br)
                            br_offset += 4
                        add_field("compatible_brands", [_fourcc(x) for x in comp_brands], None, "mp4:ftyp", payload_offset + 8)
                except Exception:
                    pass

            elif btype == b"moov":
                if payload_size > MAX_MOOV_BYTES:
                    result["status"] = "PARTIAL"
                    result["errors"].append("MOOV_TOO_LARGE")
                else:
                    walk_boxes(payload_offset, payload_offset + payload_size, depth + 1)
                    
            elif btype == b"mvhd":
                if payload_size < 20:
                    result["errors"].append("BOX_TOO_SMALL")
                    result["status"] = "PARTIAL"
                    offset += size; boxes_read += 1; continue
                try:
                    f.seek(payload_offset)
                    # version (1 byte), flags (3 bytes)
                    v_data = f.read(4)
                    if len(v_data) == 4:
                        version = v_data[0]
                        if version not in (0, 1):
                            result["errors"].append("UNSUPPORTED_VERSION")
                            result["status"] = "PARTIAL"
                            offset += size; boxes_read += 1; continue
                        if (version == 0 and payload_size < 20) or (version == 1 and payload_size < 32):
                            result["errors"].append("BOX_TOO_SMALL")
                            result["status"] = "PARTIAL"
                            offset += size; boxes_read += 1; continue
                        add_field("version", version, None, "mp4:moov/mvhd", payload_offset)
                        
                        if version == 1:
                            data = f.read(28)
                            if len(data) == 28:
                                ctime, mtime, timescale, duration = struct.unpack(">QQIQ", data)
                                dt_offset = payload_offset + 4
                                dt_size = 8
                        else:
                            data = f.read(16)
                            if len(data) == 16:
                                ctime, mtime, timescale, duration = struct.unpack(">IIII", data)
                                dt_offset = payload_offset + 4
                                dt_size = 4
                        
                        if data and (version == 1 and len(data) == 28 or version == 0 and len(data) == 16):
                            ci, cn = _interpret_timestamp(ctime)
                            mi, mn = _interpret_timestamp(mtime)
                            add_field("creation_time", ctime, ci, "mp4:moov/mvhd", dt_offset, cn)
                            add_field("modification_time", mtime, mi, "mp4:moov/mvhd", dt_offset + dt_size, mn)
                            add_field("timescale", timescale, None, "mp4:moov/mvhd", dt_offset + dt_size*2)
                            
                            dur_note = None
                            dur_interp = None
                            if timescale > 0:
                                dur_interp = duration / timescale
                            else:
                                dur_note = "timescale is zero"
                            add_field("duration", duration, dur_interp, "mp4:moov/mvhd", dt_offset + dt_size*2 + 4, dur_note)
                except Exception:
                    pass

            elif btype == b"trak":
                # Need to read track id from tkhd inside first, but we walk sequentially.
                # So we pass track_id down.
                # Find tkhd to get track_id
                t_id = track_id
                try:
                    f.seek(payload_offset)
                    # Quick scan for tkhd
                    t_off = payload_offset
                    while t_off < payload_offset + payload_size and t_off + 8 <= file_size:
                        f.seek(t_off)
                        hdata = f.read(8)
                        if len(hdata) < 8: break
                        tsize, tbtype = struct.unpack(">I4s", hdata)
                        if tbtype == b"tkhd" and tsize >= 8 and t_off + tsize <= file_size:
                            f.seek(t_off + 8)
                            vdata = f.read(4)
                            if len(vdata) == 4:
                                version = vdata[0]
                                if version == 1:
                                    tid_data = f.read(16) # ctime(8)+mtime(8)
                                    if len(tid_data) == 16:
                                        t_id_data = f.read(4)
                                        if len(t_id_data) == 4:
                                            t_id = struct.unpack(">I", t_id_data)[0]
                                else:
                                    tid_data = f.read(8) # ctime(4)+mtime(4)
                                    if len(tid_data) == 8:
                                        t_id_data = f.read(4)
                                        if len(t_id_data) == 4:
                                            t_id = struct.unpack(">I", t_id_data)[0]
                            break
                        if tsize < 8: break
                        t_off += tsize
                except Exception:
                    pass
                if t_id is None:
                    # Fallback track index if not found
                    t_id = depth * 1000 + boxes_read
                walk_boxes(payload_offset, payload_offset + payload_size, depth + 1, t_id)
                
            elif btype == b"tkhd":
                if payload_size < 84:
                    result["errors"].append("BOX_TOO_SMALL")
                    result["status"] = "PARTIAL"
                    offset += size; boxes_read += 1; continue
                try:
                    f.seek(payload_offset)
                    v_data = f.read(4)
                    if len(v_data) == 4:
                        version = v_data[0]
                        if version not in (0, 1):
                            result["errors"].append("UNSUPPORTED_VERSION")
                            result["status"] = "PARTIAL"
                            offset += size; boxes_read += 1; continue
                        if (version == 0 and payload_size < 84) or (version == 1 and payload_size < 96):
                            result["errors"].append("BOX_TOO_SMALL")
                            result["status"] = "PARTIAL"
                            offset += size; boxes_read += 1; continue
                        prefix = f"track{track_id}." if track_id is not None else ""
                        add_field(f"{prefix}version", version, None, "mp4:moov/trak/tkhd", payload_offset)
                        
                        f.seek(payload_offset + 4)
                        if version == 1:
                            v1_data = f.read(32)
                            if len(v1_data) == 32:
                                t_id = struct.unpack(">I", v1_data[16:20])[0]
                                add_field(f"{prefix}track_id", t_id, None, "mp4:moov/trak/tkhd", payload_offset + 20)
                        else:
                            v0_data = f.read(20)
                            if len(v0_data) == 20:
                                t_id = struct.unpack(">I", v0_data[8:12])[0]
                                add_field(f"{prefix}track_id", t_id, None, "mp4:moov/trak/tkhd", payload_offset + 12)
                                
                        # width/height are at the end, 8 bytes before end of payload (if standard size)
                        # Actually standard tkhd payload size is 84 (v0) or 96 (v1).
                        # Let's seek relative to tkhd end. Width and Height are the last 8 bytes.
                        if payload_size >= 8:
                            f.seek(payload_offset + payload_size - 8)
                            wh_data = f.read(8)
                            if len(wh_data) == 8:
                                width, height = struct.unpack(">II", wh_data)
                                add_field(f"{prefix}width", width, width / 65536.0, "mp4:moov/trak/tkhd", payload_offset + payload_size - 8)
                                add_field(f"{prefix}height", height, height / 65536.0, "mp4:moov/trak/tkhd", payload_offset + payload_size - 4)
                except Exception:
                    pass

            elif btype in (b"mdia", b"minf", b"stbl"):
                walk_boxes(payload_offset, payload_offset + payload_size, depth + 1, track_id)
                
            elif btype == b"hdlr":
                if payload_size < 12:
                    result["errors"].append("BOX_TOO_SMALL")
                    result["status"] = "PARTIAL"
                    offset += size; boxes_read += 1; continue
                try:
                    # version(1), flags(3), pre_defined(4), handler_type(4)
                    f.seek(payload_offset + 8)
                    data = f.read(4)
                    if len(data) == 4:
                        prefix = f"track{track_id}." if track_id is not None else ""
                        add_field(f"{prefix}handler_type", _fourcc(data), None, "mp4:moov/trak/mdia/hdlr", payload_offset + 8)
                except Exception:
                    pass
                    
            elif btype == b"stsd":
                if payload_size < 16:
                    result["errors"].append("BOX_TOO_SMALL")
                    result["status"] = "PARTIAL"
                    offset += size; boxes_read += 1; continue
                try:
                    f.seek(payload_offset + 4) # skip version/flags
                    data = f.read(4)
                    if len(data) == 4:
                        entry_count = struct.unpack(">I", data)[0]
                        prefix = f"track{track_id}." if track_id is not None else ""
                        add_field(f"{prefix}entry_count", entry_count, None, "mp4:moov/trak/mdia/minf/stbl/stsd", payload_offset + 4)
                        if entry_count > 0 and payload_size >= 16:
                            f.seek(payload_offset + 8)
                            entry_hdr = f.read(8)
                            if len(entry_hdr) == 8:
                                e_size, codec = struct.unpack(">I4s", entry_hdr)
                                add_field(f"{prefix}codec", _fourcc(codec), None, "mp4:moov/trak/mdia/minf/stbl/stsd", payload_offset + 12)
                except Exception:
                    pass

            offset += size
            boxes_read += 1

    try:
        walk_boxes(0, file_size, 1)
    except Exception:
        result["errors"].append("internal parse error")
        
    if not result["fields"]:
        result["status"] = "PARSE_ERROR"
    elif len(result["errors"]) > 0:
        result["status"] = "PARTIAL"
        
    return result
