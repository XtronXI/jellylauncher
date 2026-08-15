from common import *
from modules import ui
import json
import sqlite3
from pathlib import Path
import xml.etree.ElementTree as ET

def metadata(context):
    """
    Make the on-disk metadata library match the database's current GUIDs.

    1. Rewrites stored metadata paths (e.g. BaseItemImageInfos.Path) so they
       reference the active 'library' tree with a consistent {prefix}/{guid}
       folder layout, repairing any broken paths left by earlier GUID rewrites.
    2. Moves each migrated item's metadata folder from its old-GUID name
       (searching the active tree and the parked linux_library/windows_library
       trees) to its new-GUID name.

    Idempotent: once folders live under their new names and paths are
    consistent, later runs find nothing to do.
    """
    ui.start("Migrating metadata")
    db = context.data_dir / "data" / "jellyfin.db"

    library = context.data_dir / "metadata" / "library"
    parked = [
        context.data_dir / "metadata" / "linux_library",
        context.data_dir / "metadata" / "windows_library",
    ]

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    # 1. Heal stored metadata paths in every TEXT cell.
    path_updates = 0

    for table in [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )]:
        for column in [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]:
            rows = conn.execute(
                f'SELECT rowid, "{column}" FROM "{table}" '
                f'WHERE "{column}" IS NOT NULL'
            ).fetchall()

            for rowid, value in rows:
                if not isinstance(value, str) or "metadata" not in value:
                    continue

                new_value = normalize_metadata_path(value)

                if new_value == value:
                    continue

                conn.execute(
                    f'UPDATE "{table}" SET "{column}" = ? WHERE rowid = ?',
                    (new_value, rowid)
                )
                path_updates += 1

    conn.commit()

    # 2. Move metadata folders for items whose GUID differs between OSes.
    items = conn.execute("""
        SELECT Id, Type, Path
        FROM BaseItems
        WHERE Path IS NOT NULL AND Path != ''
    """).fetchall()
    conn.close()

    folder_moves = 0
    missing = 0

    for item in items:
        stored = normalize_guid(item["Id"])

        if stored is None:
            continue

        current_path = translate(item["Path"], context)
        other_path = translate_reverse(current_path, context)

        if other_path == current_path:
            continue

        old_guid = str(
            jellyfin_guid(
                item["Type"],
                other_path,
                context.data_dir,
                case_sensitive=context.case_sensitive
            )
        ).upper()

        if old_guid == stored:
            continue

        old_n = old_guid.replace("-", "").lower()
        new_n = stored.replace("-", "").lower()

        target = library / new_n[:2] / new_n

        if target.exists():
            continue

        source = None

        # A folder may already carry the correct (new) GUID name but sit in
        # a parked tree - relocate it into the active library.
        for tree in parked:
            candidate = tree / new_n[:2] / new_n

            if candidate.exists():
                source = candidate
                break

        # Otherwise find the old-GUID folder anywhere and rename + relocate.
        if source is None:
            for tree in [library] + parked:
                candidate = tree / old_n[:2] / old_n

                if candidate.exists():
                    source = candidate
                    break

        if source is None:
            missing += 1
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        folder_moves += 1
        ui.verbose(context, f"{source.relative_to(context.data_dir)} -> {target.relative_to(context.data_dir)}")

    if path_updates or folder_moves or missing:
        ui.verbose(context,
            f"Updated {path_updates} metadata paths, "
            f"moved {folder_moves} folders"
            + (f", {missing} items had no stored metadata" if missing else "")
            + "."
        )
    else:
        ui.verbose(context, "Metadata already up-to-date.")
    ui.success("Migrating metadata")

def mblink(context):
    ui.start("Updating .mblink paths")

    root = context.data_dir / "root" / "default"

    for file in root.rglob("*.mblink"):
        old_path = file.read_text(encoding="utf-8").strip()
        new_path = translate(old_path, context)

        if old_path != new_path:
            ui.verbose(context, f"{old_path} -> {new_path}")
            file.write_text(new_path, encoding="utf-8")
        else:
            ui.verbose(context, f"{old_path} is correct.")
    ui.success("Updating .mblink paths")

# ----------------------------------- Database ------------------------------------

