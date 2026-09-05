from pathlib import Path

SECTOR_SIZE = 2048
VOLUME_DESCRIPTOR_START_SECTOR = 16
VOLUME_DESCRIPTOR_SIGNATURE = b"CD001"
MAX_VOLUME_DESCRIPTORS = 128

JOLIET_ESCAPE_LEVELS = {
    b"%/@": 1,
    b"%/C": 2,
    b"%/E": 3,
}


def _decode_ascii(raw):
    return raw.decode("ascii", errors="replace").rstrip(" \x00")


def _decode_joliet(raw):
    # Joliet identifiers use UCS-2BE. A damaged/odd trailing byte is
    # preserved visibly through replacement decoding instead of ignored.
    return raw.decode("utf-16-be", errors="replace").rstrip(" \x00")


def _both_endian_u16(raw):
    little = int.from_bytes(raw[0:2], "little")
    big = int.from_bytes(raw[2:4], "big")
    return {
        "value": little if little == big else None,
        "little_endian": little,
        "big_endian": big,
        "consistent": little == big,
    }


def _both_endian_u32(raw):
    little = int.from_bytes(raw[0:4], "little")
    big = int.from_bytes(raw[4:8], "big")
    return {
        "value": little if little == big else None,
        "little_endian": little,
        "big_endian": big,
        "consistent": little == big,
    }




def _parse_volume_datetime(raw):
    """Parse the 17-byte ISO9660 volume date/time field.

    Bytes 0..15 are ASCII digits YYYYMMDDHHMMSScc and byte 16 is a
    signed timezone offset in 15-minute intervals from UTC. Raw source
    components are preserved alongside a derived ISO-8601 value when
    the timestamp is meaningful.
    """
    if len(raw) != 17:
        return {
            "raw": raw.hex(),
            "valid": False,
            "interpretation": None,
            "error": "invalid_length",
        }

    digits = raw[:16].decode("ascii", errors="replace")
    tz_quarters = int.from_bytes(raw[16:17], "big", signed=True)
    tz_minutes = tz_quarters * 15

    result = {
        "raw": digits,
        "timezone_offset_quarters": tz_quarters,
        "timezone_offset_minutes": tz_minutes,
        "iso8601": None,
        "valid": False,
    }

    # ISO9660 uses all-zero timestamps to mean unspecified/not set.
    if digits == "0000000000000000":
        result["interpretation"] = "unspecified"
        return result

    if len(digits) != 16 or not digits.isdigit():
        result["interpretation"] = "unparsed"
        return result

    try:
        year = int(digits[0:4])
        month = int(digits[4:6])
        day = int(digits[6:8])
        hour = int(digits[8:10])
        minute = int(digits[10:12])
        second = int(digits[12:14])
        centiseconds = int(digits[14:16])

        # Validate calendar/time fields without normalizing the source.
        from datetime import datetime, timedelta, timezone

        offset = timezone(timedelta(minutes=tz_minutes))
        dt = datetime(
            year, month, day, hour, minute, second,
            centiseconds * 10_000, tzinfo=offset
        )
        result["iso8601"] = dt.isoformat(timespec="milliseconds")
        result["valid"] = True
        result["interpretation"] = "parsed"
    except (ValueError, OverflowError):
        result["interpretation"] = "unparsed"

    return result

def _descriptor_header(block):
    return {
        "type": block[0],
        "identifier": _decode_ascii(block[1:6]),
        "version": block[6],
    }


def _parse_primary_volume_descriptor(block, sector):
    return {
        "sector": sector,
        "descriptor": _descriptor_header(block),
        "system_id": _decode_ascii(block[8:40]),
        "volume_id": _decode_ascii(block[40:72]),
        "volume_space_size_blocks": _both_endian_u32(block[80:88]),
        "volume_set_size": _both_endian_u16(block[120:124]),
        "volume_sequence_number": _both_endian_u16(block[124:128]),
        "logical_block_size": _both_endian_u16(block[128:132]),
        "path_table_size": _both_endian_u32(block[132:140]),
        "volume_set_id": _decode_ascii(block[190:318]),
        "publisher_id": _decode_ascii(block[318:446]),
        "data_preparer_id": _decode_ascii(block[446:574]),
        "application_id": _decode_ascii(block[574:702]),
        "volume_creation_time": _parse_volume_datetime(block[813:830]),
        "volume_modification_time": _parse_volume_datetime(block[830:847]),
        "volume_expiration_time": _parse_volume_datetime(block[847:864]),
        "volume_effective_time": _parse_volume_datetime(block[864:881]),
        "file_structure_version": block[881],
    }


def _parse_joliet_descriptor(block, sector):
    escape = bytes(block[88:91])
    level = JOLIET_ESCAPE_LEVELS.get(escape)

    if level is None:
        return None

    return {
        "sector": sector,
        "level": level,
        "escape_sequence": escape.decode("ascii", errors="replace"),
        "volume_id": _decode_joliet(block[40:72]),
    }


def inspect_iso9660(image_path):
    if image_path is None:
        return {"available": False}

    image_path = Path(image_path).expanduser().resolve()

    if not image_path.exists():
        return {"available": False, "error": "image_not_found"}

    if not image_path.is_file():
        return {"available": False, "error": "image_not_file"}

    primary = None
    joliet = []
    descriptors_seen = 0
    terminator_seen = False
    signature_seen = False

    with image_path.open("rb") as handle:
        for index in range(MAX_VOLUME_DESCRIPTORS):
            sector = VOLUME_DESCRIPTOR_START_SECTOR + index
            handle.seek(sector * SECTOR_SIZE)
            block = handle.read(SECTOR_SIZE)

            if len(block) < SECTOR_SIZE:
                break

            if block[1:6] != VOLUME_DESCRIPTOR_SIGNATURE:
                # ISO9660 descriptor sequence has not been recognized.
                # At sector 16 this means this is not an ISO9660 image;
                # later it means the descriptor sequence is malformed.
                if index == 0:
                    return {
                        "available": True,
                        "type": "unknown",
                        "iso9660": False,
                    }
                break

            signature_seen = True
            descriptors_seen += 1
            descriptor_type = block[0]

            if descriptor_type == 1 and primary is None:
                primary = _parse_primary_volume_descriptor(block, sector)

            elif descriptor_type == 2:
                parsed_joliet = _parse_joliet_descriptor(block, sector)
                if parsed_joliet is not None:
                    joliet.append(parsed_joliet)

            elif descriptor_type == 255:
                terminator_seen = True
                break

    if not signature_seen:
        return {
            "available": True,
            "type": "unknown",
            "iso9660": False,
        }

    filesystem = {
        "available": True,
        "type": "iso9660",
        "iso9660": True,
        "descriptor_count": descriptors_seen,
        "terminator_seen": terminator_seen,
        "primary_volume_descriptor": primary,
        "joliet": {
            "present": bool(joliet),
            "descriptors": joliet,
        },
    }

    consistency = []
    if primary is not None:
        for field in (
            "volume_space_size_blocks",
            "volume_set_size",
            "volume_sequence_number",
            "logical_block_size",
            "path_table_size",
        ):
            value = primary[field]
            if not value["consistent"]:
                consistency.append(field)

    filesystem["numeric_endianness_mismatches"] = consistency
    return filesystem
