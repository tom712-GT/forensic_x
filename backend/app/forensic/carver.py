def carve_artifacts(file_stream, max_search_bytes=1024*1024*1024, max_artifacts=1000):
    """
    Scans a stream for deterministic signatures and yields artifact dictionaries.
    Yields: {"type": str, "status": str, "start_offset": int, "data": bytes}
    """
    chunk_size = 4096
    bytes_read = 0
    buffer = b""
    absolute_offset = 0
    
    current_carve_type = None
    start_absolute_offset = -1
    artifacts_found = 0
    
    while bytes_read < max_search_bytes and artifacts_found < max_artifacts:
        chunk = file_stream.read(chunk_size)
        if not chunk:
            break
            
        bytes_read += len(chunk)
        buffer += chunk
        
        while buffer:
            if current_carve_type is None:
                best_idx = -1
                best_type = None
                
                # JPEG
                idx = buffer.find(b"\xff\xd8\xff")
                if idx != -1 and (best_idx == -1 or idx < best_idx):
                    best_idx = idx
                    best_type = "JPEG"
                    
                # PNG
                idx = buffer.find(b"\x89PNG\r\n\x1a\n")
                if idx != -1 and (best_idx == -1 or idx < best_idx):
                    best_idx = idx
                    best_type = "PNG"
                    
                # PDF
                idx = buffer.find(b"%PDF-")
                if idx != -1 and (best_idx == -1 or idx < best_idx):
                    best_idx = idx
                    best_type = "PDF"

                # ZIP
                idx = buffer.find(b"PK\x03\x04")
                if idx != -1 and (best_idx == -1 or idx < best_idx):
                    best_idx = idx
                    best_type = "ZIP_CANDIDATE"
                    
                # AVI
                idx = buffer.find(b"RIFF")
                if idx != -1 and len(buffer) >= idx + 12:
                    if buffer[idx+8:idx+12] == b"AVI ":
                        if best_idx == -1 or idx < best_idx:
                            best_idx = idx
                            best_type = "AVI_CANDIDATE"

                # MP4 (ftyp)
                idx = buffer.find(b"ftyp")
                if idx >= 4 and (best_idx == -1 or (idx - 4) < best_idx):
                    best_idx = idx - 4
                    best_type = "MP4_CANDIDATE"
                    
                if best_idx != -1:
                    start_absolute_offset = absolute_offset + best_idx
                    current_carve_type = best_type
                    absolute_offset += best_idx
                    buffer = buffer[best_idx:]
                else:
                    # Keep some bytes for cross-chunk boundaries
                    keep = min(len(buffer), 16)
                    absolute_offset += len(buffer) - keep
                    buffer = buffer[-keep:]
                    break # Read more chunks
            else:
                extracted = False
                end_idx = -1
                end_len = 0
                
                if current_carve_type == "JPEG":
                    end_idx = buffer.find(b"\xff\xd9")
                    if end_idx != -1:
                        end_len = 2
                        extracted = True
                elif current_carve_type == "PNG":
                    end_idx = buffer.find(b"IEND\xaeB`\x82")
                    if end_idx != -1:
                        end_len = 8
                        extracted = True
                elif current_carve_type == "PDF":
                    end_idx = buffer.find(b"%%EOF")
                    if end_idx != -1:
                        end_len = 5
                        extracted = True
                elif current_carve_type.endswith("_CANDIDATE"):
                    # For candidates, we don't have a reliable end marker, just save the first 1KB
                    if len(buffer) >= 1024 or (bytes_read >= max_search_bytes and not chunk):
                        end_idx = min(len(buffer), 1024)
                        end_len = 0
                        extracted = True
                
                max_artifact_size = 10 * 1024 * 1024 # 10MB
                if not extracted and len(buffer) > max_artifact_size:
                    yield {
                        "type": current_carve_type.replace("_CANDIDATE", ""),
                        "status": "PARTIAL" if not current_carve_type.endswith("_CANDIDATE") else "CANDIDATE",
                        "start_offset": start_absolute_offset,
                        "data": buffer[:max_artifact_size]
                    }
                    artifacts_found += 1
                    absolute_offset += max_artifact_size
                    buffer = buffer[max_artifact_size:]
                    current_carve_type = None
                    start_absolute_offset = -1
                    continue
                    
                if extracted:
                    artifact_data = buffer[:end_idx + end_len]
                    yield {
                        "type": current_carve_type.replace("_CANDIDATE", ""),
                        "status": "RECOVERED" if not current_carve_type.endswith("_CANDIDATE") else "CANDIDATE",
                        "start_offset": start_absolute_offset,
                        "data": artifact_data
                    }
                    artifacts_found += 1
                    advance = end_idx + end_len
                    absolute_offset += advance
                    buffer = buffer[advance:]
                    current_carve_type = None
                    start_absolute_offset = -1
                else:
                    break # Need more data
                    
    # Handle remainder
    if current_carve_type is not None and len(buffer) > 0:
        yield {
            "type": current_carve_type.replace("_CANDIDATE", ""),
            "status": "PARTIAL" if not current_carve_type.endswith("_CANDIDATE") else "CANDIDATE",
            "start_offset": start_absolute_offset,
            "data": buffer
        }
