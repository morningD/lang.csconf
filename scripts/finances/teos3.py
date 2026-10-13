"""Locate and extract a target XML from a large remote zip via EOCD + two ranged reads."""
import struct, urllib.request, zlib

UA = {'User-Agent': 'Mozilla/5.0'}

def fetch_range(url, rng, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={**UA, 'Range': f'bytes={rng}'})
            resp = urllib.request.urlopen(req, timeout=180)
            data = resp.read()
            # Some hosts silently ignore Range and return 200 with the whole
            # body (IRS apps host did exactly that -> 340MB per call). Never
            # accept a non-206 answer for a ranged read.
            if resp.status != 206:
                raise IOError(f'Range not honored (HTTP {resp.status}) for bytes={rng}')
            return data
        except Exception:
            if i == tries - 1: raise
            import time; time.sleep(3)

def head_size(url):
    try:
        req = urllib.request.Request(url, method='HEAD', headers=UA)
        return int(urllib.request.urlopen(req, timeout=60).headers.get('Content-Length', 0))
    except Exception:
        return None

def eocd(url, size):
    tail = fetch_range(url, f"bytes={max(0, size - 66000)}-")
    off = tail.rfind(b'PK\x05\x06')
    if off < 0: return None
    e = tail[off:]
    cd_size, cd_off = struct.unpack('<II', e[12:20])
    if cd_size == 0xFFFFFFFF or cd_off == 0xFFFFFFFF:
        # zip64: locator (sig PK\x06\x07, 20 bytes) sits right before the EOCD;
        # its bytes 8..16 hold the offset of the EOCD64 record.
        loff = tail.rfind(b'PK\x06\x07')
        cd64_off = struct.unpack('<Q', tail[loff+8:loff+16])[0]
        # EOCD64 record: cd_size @ +44, cd_offset @ +52
        cd64 = fetch_range(url, f"bytes={cd64_off}-{cd64_off + 56}")
        cd_size = struct.unpack('<Q', cd64[44:52])[0]
        cd_off = struct.unpack('<Q', cd64[52:60])[0]
    return cd_off, cd_size

def find_entry(url, size, needle):
    cd = eocd(url, size)
    if not cd: return None
    cd_off, cd_size = cd
    cd_data = fetch_range(url, f"bytes={cd_off}-{cd_off + cd_size}")
    idx = 0
    while idx < len(cd_data) - 46:
        if cd_data[idx:idx+4] == b'PK\x01\x02':
            (sig, ver, vneed, flags, method, mtime, mdate, crc, csize, usize,
             nlen, elen, clen, dsk, iattr, eattr, lho) = struct.unpack('<IHHHHHHIIIHHHHHII', cd_data[idx:idx+46])
            name = cd_data[idx+46:idx+46+nlen].decode('utf-8', 'replace')
            if needle in name:
                # zip64 extra may carry real offsets; check zip64 extra (header id 0x0001)
                extra = cd_data[idx+46+nlen:idx+46+nlen+elen]
                real_lho = lho
                if lho == 0xFFFFFFFF and b'\x01\x00' in extra[:4]:
                    ex = extra[4:]
                    p = 0
                    while p + 4 <= len(ex):
                        hid, hsz = struct.unpack('<HH', ex[p:p+4])
                        if hid == 1:
                            vals = struct.unpack('<Q' * (hsz // 8), ex[p+4:p+4+hsz])
                            real_lho = vals[-1]
                            break
                        p += 4 + hsz
                return name, real_lho, csize, usize, method
            idx += 46 + nlen + elen + clen
        else:
            idx += 1
    return None

def extract_member(url, size, needle, out_path):
    hit = find_entry(url, size, needle)
    if not hit: return None
    name, lho, csize, usize, method = hit
    # IRS zips carry a non-standard prefix before the first local header;
    # CD offsets are relative to the real zip start, so detect and add it.
    head = fetch_range(url, "bytes=0-2047")
    prefix = head.find(b'PK\x03\x04')
    blob = fetch_range(url, f"bytes={lho + prefix}-{lho + prefix + csize + 2048}")
    nlen2, elen2 = struct.unpack('<HH', blob[26:30])
    payload = blob[30 + nlen2 + elen2:30 + nlen2 + elen2 + csize]
    if method == 8:
        payload = zlib.decompress(payload, -15)
    open(out_path, 'wb').write(payload.encode('utf-8', 'replace') if isinstance(payload, str) else payload)
    return name