def database(context, db=None):
    ui.start("Migrating database")

    db = Path(db) if db is not None else context.data_dir / "data" / "jellyfin.db"

    conn = sqlite3.connect(db)
    cur = conn.cursor()

    cur.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type='table'
    """)

    tables = [row[0] for row in cur.fetchall()]
    updates = 0

    for table in tables:
        cur.execute(f'PRAGMA table_info("{table}")')

        for _, column, col_type, *_ in cur.fetchall():

            if col_type.upper() != "TEXT":
                continue

            cur.execute(f'''
                SELECT rowid, "{column}"
                FROM "{table}"
                WHERE "{column}" IS NOT NULL
            ''')

            rows = cur.fetchall()

            for rowid, value in rows:
                if not isinstance(value, str):
                    continue

                if table == "BaseItems" and column == "Data":
                    new_value = _translate_data_json(value, context)
                else:
                    new_value = translate(value, context)

                if new_value == value:
                    continue

                cur.execute(f'''
                    UPDATE "{table}"
                    SET "{column}" = ?
                    WHERE rowid = ?
                ''', (new_value, rowid))

                updates += 1

    conn.commit()
    conn.close()

    if updates:
        ui.verbose(context, f"Updated {updates} database entries.")
    else:
        ui.verbose(context, "Database already up-to-date.")
    ui.success("Migrating database")
def _translate_data_json(value, context):
    """
    Translate every path embedded inside a BaseItems.Data JSON blob.
    translate() only modifies absolute paths, so other strings pass through.
    """
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return value

    def walk(node):
        if isinstance(node, str):
            return translate(node, context)
        if isinstance(node, list):
            return [walk(item) for item in node]
        if isinstance(node, dict):
            return {key: walk(item) for key, item in node.items()}
        return node

    return json.dumps(walk(data), ensure_ascii=False)


def guids(context, db=None):
    """
    Recompute every item Id that changes when the shared Data folder moves
    between operating systems, and rewrite all references across the database.

    Only items whose filesystem path actually changes are migrated
    (e.g. /mnt/stream/... <-> D:\\...). Internal items (root folders,
    CollectionFolders, People/Genres/Studios) derive their Id from a
    data-dir-relative key and are stable, so they are skipped.

    Idempotent: a second run (or a run on the OS the paths already match)
    produces no mappings and changes nothing.
    """
    ui.start("Migrating GUIDs")

    db = Path(db) if db is not None else context.data_dir / "data" / "jellyfin.db"
    if not db.exists():
        ui.verbose(context, "Database not found - skipping.")
        ui.fail("Migrating metadata")
        raise FileNotFoundError(f"Database not found: {db}")

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute("""
            SELECT
                Id, Name, Type, Path, IndexNumber
            FROM BaseItems
            WHERE Path IS NOT NULL
              AND Path != ''
        """).fetchall()

        mapping = {}

        for row in rows:
            old_guid = normalize_guid(row["Id"])

            if old_guid is None:
                continue

            new_path = translate(row["Path"], context)

            if new_path == row["Path"]:
                continue

            new_guid = str(
                jellyfin_guid(
                    row["Type"],
                    new_path,
                    context.data_dir,
                    case_sensitive=context.case_sensitive
                )
            ).upper()

            if old_guid != new_guid:
                mapping[old_guid] = new_guid

        if not mapping:
            conn.close()
            ui.verbose(context, "GUIDs already up-to-date.")
            ui.success("Migrating GUIDs")
            return

        references = _rewrite_references(conn, mapping)
        _rewrite_baseitem_ids(conn, mapping)
        presentation_keys = _recompute_presentation_keys(conn, mapping)

        conn.commit()

        ui.verbose(context, f"Migrated {len(mapping)} item IDs.")
        ui.verbose(context, f"Rewrote {references} referencing cells.")
        ui.verbose(context, f"Updated {presentation_keys} presentation keys.")
    finally:
        conn.close()
    
    ui.success("Migrating GUIDs")

def _rewrite_references(conn, mapping):
    """Rewrite GUID references in every table/column except BaseItems.Id."""
    updates = 0

    tables = [r[0] for r in conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        """
    )]

    for table in tables:
        columns = conn.execute(f'PRAGMA table_info("{table}")').fetchall()

        for column in columns:
            column_name = column[1]

            if table == "BaseItems" and column_name == "Id":
                continue

            rows = conn.execute(
                f'SELECT rowid, "{column_name}" FROM "{table}" WHERE "{column_name}" IS NOT NULL'
            ).fetchall()

            for rowid, value in rows:
                if not isinstance(value, str):
                    continue

                new_value = rewrite_guids_in_text(value, mapping)

                if new_value == value:
                    continue

                conn.execute(
                    f'UPDATE "{table}" SET "{column_name}" = ? WHERE rowid = ?',
                    (new_value, rowid)
                )
                updates += 1

    return updates


