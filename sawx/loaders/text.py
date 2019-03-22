from ..utils.textutil import guessBinary

import logging
log = logging.getLogger(__name__)


def identify_mime(uri, fh, header):
    mime_type = None
    is_binary = guessBinary(header)
    if not is_binary:
        header = header.strip().lower()
        if header.startswith(b"<"):
            if header.startswith(b"<?xml"):
                found_xml = True
            else:
                found_xml = False
            if b"<rss" in header:
                mime_type = "application/rss+xml"
            elif b"<!doctype html" in header or b"<html" in header:
                mime_type = "text/html"
            elif found_xml:
                mime_type = "text/xml"
        elif header.startswith(b"#!"):
            line = header[2:80].lower().strip()
            if line.startswith(b"/usr/bin/env"):
                line = line[12:].strip()
            words = line.split()
            names = words[0].split(b"/")
            if names[-1]:
                mime_type = "text/%s" % names[-1].decode("utf-8")

        if not mime_type:
            mime_type = "text/plain"

    if mime_type:
        log.debug(f"text loader: identified {mime_type}")
        return dict(mime=mime_type, ext="")
    else:
        log.debug(f"text loader: unidentified")
        return None
