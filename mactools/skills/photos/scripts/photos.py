#!/usr/bin/env python3
"""
Photos Library search tool — queries Apple Photos SQLite database directly.
Read-only operations only. Never modifies the Photos database.

Usage: photos.py <command> [options]

Commands:
  search "keyword"                Search photos by filename or associated text
  recent [days] [-n count]        Recent photos (default: 7 days, 20 results)
  albums                          List all albums
  album "Name" [-n count]         List photos in an album
  info <path_or_uuid>             Show photo metadata
  export <uuid> <output_path>     Export/copy a photo to a specific path
"""

import sys
import os
import sqlite3
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# CoreData epoch: 2001-01-01 00:00:00 UTC
COREDATA_EPOCH_OFFSET = 978307200


def find_photos_db():
    """Find the Photos.sqlite database, searching common locations."""
    candidates = []

    # Primary location
    home = Path.home()
    primary = home / "Pictures" / "Photos Library.photoslibrary" / "database" / "Photos.sqlite"
    candidates.append(primary)

    # Check for other .photoslibrary bundles in ~/Pictures
    pictures_dir = home / "Pictures"
    if pictures_dir.exists():
        for item in pictures_dir.iterdir():
            if item.suffix == ".photoslibrary" and item.is_dir():
                db = item / "database" / "Photos.sqlite"
                if db not in candidates:
                    candidates.append(db)

    # System Photos library location (older macOS or iCloud-synced)
    sys_photos = home / "Library" / "Containers" / "com.apple.Photos" / "Data" / "Library" / "Photos Library.photoslibrary" / "database" / "Photos.sqlite"
    candidates.append(sys_photos)

    for db_path in candidates:
        if db_path.exists():
            return str(db_path)

    return None


def get_library_root(db_path):
    """Get the Photos library root from the database path."""
    # db_path is .../Photos Library.photoslibrary/database/Photos.sqlite
    return str(Path(db_path).parent.parent)


def connect_db(db_path):
    """Connect to the Photos database in read-only mode."""
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def row_get(row, key, default=None):
    """Safe get for sqlite3.Row objects."""
    try:
        return row[key]
    except (IndexError, KeyError):
        return default


def coredata_to_datetime(timestamp):
    """Convert CoreData timestamp (seconds since 2001-01-01) to datetime string."""
    if timestamp is None:
        return None
    try:
        unix_ts = timestamp + COREDATA_EPOCH_OFFSET
        dt = datetime.fromtimestamp(unix_ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, ValueError, OverflowError):
        return None