def _rewrite_baseitem_ids(conn, mapping):
    """
    Rewrite BaseItems.Id using a two-phase park so no new value can
    collide with another row's Id during the update.
    """
    all_ids = [normalize_guid(r[0]) for r in conn.execute("SELECT Id FROM BaseItems")]
    full = {guid: mapping.get(guid, guid) for guid in all_ids if guid is not None}

    conn.execute("UPDATE BaseItems SET Id = 'PARK:' || Id")

    for old, new in full.items():
        conn.execute(
            "UPDATE BaseItems SET Id = ? WHERE Id = ?",
            (new, "PARK:" + old)
        )


def _recompute_presentation_keys(conn, mapping):
    """
    Recompute PresentationUniqueKey and SeriesPresentationUniqueKey for
    items whose Id (or whose owning Series) changed during the migration.

    A regular item's key is its own Id in N-format (lowercase, no dashes);
    a Season uses {series PUK}-{IndexNumber:000}; SeriesPresentationUniqueKey
    is the owning Series' key.

    Items not affected by the migration keep their existing keys, so
    name-based keys (Person-<Name>, Genre-<Name>, Studio-<Name>) and any
    other stable keys are preserved verbatim.
    """
    changed_ids = set(mapping.values())

    rows = conn.execute("""
        SELECT
            Id, Type, SeriesId, IndexNumber,
            PresentationUniqueKey, SeriesPresentationUniqueKey
        FROM BaseItems
    """).fetchall()

    id_to_puk = {}

    for row in rows:
        guid = normalize_guid(row["Id"])

        if guid is None:
            continue

        id_to_puk[guid] = guid.replace("-", "").lower()

    updates = 0

    for row in rows:
        guid = normalize_guid(row["Id"])
        if guid is None:
            continue

        series_id = normalize_guid(row["SeriesId"])

        if guid not in changed_ids and series_id not in changed_ids:
            continue

        if (
            row["Type"] == "MediaBrowser.Controller.Entities.TV.Season"
            and series_id is not None
            and series_id in id_to_puk
            and row["IndexNumber"] is not None
        ):
            puk = id_to_puk[series_id] + "-" + f"{row['IndexNumber']:03d}"
        else:
            puk = id_to_puk[guid]

        series_puk = (
            id_to_puk[series_id]
            if series_id is not None and series_id in id_to_puk
            else None
        )

        if row["PresentationUniqueKey"] != puk or row["SeriesPresentationUniqueKey"] != series_puk:
            conn.execute("""
                UPDATE BaseItems
                SET PresentationUniqueKey = ?, SeriesPresentationUniqueKey = ?
                WHERE Id = ?
            """, (puk, series_puk, guid))
            updates += 1

    return updates

# -------------------------------------- XML --------------------------------------

def _translate(element, context):
    updates = 0

    if element.text:
        new = translate(element.text, context)
        if new != element.text:
            element.text = new
            updates += 1

    for child in element:
        updates += _translate(child, context)

    return updates

def _deduplicate_options(tree):
    updates = 0

    root = tree.getroot()
    path_infos = root.find("PathInfos")

    if path_infos is None:
        return 0

    seen = set()

    for media_path in list(path_infos):
        path = media_path.find("Path")

        if path is None or path.text is None:
            continue

        if path.text in seen:
            path_infos.remove(media_path)
            updates += 1
        else:
            seen.add(path.text)
    
    return updates


def xml(context):
    ui.start("Migrating XML")

    updates = 0
    plugins_dir = context.data_dir / "plugins"

    for xml_file in context.data_dir.rglob("*.xml"):
        if plugins_dir in xml_file.parents:
            continue
        tree = ET.parse(xml_file)
        file_updates = 0
        file_updates += _translate(tree.getroot(), context)
        file_updates += _deduplicate_options(tree)

        if file_updates:
            tree.write(xml_file, encoding="utf-8", xml_declaration=True)
            updates += file_updates

    if updates:
        ui.verbose(context, f"Updated {updates} XML entries.")
    else:
        ui.verbose(context, "XML already up-to-date.")
    ui.success("Migrating XML")