def carve_jpeg(file_stream, max_search_bytes=1024*1024):
    """
    Minimally search for a JPEG header and extract up to the EOI marker.
    This is bounded and streaming-safe.
    """
    chunk_size = 4096
    bytes_read = 0
    buffer = b""
    start_absolute_offset = -1
    
    while bytes_read < max_search_bytes:
        chunk = file_stream.read(chunk_size)
        if not chunk:
            break
            
        bytes_read += len(chunk)
        buffer += chunk
        
        if start_absolute_offset == -1:
            idx = buffer.find(b"\xff\xd8\xff")
            if idx != -1:
                start_absolute_offset = bytes_read - len(buffer) + idx
                buffer = buffer[idx:]
            else:
                buffer = buffer[-2:] if len(buffer) >= 2 else buffer
                
        if start_absolute_offset != -1:
            # Look for end marker. EOI is 0xFF 0xD9
            end_idx = buffer.find(b"\xff\xd9")
            if end_idx != -1:
                return start_absolute_offset, buffer[:end_idx+2]
                
            if len(buffer) > 10 * 1024 * 1024:
                return start_absolute_offset, buffer
                
    if start_absolute_offset != -1 and len(buffer) > 0:
        return start_absolute_offset, buffer
        
    return None, None