def detect_join_table(conn):
    """Detect the album-asset join table name (varies across macOS versions)."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Z_%ASSETS' ORDER BY name"
    )
    tables = [row["name"] for row in cursor.fetchall()]

    # Common patterns: Z_26ASSETS, Z_27ASSETS, Z_28ASSETS, etc.
    # The join table has columns like Z_26ALBUMS (or similar) and Z_34ASSETS (or similar)
    for table in tables:
        # Check columns to confirm it's an album-asset join
        col_cursor = conn.execute(f"PRAGMA table_info({table})")
        cols = [row["name"] for row in col_cursor.fetchall()]
        # Look for a column ending in ALBUMS and one ending in ASSETS
        album_col = None
        asset_col = None
        for col in cols:
            if "ALBUM" in col.upper():
                album_col = col
            elif "ASSET" in col.upper():
                asset_col = col
        if album_col and asset_col:
            return table, album_col, asset_col

    return None, None, None


def resolve_photo_path(row, library_root):
    """Resolve the full file path for a photo asset."""
    directory = row["ZDIRECTORY"] if "ZDIRECTORY" in row.keys() else None
    filename = row["ZFILENAME"] if "ZFILENAME" in row.keys() else None

    if directory and filename:
        full_path = os.path.join(library_root, "originals", directory, filename)
        if os.path.exists(full_path):
            return full_path

    # Try alternative path structure
    if directory and filename:
        full_path = os.path.join(library_root, "masters", directory, filename)
        if os.path.exists(full_path):
            return full_path

    # Return best guess even if not verified
    if directory and filename:
        return os.path.join(library_root, "originals", directory, filename)
    elif filename:
        return filename

    return None


def format_photo(index, row, library_root):
    """Format a single photo result for display."""
    filename = row["ZFILENAME"] or "Unknown"
    date_str = coredata_to_datetime(row["ZDATECREATED"]) or "Unknown"
    uuid = row["ZUUID"] or ""

    lines = [f"{index}. {filename}"]
    lines.append(f"   UUID: {uuid}")
    lines.append(f"   Date: {date_str}")

    # Dimensions
    width = row_get(row,"ZWIDTH")
    height = row_get(row,"ZHEIGHT")
    if width and height and width > 0 and height > 0:
        lines.append(f"   Size: {width}x{height}")

    # Location
    lat = row_get(row,"ZLATITUDE")
    lon = row_get(row,"ZLONGITUDE")
    if lat is not None and lon is not None and lat != 0 and lon != 0:
        # Filter out sentinel values (Photos uses very large negative values for "no location")
        if abs(lat) <= 90 and abs(lon) <= 180:
            lines.append(f"   Location: {lat:.4f}, {lon:.4f}")

    # Path
    path = resolve_photo_path(row, library_root)
    if path:
        # Shorten home directory for display
        home = str(Path.home())
        display_path = path.replace(home, "~")
        lines.append(f"   Path: {display_path}")

    return "\n".join(lines)


def cmd_search(conn, library_root, args):
    """Search photos by filename or associated text."""
    keyword = args.keyword
    limit = args.n or 20

    query = """
        SELECT a.ZUUID, a.ZFILENAME, a.ZDATECREATED, a.ZDIRECTORY,
               a.ZLATITUDE, a.ZLONGITUDE,
               a.ZWIDTH, a.ZHEIGHT
        FROM ZASSET a
        LEFT JOIN ZADDITIONALASSETATTRIBUTES attr ON attr.ZASSET = a.Z_PK
        WHERE a.ZTRASHEDSTATE = 0
          AND (
            a.ZFILENAME LIKE ? COLLATE NOCASE
            OR attr.ZTITLE LIKE ? COLLATE NOCASE
            OR attr.ZORIGINALFILENAME LIKE ? COLLATE NOCASE
          )
        ORDER BY a.ZDATECREATED DESC
        LIMIT ?
    """
    pattern = f"%{keyword}%"
    try:
        cursor = conn.execute(query, (pattern, pattern, pattern, limit))
    except sqlite3.OperationalError:
        # Fallback: some macOS versions may not have ZTRASHEDSTATE or ZORIGINALFILENAME
        query = """
            SELECT a.ZUUID, a.ZFILENAME, a.ZDATECREATED, a.ZDIRECTORY,
                   a.ZLATITUDE, a.ZLONGITUDE,
                   a.ZWIDTH, a.ZHEIGHT
            FROM ZASSET a
            LEFT JOIN ZADDITIONALASSETATTRIBUTES attr ON attr.ZASSET = a.Z_PK
            WHERE a.ZFILENAME LIKE ? COLLATE NOCASE
               OR attr.ZTITLE LIKE ? COLLATE NOCASE
            ORDER BY a.ZDATECREATED DESC
            LIMIT ?
        """
        cursor = conn.execute(query, (pattern, pattern, limit))

    rows = cursor.fetchall()
    if not rows:
        print(f"No photos found matching \"{keyword}\".")
        return

    for i, row in enumerate(rows, 1):
        print(format_photo(i, row, library_root))
        if i < len(rows):
            print()

    print(f"\n--- {len(rows)} result(s) shown (max {limit}) ---")


def cmd_recent(conn, library_root, args):
    """List recent photos."""
    days = args.days or 7
    limit = args.n or 20

    # Calculate CoreData timestamp for N days ago
    cutoff = datetime.now() - timedelta(days=days)
    cutoff_coredata = cutoff.timestamp() - COREDATA_EPOCH_OFFSET

    query = """
        SELECT a.ZUUID, a.ZFILENAME, a.ZDATECREATED, a.ZDIRECTORY,
               a.ZLATITUDE, a.ZLONGITUDE,
               a.ZWIDTH, a.ZHEIGHT
        FROM ZASSET a
        WHERE a.ZDATECREATED >= ?
        ORDER BY a.ZDATECREATED DESC
        LIMIT ?
    """
    try:
        # Try with ZTRASHEDSTATE filter first
        query_with_trash = query.replace(
            "WHERE a.ZDATECREATED >= ?",
            "WHERE a.ZTRASHEDSTATE = 0 AND a.ZDATECREATED >= ?"
        )
        cursor = conn.execute(query_with_trash, (cutoff_coredata, limit))
    except sqlite3.OperationalError:
        cursor = conn.execute(query, (cutoff_coredata, limit))

    rows = cursor.fetchall()
    if not rows:
        print(f"No photos found in the last {days} day(s).")
        return

    print(f"Photos from the last {days} day(s):\n")
    for i, row in enumerate(rows, 1):
        print(format_photo(i, row, library_root))
        if i < len(rows):
            print()

    print(f"\n--- {len(rows)} result(s) shown (max {limit}) ---")


def cmd_albums(conn, library_root, args):
    """List all user albums."""
    query = """
        SELECT ZTITLE, ZUUID,
               (SELECT COUNT(*) FROM ZASSET) as ZTOTAL
        FROM ZGENERICALBUM
        WHERE ZTITLE IS NOT NULL
          AND ZTRASHEDSTATE = 0
        ORDER BY ZTITLE
    """
    try:
        cursor = conn.execute(query)
    except sqlite3.OperationalError:
        # Fallback without ZTRASHEDSTATE
        query = """
            SELECT ZTITLE, ZUUID
            FROM ZGENERICALBUM
            WHERE ZTITLE IS NOT NULL
            ORDER BY ZTITLE
        """
        cursor = conn.execute(query)

    rows = cursor.fetchall()
    if not rows:
        print("No albums found.")
        return

    # Get photo counts per album using the join table
    join_table, album_col, asset_col = detect_join_table(conn)

    print("Albums:\n")
    for i, row in enumerate(rows, 1):
        title = row["ZTITLE"]
        uuid = row["ZUUID"] or ""

        count_str = ""
        if join_table and album_col:
            try:
                # Get the album's Z_PK
                pk_cursor = conn.execute(
                    "SELECT Z_PK FROM ZGENERICALBUM WHERE ZUUID = ?", (uuid,)
                )
                pk_row = pk_cursor.fetchone()
                if pk_row:
                    count_cursor = conn.execute(
                        f"SELECT COUNT(*) as cnt FROM {join_table} WHERE {album_col} = ?",
                        (pk_row["Z_PK"],)
                    )
                    count_row = count_cursor.fetchone()
                    if count_row:
                        count_str = f" ({count_row['cnt']} photos)"
            except sqlite3.OperationalError:
                pass

        print(f"  {i}. {title}{count_str}")

    print(f"\n--- {len(rows)} album(s) ---")


def cmd_album(conn, library_root, args):
    """List photos in a specific album."""
    album_name = args.name
    limit = args.n or 20

    # Find the album
    album_cursor = conn.execute(
        "SELECT Z_PK, ZTITLE, ZUUID FROM ZGENERICALBUM WHERE ZTITLE = ? COLLATE NOCASE",
        (album_name,)
    )
    album_row = album_cursor.fetchone()

    if not album_row:
        # Try partial match
        album_cursor = conn.execute(
            "SELECT Z_PK, ZTITLE, ZUUID FROM ZGENERICALBUM WHERE ZTITLE LIKE ? COLLATE NOCASE",
            (f"%{album_name}%",)
        )
        album_row = album_cursor.fetchone()

    if not album_row:
        print(f"Album \"{album_name}\" not found.")
        return

    album_pk = album_row["Z_PK"]
    actual_title = album_row["ZTITLE"]

    join_table, album_col, asset_col = detect_join_table(conn)
    if not join_table:
        print("Error: Could not detect album-asset join table structure.")
        return

    query = f"""
        SELECT a.ZUUID, a.ZFILENAME, a.ZDATECREATED, a.ZDIRECTORY,
               a.ZLATITUDE, a.ZLONGITUDE,
               a.ZWIDTH, a.ZHEIGHT
        FROM ZASSET a
        INNER JOIN {join_table} j ON j.{asset_col} = a.Z_PK
        WHERE j.{album_col} = ?
        ORDER BY a.ZDATECREATED DESC
        LIMIT ?
    """
    cursor = conn.execute(query, (album_pk, limit))
    rows = cursor.fetchall()

    if not rows:
        print(f"No photos found in album \"{actual_title}\".")
        return

    print(f"Album: {actual_title}\n")
    for i, row in enumerate(rows, 1):
        print(format_photo(i, row, library_root))
        if i < len(rows):
            print()

    print(f"\n--- {len(rows)} result(s) shown (max {limit}) ---")


def cmd_info(conn, library_root, args):
    """Show detailed metadata for a photo."""
    identifier = args.identifier

    # Determine if it's a UUID or a path/filename
    is_uuid = len(identifier) == 36 and identifier.count("-") == 4

    if is_uuid:
        where_clause = "a.ZUUID = ?"
        param = identifier
    else:
        # Could be a filename or path — extract filename
        filename = os.path.basename(identifier)
        where_clause = "a.ZFILENAME = ? COLLATE NOCASE"
        param = filename

    query = f"""
        SELECT a.ZUUID, a.ZFILENAME, a.ZDATECREATED, a.ZDIRECTORY,
               a.ZLATITUDE, a.ZLONGITUDE,
               a.ZWIDTH, a.ZHEIGHT,
               a.ZDURATION, a.ZKIND,
               attr.ZTITLE, attr.ZEXIFTIMESTAMPSTRING,
               attr.ZCAMERAMAKE, attr.ZCAMERAMODEL,
               attr.ZLENSMAKE, attr.ZLENSMODEL,
               attr.ZFOCALLENGTHIN35MMFORMAT,
               attr.ZORIGINALFILESIZE, attr.ZORIGINALFILENAME
        FROM ZASSET a
        LEFT JOIN ZADDITIONALASSETATTRIBUTES attr ON attr.ZASSET = a.Z_PK
        WHERE {where_clause}
        LIMIT 1
    """
    try:
        cursor = conn.execute(query, (param,))
    except sqlite3.OperationalError:
        # Simplified fallback query
        query = f"""
            SELECT a.ZUUID, a.ZFILENAME, a.ZDATECREATED, a.ZDIRECTORY,
                   a.ZLATITUDE, a.ZLONGITUDE,
                   a.ZWIDTH, a.ZHEIGHT
            FROM ZASSET a
            WHERE {where_clause}
            LIMIT 1
        """
        cursor = conn.execute(query, (param,))

    row = cursor.fetchone()
    if not row:
        print(f"Photo not found: {identifier}")
        return

    keys = row.keys()

    print(f"Filename: {row['ZFILENAME'] or 'Unknown'}")
    print(f"UUID: {row['ZUUID'] or 'Unknown'}")

    date_str = coredata_to_datetime(row["ZDATECREATED"])
    if date_str:
        print(f"Date: {date_str}")

    if "ZTITLE" in keys and row["ZTITLE"]:
        print(f"Title: {row['ZTITLE']}")

    if "ZORIGINALFILENAME" in keys and row["ZORIGINALFILENAME"]:
        print(f"Original filename: {row['ZORIGINALFILENAME']}")

    width = row_get(row,"ZWIDTH")
    height = row_get(row,"ZHEIGHT")
    if width and height and width > 0 and height > 0:
        print(f"Dimensions: {width}x{height}")

    if "ZORIGINALFILESIZE" in keys and row["ZORIGINALFILESIZE"]:
        size_bytes = row["ZORIGINALFILESIZE"]
        if size_bytes >= 1048576:
            print(f"File size: {size_bytes / 1048576:.1f} MB")
        elif size_bytes >= 1024:
            print(f"File size: {size_bytes / 1024:.1f} KB")
        else:
            print(f"File size: {size_bytes} B")

    duration = row_get(row,"ZDURATION")
    if duration and duration > 0:
        print(f"Duration: {duration:.1f}s")

    kind = row_get(row,"ZKIND")
    if kind is not None:
        kind_names = {0: "Photo", 1: "Video"}
        print(f"Type: {kind_names.get(kind, f'Unknown ({kind})')}")

    lat = row_get(row,"ZLATITUDE")
    lon = row_get(row,"ZLONGITUDE")
    if lat is not None and lon is not None and abs(lat) <= 90 and abs(lon) <= 180 and (lat != 0 or lon != 0):
        print(f"Location: {lat:.6f}, {lon:.6f}")

    if "ZEXIFTIMESTAMPSTRING" in keys and row["ZEXIFTIMESTAMPSTRING"]:
        print(f"EXIF timestamp: {row['ZEXIFTIMESTAMPSTRING']}")

    # Camera info
    camera_parts = []
    if "ZCAMERAMAKE" in keys and row["ZCAMERAMAKE"]:
        camera_parts.append(row["ZCAMERAMAKE"])
    if "ZCAMERAMODEL" in keys and row["ZCAMERAMODEL"]:
        camera_parts.append(row["ZCAMERAMODEL"])
    if camera_parts:
        print(f"Camera: {' '.join(camera_parts)}")

    lens_parts = []
    if "ZLENSMAKE" in keys and row["ZLENSMAKE"]:
        lens_parts.append(row["ZLENSMAKE"])
    if "ZLENSMODEL" in keys and row["ZLENSMODEL"]:
        lens_parts.append(row["ZLENSMODEL"])
    if lens_parts:
        print(f"Lens: {' '.join(lens_parts)}")

    if "ZFOCALLENGTHIN35MMFORMAT" in keys and row["ZFOCALLENGTHIN35MMFORMAT"]:
        print(f"Focal length (35mm eq): {row['ZFOCALLENGTHIN35MMFORMAT']}mm")

    path = resolve_photo_path(row, library_root)
    if path:
        home = str(Path.home())
        display_path = path.replace(home, "~")
        print(f"Path: {display_path}")
        if os.path.exists(path):
            print(f"File exists: Yes")
        else:
            print(f"File exists: No (may be in iCloud)")


def cmd_export(conn, library_root, args):
    """Export (copy) a photo to a specified output path."""
    uuid = args.uuid
    output_path = args.output_path

    # Expand ~ in output path
    output_path = os.path.expanduser(output_path)

    # Find the photo
    query = """
        SELECT a.ZUUID, a.ZFILENAME, a.ZDIRECTORY
        FROM ZASSET a
        WHERE a.ZUUID = ?
        LIMIT 1
    """
    cursor = conn.execute(query, (uuid,))
    row = cursor.fetchone()

    if not row:
        print(f"Photo not found with UUID: {uuid}")
        sys.exit(1)

    source_path = resolve_photo_path(row, library_root)
    if not source_path or not os.path.exists(source_path):
        print(f"Source file not found: {source_path or 'unknown'}")
        print("The photo may be stored in iCloud and not downloaded locally.")
        sys.exit(1)

    # If output_path is a directory, use original filename
    if os.path.isdir(output_path):
        output_path = os.path.join(output_path, row["ZFILENAME"])

    # Create parent directory if needed
    parent = os.path.dirname(output_path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)

    shutil.copy2(source_path, output_path)
    print(f"Exported: {row['ZFILENAME']}")
    print(f"  From: {source_path}")
    print(f"  To:   {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Search and browse Apple Photos library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # search
    p_search = subparsers.add_parser("search", help="Search photos by keyword")
    p_search.add_argument("keyword", help="Search keyword")
    p_search.add_argument("-n", type=int, default=20, help="Max results (default: 20)")

    # recent
    p_recent = subparsers.add_parser("recent", help="Recent photos")
    p_recent.add_argument("days", nargs="?", type=int, default=7, help="Days to look back (default: 7)")
    p_recent.add_argument("-n", type=int, default=20, help="Max results (default: 20)")

    # albums
    subparsers.add_parser("albums", help="List all albums")

    # album
    p_album = subparsers.add_parser("album", help="List photos in an album")
    p_album.add_argument("name", help="Album name (exact or partial match)")
    p_album.add_argument("-n", type=int, default=20, help="Max results (default: 20)")

    # info
    p_info = subparsers.add_parser("info", help="Show photo metadata")
    p_info.add_argument("identifier", help="Photo UUID or filename")

    # export
    p_export = subparsers.add_parser("export", help="Export a photo to a path")
    p_export.add_argument("uuid", help="Photo UUID")
    p_export.add_argument("output_path", help="Output file or directory path")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Find and connect to database
    db_path = find_photos_db()
    if not db_path:
        print("Error: Photos library database not found.")
        print("Searched locations:")
        print("  ~/Pictures/Photos Library.photoslibrary/database/Photos.sqlite")
        print("  ~/Pictures/*.photoslibrary/database/Photos.sqlite")
        print("  ~/Library/Containers/com.apple.Photos/.../Photos.sqlite")
        print()
        print("Possible causes:")
        print("  - Photos library is in a non-standard location")
        print("  - Full Disk Access is required (System Settings > Privacy & Security > Full Disk Access)")
        sys.exit(1)

    library_root = get_library_root(db_path)

    try:
        conn = connect_db(db_path)
    except sqlite3.OperationalError as e:
        if "unable to open" in str(e).lower() or "readonly" in str(e).lower():
            print(f"Error: Cannot open Photos database at {db_path}")
            print("Full Disk Access may be required.")
            print("Grant access in: System Settings > Privacy & Security > Full Disk Access")
        else:
            print(f"Error connecting to database: {e}")
        sys.exit(1)

    try:
        commands = {
            "search": cmd_search,
            "recent": cmd_recent,
            "albums": cmd_albums,
            "album": cmd_album,
            "info": cmd_info,
            "export": cmd_export,
        }
        commands[args.command](conn, library_root, args)
    except sqlite3.OperationalError as e:
        error_msg = str(e).lower()
        if "no such table" in error_msg:
            print(f"Error: Database schema mismatch — {e}")
            print("This may indicate an incompatible Photos library version.")
        elif "database is locked" in error_msg:
            print("Error: Photos database is locked. Close Photos.app and try again.")
        else:
            print(f"Database error: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
