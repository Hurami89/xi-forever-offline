"""MP3 checks and tags for VanaSync (2026-11-27, J's Radio handoff). Python standard library only.

is_mp3(handle)    : True when the file is an MP3 (an ID3v2 tag followed by MPEG audio, or MPEG audio at once).
read_tags(handle) : {"title", "artist", "album", "track"} from ID3v2.2/2.3/2.4 text frames (TIT2/TPE1/TALB/TRCK),
                    falling back to an ID3v1 tag at the end. Missing fields are "". Nothing is guessed.
"""
import struct

TEXT_FRAMES = {"TIT2": "title", "TPE1": "artist", "TALB": "album", "TRCK": "track",
               "TT2": "title", "TP1": "artist", "TAL": "album", "TRK": "track"}
MAX_TAG = 8 * 1024 * 1024


def _syncsafe(data):
    return (data[0] << 21) | (data[1] << 14) | (data[2] << 7) | data[3]


def _frame_sync(data, at):
    """An MPEG audio frame header at `at`: 11 set sync bits, a known version and layer, a usable bitrate and rate."""
    if at + 4 > len(data) or data[at] != 0xFF or (data[at + 1] & 0xE0) != 0xE0:
        return False
    version = (data[at + 1] >> 3) & 3
    layer = (data[at + 1] >> 1) & 3
    bitrate = data[at + 2] >> 4
    rate = (data[at + 2] >> 2) & 3
    return version != 1 and layer != 0 and bitrate not in (0, 15) and rate != 3


def is_mp3(handle):
    """True when the open file is an MP3. A renamed WAV, text or picture is refused. Leaves the position at the start."""
    try:
        handle.seek(0)
        data = handle.read(10)
        at = 0
        if data[:3] == b"ID3" and len(data) == 10:
            at = 10 + _syncsafe(data[6:10]) + (10 if data[5] & 0x10 else 0)
        handle.seek(at)
        data = handle.read(8192)
        start = 0
        while start < len(data) and data[start] == 0:   # padding after the tag
            start += 1
        return any(_frame_sync(data, i) for i in range(start, min(len(data) - 3, start + 4096)))
    except (OSError, ValueError):
        return False
    finally:
        try:
            handle.seek(0)
        except (OSError, ValueError):
            pass


def _text(frame_data):
    if not frame_data:
        return ""
    encoding, body = frame_data[0], frame_data[1:]
    try:
        if encoding == 0:
            text = body.decode("latin-1")
        elif encoding == 1:
            text = body.decode("utf-16")
        elif encoding == 2:
            text = body.decode("utf-16-be")
        elif encoding == 3:
            text = body.decode("utf-8")
        else:
            return ""
    except UnicodeDecodeError:
        return ""
    # several values are separated by NUL: keep the first; drop the terminator
    return text.split("\x00")[0].strip()


def _id3v2(handle):
    handle.seek(0)
    header = handle.read(10)
    if len(header) < 10 or header[:3] != b"ID3":
        return {}
    major, flags = header[3], header[5]
    size = _syncsafe(header[6:10])
    if major not in (2, 3, 4) or size > MAX_TAG or flags & 0x80:   # unsynchronised tags are rare: not read
        return {}
    data = handle.read(size)
    at = 0
    if flags & 0x40 and major in (3, 4):                           # an extended header: skip it
        ext = struct.unpack(">I", data[:4])[0] if major == 3 else _syncsafe(data[:4])
        at = ext + (4 if major == 3 else 0)
    out = {}
    while at < len(data):
        if major == 2:
            if at + 6 > len(data) or data[at] == 0:
                break
            name = data[at:at + 3].decode("latin-1", "replace")
            length = (data[at + 3] << 16) | (data[at + 4] << 8) | data[at + 5]
            body = data[at + 6:at + 6 + length]
            at += 6 + length
        else:
            if at + 10 > len(data) or data[at] == 0:
                break
            name = data[at:at + 4].decode("latin-1", "replace")
            raw = data[at + 4:at + 8]
            length = _syncsafe(raw) if major == 4 else struct.unpack(">I", raw)[0]
            fflags = data[at + 9]
            body = data[at + 10:at + 10 + length]
            at += 10 + length
            if major == 4 and fflags & 0x01:                       # a data length indicator in front
                body = body[4:]
            if fflags & (0x0C if major == 4 else 0xC0):            # compressed or encrypted: not read
                continue
        key = TEXT_FRAMES.get(name)
        if key and key not in out:
            value = _text(body)
            if value:
                out[key] = value
    return out


def _id3v1(handle):
    try:
        handle.seek(-128, 2)
    except OSError:
        return {}
    tag = handle.read(128)
    if len(tag) != 128 or tag[:3] != b"TAG":
        return {}
    field = lambda raw: raw.split(b"\x00")[0].decode("latin-1").strip()
    out = {"title": field(tag[3:33]), "artist": field(tag[33:63]), "album": field(tag[63:93])}
    if tag[125] == 0 and tag[126]:
        out["track"] = str(tag[126])
    return {k: v for k, v in out.items() if v}


def read_tags(handle):
    tags = {"title": "", "artist": "", "album": "", "track": ""}
    try:
        found = _id3v2(handle)
        for key, value in _id3v1(handle).items():
            found.setdefault(key, value)
    except (OSError, ValueError, struct.error, IndexError):
        found = {}
    for key, value in found.items():
        tags[key] = value[:200]
    return tags
